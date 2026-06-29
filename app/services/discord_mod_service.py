"""
app/services/discord_mod_service.py — Modération automatique en temps réel sur Discord.

Entièrement indépendante de la modération Twitch (réglages et liste de mots
séparés, dans des tables dédiées `discord_moderation_settings` /
`discord_banned_words`) : la première version réutilisait telles quelles les
règles Twitch (notamment le blocage de liens), ce qui a généré des faux
positifs car le Discord du serveur a un usage des liens très différent du
chat Twitch. Cette version repart d'une base propre, pensée pour Discord :

- Mots interdits (liste propre à Discord, gérable depuis /admin/discord_moderation)
- Spam (X messages en moins de Y secondes)
- Exemption par rôle : les rôles cochés comme "exempts" ne sont jamais modérés,
  en plus du bypass déjà existant pour quiconque a la permission "Gérer les
  messages" (modérateurs/admins du serveur).
"""

import logging
import re
import time
from collections import defaultdict
import asyncio
from datetime import date, datetime, timedelta, timezone

import discord

from app.core.config import settings
from app.core.database import get_db_connection

PLATFORM_EMOJI = {"Twitch": "🟣", "Discord": "🔵"}

logger = logging.getLogger("masthbot.discord_mod")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True


async def init_discord_mod_tables() -> None:
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_moderation_settings (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                banned_words_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                banned_words_action   TEXT NOT NULL DEFAULT 'delete',
                banned_words_duration INTEGER NOT NULL DEFAULT 0,
                spam_enabled        BOOLEAN NOT NULL DEFAULT FALSE,
                spam_limit          INTEGER NOT NULL DEFAULT 5,
                spam_timeframe      INTEGER NOT NULL DEFAULT 10,
                spam_action         TEXT NOT NULL DEFAULT 'delete',
                spam_duration       INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute(
            "INSERT INTO discord_moderation_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_banned_words (
                id          SERIAL PRIMARY KEY,
                word        TEXT NOT NULL UNIQUE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_exempt_roles (
                id          SERIAL PRIMARY KEY,
                role_id     TEXT NOT NULL UNIQUE,
                role_name   TEXT NOT NULL DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_features_settings (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                tiktok_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
                tiktok_username     TEXT NOT NULL DEFAULT '',
                tiktok_channel_id   TEXT NOT NULL DEFAULT '',
                leave_enabled       BOOLEAN NOT NULL DEFAULT FALSE,
                leave_channel_id    TEXT NOT NULL DEFAULT '',
                youtube_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
                youtube_channel_id  TEXT NOT NULL DEFAULT '',
                youtube_discord_channel_id TEXT NOT NULL DEFAULT ''
            )
        """)
        await db.execute(
            "INSERT INTO discord_features_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
        )
        for col, coltype in [
            ("youtube_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("youtube_channel_id", "TEXT NOT NULL DEFAULT ''"),
            ("youtube_discord_channel_id", "TEXT NOT NULL DEFAULT ''"),
            ("clear_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("sondage_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("warn_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("slowmode_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("lock_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("userinfo_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("giveaway_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("annonce_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("youtube_announce_message", "TEXT NOT NULL DEFAULT '📺 **Nouvelle vidéo YouTube !**'"),
            ("tiktok_announce_message", "TEXT NOT NULL DEFAULT '🎵 **Nouvelle vidéo TikTok !**'"),
            ("showtiktok_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("showtiktok_message", "TEXT NOT NULL DEFAULT '🎵 TikTok affiché à l''écran ! — {title} {url}'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE discord_features_settings ADD COLUMN IF NOT EXISTS {col} {coltype}")
            except Exception:
                pass

        # --- Bienvenue ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_welcome_settings (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                channel_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                channel_id      TEXT NOT NULL DEFAULT '',
                channel_message TEXT NOT NULL DEFAULT 'Bienvenue {member} sur le serveur ! 🎉',
                dm_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
                dm_message      TEXT NOT NULL DEFAULT 'Salut {member} ! Bienvenue sur le serveur, n''hésite pas à lire le règlement 😺',
                embed_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
                embed_title       TEXT NOT NULL DEFAULT '🎉 Bienvenue sur le serveur !',
                embed_description TEXT NOT NULL DEFAULT 'On est super content de t''accueillir {member} !\nN''hésite pas à lire le règlement et à te présenter 😺',
                embed_color       TEXT NOT NULL DEFAULT '#00f5c3'
            )
        """)
        await db.execute("INSERT INTO discord_welcome_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
        for col, coltype in [
            ("embed_enabled", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("embed_title", "TEXT NOT NULL DEFAULT '🎉 Bienvenue sur le serveur !'"),
            ("embed_description", "TEXT NOT NULL DEFAULT 'Bienvenue {member} !'"),
            ("embed_color", "TEXT NOT NULL DEFAULT '#00f5c3'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE discord_welcome_settings ADD COLUMN IF NOT EXISTS {col} {coltype}")
            except Exception:
                pass

        # --- Portail règlement (rôle général débloqué en réagissant au règlement) ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_gate_settings (
                id               INTEGER PRIMARY KEY CHECK (id = 1),
                enabled          BOOLEAN NOT NULL DEFAULT FALSE,
                channel_id       TEXT NOT NULL DEFAULT '',
                message_id       TEXT NOT NULL DEFAULT '',
                rules_text       TEXT NOT NULL DEFAULT '',
                emoji            TEXT NOT NULL DEFAULT '✅',
                general_role_id  TEXT NOT NULL DEFAULT ''
            )
        """)
        await db.execute("INSERT INTO discord_gate_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")

        # --- Rôles auto-attribuables (panneau à réactions, ex: jeux, notifications) ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_self_roles (
                id          SERIAL PRIMARY KEY,
                channel_id  TEXT NOT NULL,
                message_id  TEXT,
                emoji       TEXT NOT NULL,
                role_id     TEXT NOT NULL,
                role_name   TEXT NOT NULL DEFAULT '',
                label       TEXT NOT NULL DEFAULT ''
            )
        """)

        # --- Anniversaires Discord ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_birthdays (
                id              SERIAL PRIMARY KEY,
                discord_user_id TEXT NOT NULL UNIQUE,
                username        TEXT NOT NULL DEFAULT '',
                day             INTEGER NOT NULL,
                month           INTEGER NOT NULL,
                year            INTEGER,
                last_announced_year INTEGER,
                set_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        try:
            await db.execute("ALTER TABLE discord_birthdays ADD COLUMN IF NOT EXISTS year INTEGER")
        except Exception:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_birthday_settings (
                id                INTEGER PRIMARY KEY CHECK (id = 1),
                enabled           BOOLEAN NOT NULL DEFAULT FALSE,
                channel_id        TEXT NOT NULL DEFAULT '',
                message_template  TEXT NOT NULL DEFAULT '🎂 Joyeux anniversaire {member} !! Profite bien de ta journée 🥳'
            )
        """)
        await db.execute("INSERT INTO discord_birthday_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")

        # --- Avertissements (/warn) ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discord_warnings (
                id              SERIAL PRIMARY KEY,
                discord_user_id TEXT NOT NULL,
                username        TEXT NOT NULL DEFAULT '',
                reason          TEXT NOT NULL DEFAULT '',
                moderator       TEXT NOT NULL DEFAULT '',
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


class DiscordModBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Historique en mémoire des derniers messages par utilisateur, pour la détection de spam.
        # Volontairement non persisté : ça repart à zéro à chaque redémarrage, ce qui est acceptable.
        self.recent_messages: dict[int, list[tuple[discord.Message, float]]] = defaultdict(list)
        self.tree = discord.app_commands.CommandTree(self)
        self._register_slash_commands()
        # Giveaways actifs en mémoire : message_id -> {"prize": str, "end_at": datetime}
        # Volontairement non persisté, comme self.recent_messages : un redémarrage pendant un
        # giveaway en cours est acceptable, il suffit de relancer la commande.
        self.active_giveaways: dict[int, dict] = {}

    def _register_slash_commands(self):
        @self.tree.command(name="anniversaire", description="Enregistre ta date d'anniversaire (visible seulement par toi)")
        @discord.app_commands.describe(date="Au format JJ/MM ou JJ/MM/AAAA (ex: 25/12 ou 25/12/2000)")
        async def anniversaire_cmd(interaction: discord.Interaction, date: str):
            await self._handle_birthday_slash(interaction, date)

        @self.tree.command(name="clear", description="Supprime les X derniers messages du salon")
        @discord.app_commands.describe(nombre="Nombre de messages à supprimer (1 à 100)")
        async def clear_cmd(interaction: discord.Interaction, nombre: discord.app_commands.Range[int, 1, 100]):
            await self._handle_clear_slash(interaction, nombre)

        @self.tree.command(name="sondage", description="Crée un sondage avec réactions")
        @discord.app_commands.describe(
            question="La question du sondage",
            option1="Option 1", option2="Option 2",
            option3="Option 3 (optionnel)", option4="Option 4 (optionnel)",
            option5="Option 5 (optionnel)",
        )
        async def sondage_cmd(
            interaction: discord.Interaction,
            question: str,
            option1: str,
            option2: str,
            option3: str = "",
            option4: str = "",
            option5: str = "",
        ):
            options = [o for o in [option1, option2, option3, option4, option5] if o.strip()]
            await self._handle_poll_slash(interaction, question, options)

        @self.tree.command(name="warn", description="Avertit un membre (loggé dans Logs_Moderation)")
        @discord.app_commands.describe(membre="Le membre à avertir", raison="Raison de l'avertissement")
        async def warn_cmd(interaction: discord.Interaction, membre: discord.Member, raison: str):
            await self._handle_warn_slash(interaction, membre, raison)

        @self.tree.command(name="slowmode", description="Active le mode lent sur ce salon")
        @discord.app_commands.describe(secondes="Délai entre deux messages, en secondes (0 pour désactiver, max 21600)")
        async def slowmode_cmd(interaction: discord.Interaction, secondes: discord.app_commands.Range[int, 0, 21600]):
            await self._handle_slowmode_slash(interaction, secondes)

        @self.tree.command(name="lock", description="Verrouille ce salon (les membres ne peuvent plus écrire)")
        async def lock_cmd(interaction: discord.Interaction):
            await self._handle_lock_slash(interaction, locked=True)

        @self.tree.command(name="unlock", description="Déverrouille ce salon")
        async def unlock_cmd(interaction: discord.Interaction):
            await self._handle_lock_slash(interaction, locked=False)

        @self.tree.command(name="userinfo", description="Affiche la fiche d'un membre (visible seulement par toi)")
        @discord.app_commands.describe(membre="Le membre à consulter")
        async def userinfo_cmd(interaction: discord.Interaction, membre: discord.Member):
            await self._handle_userinfo_slash(interaction, membre)

        @self.tree.command(name="giveaway", description="Lance un tirage au sort avec réaction 🎉")
        @discord.app_commands.describe(
            prix="Ce que le gagnant remporte",
            duree_minutes="Durée du giveaway en minutes",
        )
        async def giveaway_cmd(interaction: discord.Interaction, prix: str, duree_minutes: discord.app_commands.Range[int, 1, 10080]):
            await self._handle_giveaway_slash(interaction, prix, duree_minutes)

        @self.tree.command(name="annonce", description="Poste une annonce en embed dans un salon")
        @discord.app_commands.describe(salon="Salon de destination", titre="Titre de l'annonce", message="Contenu de l'annonce")
        async def annonce_cmd(interaction: discord.Interaction, salon: discord.TextChannel, titre: str, message: str):
            await self._handle_annonce_slash(interaction, salon, titre, message)

    async def setup_hook(self):
        guild_id = settings.GUILD_ID
        try:
            if guild_id:
                guild_obj = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
                logger.info(f"✅ [DISCORD MOD] Commandes slash synchronisées sur le serveur {guild_id}.")
            else:
                await self.tree.sync()
                logger.info("✅ [DISCORD MOD] Commandes slash synchronisées globalement (peut prendre jusqu'à 1h pour apparaître).")
        except Exception as e:
            logger.error(f"❌ [DISCORD MOD] Échec synchronisation des commandes slash : {e}")

    async def on_ready(self):
        logger.info(f"✅ [DISCORD MOD] Bot connecté en tant que {self.user} — modération active.")

    async def on_member_join(self, member: discord.Member):
        try:
            async with get_db_connection() as db:
                await db.execute("SELECT * FROM discord_welcome_settings WHERE id = 1")
                row = await db.fetchone()
            if not row:
                return
            row = dict(row)

            def _fill(text: str, use_mention: bool = True) -> str:
                val = member.mention if use_mention else member.display_name
                return text.replace("{member}", val).replace("{membre}", val)

            if row.get("channel_enabled") and row.get("channel_id"):
                try:
                    channel = self.get_channel(int(row["channel_id"])) or await self.fetch_channel(int(row["channel_id"]))
                    msg = _fill(row["channel_message"])

                    embed = None
                    if row.get("embed_enabled"):
                        try:
                            color = discord.Color(int(row["embed_color"].lstrip("#"), 16))
                        except (ValueError, AttributeError):
                            color = discord.Color(0x00F5C3)
                        embed = discord.Embed(
                            title=_fill(row["embed_title"], use_mention=False),
                            description=_fill(row["embed_description"]),
                            color=color,
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        embed.set_footer(text=f"Membre n°{member.guild.member_count} • {member.guild.name}")
                        embed.timestamp = datetime.now(timezone.utc)

                    await channel.send(content=msg, embed=embed)
                except Exception as e:
                    logger.error(f"❌ [WELCOME] Échec message salon pour {member} : {e}")

            if row.get("dm_enabled"):
                try:
                    msg = row["dm_message"].replace("{member}", member.display_name).replace("{membre}", member.display_name)
                    await member.send(msg)
                except discord.Forbidden:
                    logger.warning(f"⚠️ [WELCOME] {member} a ses DM fermés, message privé ignoré.")
                except Exception as e:
                    logger.error(f"❌ [WELCOME] Échec DM pour {member} : {e}")
        except Exception as e:
            logger.error(f"❌ [WELCOME] Erreur générale on_member_join pour {member} : {e}")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member is None or payload.member.bot:
            return
        await self._handle_reaction(payload, adding=True)

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == (self.user.id if self.user else None):
            return
        await self._handle_reaction(payload, adding=False)

    async def _handle_reaction(self, payload: discord.RawReactionActionEvent, adding: bool):
        emoji = str(payload.emoji)
        guild = self.get_guild(payload.guild_id) if payload.guild_id else None
        if not guild:
            return

        try:
            # 1. Portail règlement
            async with get_db_connection() as db:
                await db.execute("SELECT * FROM discord_gate_settings WHERE id = 1")
                gate = await db.fetchone()

            if gate and gate["enabled"] and str(payload.message_id) == gate["message_id"] and emoji == gate["emoji"]:
                if gate["general_role_id"]:
                    member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
                    role = guild.get_role(int(gate["general_role_id"]))
                    if member and role:
                        try:
                            if adding:
                                await member.add_roles(role, reason="Règlement accepté")
                                logger.info(f"✅ [GATE] Rôle général attribué à {member.display_name}")
                            else:
                                await member.remove_roles(role, reason="Réaction règlement retirée")
                                logger.info(f"🚫 [GATE] Rôle général retiré à {member.display_name} (réaction retirée)")
                        except discord.Forbidden:
                            logger.error("❌ [GATE] Permissions insuffisantes pour (re)attribuer le rôle général (rôle du bot trop bas ?)")
                return

            # 2. Rôles auto-attribuables
            async with get_db_connection() as db:
                await db.execute(
                    "SELECT * FROM discord_self_roles WHERE message_id = ? AND emoji = ?",
                    str(payload.message_id), emoji
                )
                self_role = await db.fetchone()

            if self_role:
                member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
                role = guild.get_role(int(self_role["role_id"]))
                if member and role:
                    try:
                        if adding:
                            await member.add_roles(role, reason="Auto-attribution")
                        else:
                            await member.remove_roles(role, reason="Retrait auto-attribution")
                    except discord.Forbidden:
                        logger.error(f"❌ [SELF-ROLES] Permissions insuffisantes pour {role.name} (rôle du bot trop bas ?)")
        except Exception as e:
            logger.error(f"❌ [REACTION] Erreur traitement réaction : {e}")

    async def _handle_birthday_slash(self, interaction: discord.Interaction, date_str: str):
        parts = date_str.strip().split("/")
        if len(parts) not in (2, 3):
            await interaction.response.send_message(
                "❌ Format invalide. Utilise `JJ/MM` (ex: `25/12`) ou `JJ/MM/AAAA` (ex: `25/12/2000`).",
                ephemeral=True
            )
            return

        try:
            day, month = int(parts[0]), int(parts[1])
            year = int(parts[2]) if len(parts) == 3 else None
            if not (1 <= day <= 31 and 1 <= month <= 12):
                raise ValueError()
            if year is not None and not (1900 <= year <= datetime.now().year):
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "❌ Date invalide. Utilise `JJ/MM` (ex: `25/12`) ou `JJ/MM/AAAA` (ex: `25/12/2000`).",
                ephemeral=True
            )
            return

        async with get_db_connection() as db:
            await db.execute(
                "INSERT INTO discord_birthdays (discord_user_id, username, day, month, year) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (discord_user_id) DO UPDATE SET day = EXCLUDED.day, month = EXCLUDED.month, "
                "year = EXCLUDED.year, username = EXCLUDED.username",
                str(interaction.user.id), interaction.user.display_name, day, month, year
            )

        date_display = f"{day:02d}/{month:02d}" + (f"/{year}" if year else "")
        await interaction.response.send_message(f"🎂 C'est noté ! Anniversaire enregistré : {date_display}", ephemeral=True)

    @staticmethod
    def _is_mod_or_owner(member: discord.Member) -> bool:
        return member.guild_permissions.manage_messages or member.guild.owner_id == member.id

    async def _handle_clear_slash(self, interaction: discord.Interaction, nombre: int):
        member = interaction.user
        if not isinstance(member, discord.Member) or not self._is_mod_or_owner(member):
            await interaction.response.send_message("❌ Tu n'as pas la permission de gérer les messages.", ephemeral=True)
            return
        async with get_db_connection() as db:
            await db.execute("SELECT clear_enabled FROM discord_features_settings WHERE id = 1")
            row = await db.fetchone()
        if row and not row["clear_enabled"]:
            await interaction.response.send_message("❌ Cette commande est désactivée depuis le panneau d'administration.", ephemeral=True)
            return
        if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Cette commande ne fonctionne que dans un salon textuel.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=nombre)
        except discord.Forbidden:
            await interaction.followup.send("❌ Permissions insuffisantes pour supprimer des messages ici.", ephemeral=True)
            return
        except Exception as e:
            logger.error(f"❌ [CLEAR] Échec purge salon {interaction.channel.id} : {e}")
            await interaction.followup.send(f"❌ Erreur lors de la suppression : {e}", ephemeral=True)
            return

        await interaction.followup.send(f"🧹 {len(deleted)} message(s) supprimé(s).", ephemeral=True)
        await self._log_to_discord_channel(
            str(member), "Clear",
            f"{len(deleted)} message(s) supprimé(s) dans #{interaction.channel.name} par {member.display_name}"
        )

    async def _handle_poll_slash(self, interaction: discord.Interaction, question: str, options: list[str]):
        member = interaction.user
        if not isinstance(member, discord.Member) or not self._is_mod_or_owner(member):
            await interaction.response.send_message("❌ Seuls les modérateurs peuvent créer un sondage.", ephemeral=True)
            return
        async with get_db_connection() as db:
            await db.execute("SELECT sondage_enabled FROM discord_features_settings WHERE id = 1")
            row = await db.fetchone()
        if row and not row["sondage_enabled"]:
            await interaction.response.send_message("❌ Cette commande est désactivée depuis le panneau d'administration.", ephemeral=True)
            return
        if len(options) < 2:
            await interaction.response.send_message("❌ Il faut au moins 2 options pour un sondage.", ephemeral=True)
            return

        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        lines = [f"**📊 {question}**\n"]
        for i, opt in enumerate(options):
            lines.append(f"{number_emojis[i]} {opt}")
        embed = discord.Embed(description="\n".join(lines), color=discord.Color(0x00F5C3))
        embed.set_footer(text=f"Sondage lancé par {interaction.user.display_name}")
        embed.timestamp = datetime.now(timezone.utc)

        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(options)):
            try:
                await msg.add_reaction(number_emojis[i])
            except Exception as e:
                logger.error(f"❌ [SONDAGE] Échec ajout réaction {number_emojis[i]} : {e}")

    async def _feature_enabled(self, column: str) -> bool:
        async with get_db_connection() as db:
            await db.execute(f"SELECT {column} FROM discord_features_settings WHERE id = 1")
            row = await db.fetchone()
        return bool(row[column]) if row else True

    async def _handle_warn_slash(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        moderator = interaction.user
        if not isinstance(moderator, discord.Member) or not self._is_mod_or_owner(moderator):
            await interaction.response.send_message("❌ Tu n'as pas la permission d'avertir un membre.", ephemeral=True)
            return
        if not await self._feature_enabled("warn_enabled"):
            await interaction.response.send_message("❌ Cette commande est désactivée depuis le panneau d'administration.", ephemeral=True)
            return

        async with get_db_connection() as db:
            await db.execute(
                "INSERT INTO discord_warnings (discord_user_id, username, reason, moderator) VALUES (?, ?, ?, ?)",
                str(membre.id), membre.display_name, raison, moderator.display_name
            )
            await db.execute("SELECT COUNT(*) AS total FROM discord_warnings WHERE discord_user_id = ?", str(membre.id))
            row = await db.fetchone()
        total = row["total"] if row else 1

        await interaction.response.send_message(
            f"⚠️ {membre.mention} a été averti ({total} avertissement(s) au total).\nRaison : {raison}"
        )
        try:
            await membre.send(f"⚠️ Tu as reçu un avertissement sur **{interaction.guild.name}**.\nRaison : {raison}")
        except discord.Forbidden:
            pass
        await self._log_to_discord_channel(
            membre.display_name, "Avertissement",
            f"Averti par {moderator.display_name} — Raison : {raison} (total : {total})"
        )

    async def _handle_slowmode_slash(self, interaction: discord.Interaction, secondes: int):
        member = interaction.user
        if not isinstance(member, discord.Member) or not self._is_mod_or_owner(member):
            await interaction.response.send_message("❌ Tu n'as pas la permission de gérer ce salon.", ephemeral=True)
            return
        if not await self._feature_enabled("slowmode_enabled"):
            await interaction.response.send_message("❌ Cette commande est désactivée depuis le panneau d'administration.", ephemeral=True)
            return
        if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("❌ Cette commande ne fonctionne que dans un salon textuel.", ephemeral=True)
            return

        try:
            await interaction.channel.edit(slowmode_delay=secondes)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Permissions insuffisantes sur ce salon.", ephemeral=True)
            return

        if secondes == 0:
            await interaction.response.send_message("✅ Mode lent désactivé sur ce salon.")
        else:
            await interaction.response.send_message(f"🐌 Mode lent activé : un message toutes les {secondes}s.")

    async def _handle_lock_slash(self, interaction: discord.Interaction, locked: bool):
        member = interaction.user
        if not isinstance(member, discord.Member) or not self._is_mod_or_owner(member):
            await interaction.response.send_message("❌ Tu n'as pas la permission de gérer ce salon.", ephemeral=True)
            return
        if not await self._feature_enabled("lock_enabled"):
            await interaction.response.send_message("❌ Cette commande est désactivée depuis le panneau d'administration.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ Cette commande ne fonctionne que dans un salon textuel.", ephemeral=True)
            return

        everyone = interaction.guild.default_role
        try:
            await interaction.channel.set_permissions(
                everyone, send_messages=(False if locked else None),
                reason=f"/{'lock' if locked else 'unlock'} par {member.display_name}"
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ Permissions insuffisantes sur ce salon.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Salon verrouillé." if locked else "🔓 Salon déverrouillé.")

    async def _handle_userinfo_slash(self, interaction: discord.Interaction, membre: discord.Member):
        if not isinstance(interaction.user, discord.Member) or not self._is_mod_or_owner(interaction.user):
            await interaction.response.send_message("❌ Réservé aux modérateurs.", ephemeral=True)
            return
        if not await self._feature_enabled("userinfo_enabled"):
            await interaction.response.send_message("❌ Cette commande est désactivée depuis le panneau d'administration.", ephemeral=True)
            return

        async with get_db_connection() as db:
            await db.execute("SELECT COUNT(*) AS total FROM discord_warnings WHERE discord_user_id = ?", str(membre.id))
            warn_row = await db.fetchone()
            await db.execute("SELECT day, month, year FROM discord_birthdays WHERE discord_user_id = ?", str(membre.id))
            bday_row = await db.fetchone()

        roles = [r.mention for r in membre.roles if r.name != "@everyone"]
        embed = discord.Embed(title=f"👤 {membre.display_name}", color=discord.Color(0x00F5C3))
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name="Pseudo", value=str(membre), inline=True)
        embed.add_field(name="ID", value=str(membre.id), inline=True)
        embed.add_field(name="Arrivé le", value=membre.joined_at.strftime("%d/%m/%Y") if membre.joined_at else "Inconnu", inline=True)
        embed.add_field(name="Compte créé le", value=membre.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Avertissements", value=str(warn_row["total"] if warn_row else 0), inline=True)
        if bday_row:
            bday_str = f"{bday_row['day']:02d}/{bday_row['month']:02d}" + (f"/{bday_row['year']}" if bday_row['year'] else "")
            embed.add_field(name="Anniversaire", value=bday_str, inline=True)
        embed.add_field(name=f"Rôles ({len(roles)})", value=", ".join(roles) if roles else "Aucun", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_giveaway_slash(self, interaction: discord.Interaction, prix: str, duree_minutes: int):
        member = interaction.user
        if not isinstance(member, discord.Member) or not self._is_mod_or_owner(member):
            await interaction.response.send_message("❌ Réservé aux modérateurs.", ephemeral=True)
            return
        if not await self._feature_enabled("giveaway_enabled"):
            await interaction.response.send_message("❌ Cette commande est désactivée depuis le panneau d'administration.", ephemeral=True)
            return

        end_at = datetime.now(timezone.utc) + timedelta(minutes=duree_minutes)
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Lot : {prix}**\n\nRéagis avec 🎉 pour participer !\nFin : <t:{int(end_at.timestamp())}:R>",
            color=discord.Color(0x00F5C3),
        )
        embed.set_footer(text=f"Lancé par {member.display_name}")

        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await msg.add_reaction("🎉")

        self.active_giveaways[msg.id] = {"prize": prix, "end_at": end_at, "channel_id": msg.channel.id}
        asyncio.create_task(self._end_giveaway_later(msg.id, duree_minutes * 60))

    async def _end_giveaway_later(self, message_id: int, delay_seconds: int):
        await asyncio.sleep(delay_seconds)
        info = self.active_giveaways.pop(message_id, None)
        if not info:
            return
        try:
            channel = self.get_channel(info["channel_id"]) or await self.fetch_channel(info["channel_id"])
            msg = await channel.fetch_message(message_id)
            reaction = discord.utils.get(msg.reactions, emoji="🎉")
            participants = []
            if reaction:
                async for user in reaction.users():
                    if not user.bot:
                        participants.append(user)

            if not participants:
                await channel.send(f"🎉 Giveaway terminé pour **{info['prize']}** — personne n'a participé.")
                return

            import random
            winner = random.choice(participants)
            await channel.send(f"🎉 Félicitations {winner.mention} ! Tu remportes **{info['prize']}** !")
        except Exception as e:
            logger.error(f"❌ [GIVEAWAY] Échec de la clôture du giveaway {message_id} : {e}")

    async def _handle_annonce_slash(self, interaction: discord.Interaction, salon: discord.TextChannel, titre: str, message: str):
        member = interaction.user
        if not isinstance(member, discord.Member) or not self._is_mod_or_owner(member):
            await interaction.response.send_message("❌ Réservé aux modérateurs.", ephemeral=True)
            return
        if not await self._feature_enabled("annonce_enabled"):
            await interaction.response.send_message("❌ Cette commande est désactivée depuis le panneau d'administration.", ephemeral=True)
            return

        embed = discord.Embed(title=titre, description=message, color=discord.Color(0x00F5C3))
        embed.set_footer(text=f"Annonce par {member.display_name}")
        embed.timestamp = datetime.now(timezone.utc)

        try:
            await salon.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Permissions insuffisantes dans ce salon.", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ Annonce postée dans {salon.mention}.", ephemeral=True)

    async def on_member_remove(self, member: discord.Member):
        try:
            async with get_db_connection() as db:
                await db.execute("SELECT leave_enabled, leave_channel_id FROM discord_features_settings WHERE id = 1")
                row = await db.fetchone()
            if not row or not row["leave_enabled"] or not row["leave_channel_id"]:
                return

            channel = self.get_channel(int(row["leave_channel_id"])) or await self.fetch_channel(int(row["leave_channel_id"]))
            joined = member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "inconnue"
            await channel.send(
                f"📤 **{member.display_name}** (`{member.name}`) a quitté le serveur.\n"
                f"↳ Membre depuis le {joined}"
            )
        except Exception as e:
            logger.error(f"❌ [DISCORD MOD] Erreur annonce départ pour {member}: {e}")

    async def publish_rules_message(self, channel_id: str, rules_text: str, emoji: str) -> str:
        """Poste (ou republie) le message de règlement et y ajoute la réaction. Retourne l'ID du message."""
        channel = self.get_channel(int(channel_id)) or await self.fetch_channel(int(channel_id))
        msg = await channel.send(rules_text)
        await msg.add_reaction(emoji)
        return str(msg.id)

    async def publish_self_roles_panel(self, channel_id: str) -> str:
        """(Re)génère le panneau de rôles auto-attribuables dans le salon donné, avec une réaction par rôle."""
        async with get_db_connection() as db:
            await db.execute("SELECT * FROM discord_self_roles WHERE channel_id = ? ORDER BY id ASC", channel_id)
            roles = await db.fetchall()

        if not roles:
            raise ValueError("Aucun rôle configuré pour ce salon.")

        lines = ["**🎭 Choisis tes rôles en cliquant sur les réactions ci-dessous !**\n"]
        for r in roles:
            label = r["label"] or r["role_name"]
            lines.append(f"{r['emoji']} — {label}")
        text = "\n".join(lines)

        channel = self.get_channel(int(channel_id)) or await self.fetch_channel(int(channel_id))
        msg = await channel.send(text)
        for r in roles:
            try:
                await msg.add_reaction(r["emoji"])
            except Exception as e:
                logger.error(f"❌ [SELF-ROLES] Échec ajout réaction {r['emoji']} : {e}")

        async with get_db_connection() as db:
            await db.execute("UPDATE discord_self_roles SET message_id = ? WHERE channel_id = ?", str(msg.id), channel_id)

        return str(msg.id)

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if isinstance(message.author, discord.Member):
            if message.author.guild_permissions.manage_messages:
                return  # modérateurs/admins jamais modérés
            if await self._is_exempt_role(message.author):
                return

        try:
            await self._moderate(message)
        except Exception as e:
            logger.error(f"❌ [DISCORD MOD] Erreur lors de l'analyse du message : {e}")

    async def _is_exempt_role(self, member: discord.Member) -> bool:
        if not member.roles:
            return False
        member_role_ids = {str(r.id) for r in member.roles}
        async with get_db_connection() as db:
            await db.execute("SELECT role_id FROM discord_exempt_roles")
            rows = await db.fetchall()
        exempt_ids = {r["role_id"] for r in rows}
        return bool(member_role_ids & exempt_ids)

    async def _moderate(self, message: discord.Message):
        async with get_db_connection() as db:
            await db.execute("SELECT * FROM discord_moderation_settings WHERE id = 1")
            mod_settings = await db.fetchone()
            await db.execute("SELECT word FROM discord_banned_words")
            banned_rows = await db.fetchall()

        if not mod_settings:
            return
        mod_settings = dict(mod_settings)
        text_lower = message.content.lower()

        if mod_settings.get("banned_words_enabled"):
            banned_words = [r["word"].lower() for r in banned_rows]
            for word in banned_words:
                if word and re.search(rf"\b{re.escape(word)}\b", text_lower):
                    await self._sanction(
                        message,
                        mod_settings["banned_words_action"],
                        mod_settings["banned_words_duration"],
                        f"Mot interdit ({word})",
                    )
                    return

        if mod_settings.get("spam_enabled"):
            spam_messages = await self._check_spam(message, mod_settings["spam_limit"], mod_settings["spam_timeframe"])
            if spam_messages:
                await self._sanction(
                    message,
                    mod_settings["spam_action"],
                    mod_settings["spam_duration"],
                    f"Spam ({mod_settings['spam_limit']} messages en {mod_settings['spam_timeframe']}s)",
                    extra_messages=spam_messages,
                )
                return

    async def _check_spam(self, message: discord.Message, limit: int, timeframe: int) -> list[discord.Message]:
        """Retourne la liste des messages de la rafale (à supprimer) si le seuil est dépassé, sinon []."""
        now = time.time()
        uid = message.author.id
        history = [(m, t) for m, t in self.recent_messages[uid] if now - t < timeframe]
        history.append((message, now))
        self.recent_messages[uid] = history
        if len(history) > limit:
            return [m for m, _ in history]
        return []

    async def _sanction(self, message: discord.Message, action: str, duration: int, reason: str, extra_messages: list[discord.Message] | None = None):
        if action not in ("delete", "timeout", "ban"):
            return

        username = message.author.display_name
        await self._log_to_dashboard(username, "sanction_discord", f"{action} : {reason}")

        # En cas de rafale (spam), on supprime TOUS les messages de la rafale, pas juste celui
        # qui a déclenché le seuil — sinon les messages précédents restent affichés.
        messages_to_delete = extra_messages if extra_messages else [message]
        try:
            for msg in messages_to_delete:
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass  # déjà supprimé entre-temps, pas grave

            if action == "timeout" and isinstance(message.author, discord.Member):
                until = datetime.now(timezone.utc) + timedelta(seconds=duration or 600)
                await message.author.timeout(until, reason=reason)
            elif action == "ban" and isinstance(message.author, discord.Member):
                await message.author.ban(reason=reason, delete_message_seconds=0)
            logger.info(f"🛡️ [DISCORD MOD] {action} appliqué à {username} ({reason}) — {len(messages_to_delete)} message(s) supprimé(s)")
        except discord.Forbidden:
            logger.error(f"❌ [DISCORD MOD] Permissions insuffisantes pour sanctionner {username} (rôle du bot trop bas ?)")
        except Exception as e:
            logger.error(f"❌ [DISCORD MOD] Erreur lors de la sanction de {username} : {e}")

        if message.author.id in self.recent_messages:
            del self.recent_messages[message.author.id]

        await self._log_to_discord_channel(username, action, reason)

    async def _log_to_discord_channel(self, username: str, action: str, reason: str):
        channel_id = settings.MODERATION_LOG_CHANNEL_ID
        if not channel_id:
            return
        try:
            channel = self.get_channel(int(channel_id)) or await self.fetch_channel(int(channel_id))
            action_label = {"delete": "Suppression", "timeout": "Timeout", "ban": "Bannissement"}.get(action, action)
            await channel.send(
                f"{PLATFORM_EMOJI['Discord']} **[DISCORD]** `{action_label}` — **{username}**\n"
                f"↳ Raison : {reason}"
            )
        except Exception as e:
            logger.error(f"❌ [DISCORD MOD] Échec envoi log salon modération : {e}")

    async def _log_to_dashboard(self, username: str, event_type: str, reason: str):
        try:
            async with get_db_connection() as conn:
                details = {"reason": reason, "bot": "Félix (Discord)"}
                await conn.execute(
                    "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES ($1, $2, $3, NOW())",
                    (event_type, username, str(details))
                )
        except Exception as e:
            logger.error(f"❌ [DISCORD MOD] Erreur écriture log dashboard : {e}")


discord_mod_bot = DiscordModBot(intents=intents)


async def start_discord_mod_bot():
    token = settings.DISCORD_TOKEN
    if not token:
        logger.warning("⚠️ [DISCORD MOD] DISCORD_TOKEN manquant dans .env, modération Discord désactivée.")
        return
    try:
        await discord_mod_bot.start(token)
    except discord.PrivilegedIntentsRequired:
        logger.error(
            "❌ [DISCORD MOD] Intents privilégiés non activés sur le Developer Portal Discord "
            "(MESSAGE CONTENT + SERVER MEMBERS). Modération Discord désactivée."
        )
    except Exception as e:
        logger.error(f"❌ [DISCORD MOD] Échec du démarrage du bot de modération Discord : {e}")


async def check_birthdays_today():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_birthday_settings WHERE id = 1")
        bday_settings = await db.fetchone()
        if not bday_settings or not bday_settings["enabled"] or not bday_settings["channel_id"]:
            return

        today = date.today()
        await db.execute(
            "SELECT * FROM discord_birthdays WHERE day = ? AND month = ? "
            "AND (last_announced_year IS NULL OR last_announced_year != ?)",
            today.day, today.month, today.year
        )
        birthdays = await db.fetchall()

        if not birthdays:
            return

        if not discord_mod_bot.is_ready():
            return

        try:
            channel = discord_mod_bot.get_channel(int(bday_settings["channel_id"])) or await discord_mod_bot.fetch_channel(int(bday_settings["channel_id"]))
        except Exception as e:
            logger.error(f"❌ [BIRTHDAY] Salon d'annonce introuvable : {e}")
            return

        for b in birthdays:
            try:
                mention = f"<@{b['discord_user_id']}>"
                msg = bday_settings["message_template"].replace("{member}", mention)
                if b["year"]:
                    age = today.year - b["year"]
                    msg += f" ({age} ans)"
                await channel.send(msg)
                await db.execute(
                    "UPDATE discord_birthdays SET last_announced_year = ? WHERE id = ?",
                    today.year, b["id"]
                )
                logger.info(f"🎂 [BIRTHDAY] Anniversaire annoncé pour {b['username']}")
            except Exception as e:
                logger.error(f"❌ [BIRTHDAY] Échec annonce pour {b['username']} : {e}")


async def birthday_check_routine():
    logger.info("🎂 [BIRTHDAY] Démarrage de la surveillance des anniversaires Discord.")
    while True:
        try:
            await check_birthdays_today()
        except Exception as e:
            logger.error(f"❌ [BIRTHDAY] Erreur dans la boucle de vérification : {e}")
        await asyncio.sleep(6 * 60 * 60)  # vérifie toutes les 6h (suffisant pour ne jamais rater un jour)
