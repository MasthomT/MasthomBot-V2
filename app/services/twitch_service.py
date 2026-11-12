import re
import random
import socket as _socket
import time
import aiohttp
import json
import logging
import asyncio
from twitchio.ext import commands

from app.core.config import settings
from app.repositories import viewer_repo
from app.services.notification_service import notification_service
from app.services.moderation_service import moderation_service
from app.services.credits_service import credits_service
from app.services.obs_service import obs_service
from app.routes.overlays import trigger_overlay_event
from app.core.database import init_db, get_db_connection
from app.core import settings_cache
from app.services.twitch_common import safe_send, _birthday_wished
from app.services.twitch_commands import ChatCommandsMixin
from app.services.twitch_timers import TimersMixin

logger = logging.getLogger("masthbot.twitch")


class MasthbotTwitch(ChatCommandsMixin, TimersMixin, commands.Bot):
    def __init__(self):
        raw_bot_token = settings.TWITCH_BOT_OAUTH_TOKEN
        clean_bot_token = raw_bot_token if raw_bot_token.startswith('oauth:') else f'oauth:{raw_bot_token}'
        
        self.master_token = settings.TWITCH_OAUTH_TOKEN.replace('oauth:', '').strip()
        self.broadcaster_id = None
        self.channel_name = settings.TWITCH_CHANNEL.replace("#", "").lower()
        self.notified_lives = set()
        self.known_levels = {}
        self.role_checked_users = set()

        self.web_session = None
        self.is_ready_flag = False

        super().__init__(
            token=clean_bot_token,
            prefix='!',
            initial_channels=[settings.TWITCH_CHANNEL]
        )

    async def get_web_session(self):
        if self.web_session is None or self.web_session.closed:
            self.web_session = aiohttp.ClientSession()
        return self.web_session

    async def close(self):
        if self.web_session and not self.web_session.closed:
            await self.web_session.close()
        await super().close()

    async def get_db_config(self):
        try:
            if True:  # (bloc conservé pour garder l'indentation du dict ci-dessous)
                p = await settings_cache.get_personality()
                s = await settings_cache.get_settings()

                return {
                    'system_prompt': p.get('system_prompt', "Tu es Félix."),
                    'base_context': p.get('base_context', "Chat de Masthom."),
                    'intervention_rate': p.get('intervention_rate', 20),
                    'roast_level': p.get('roast_level', 10),
                    'ai_enabled': s.get('ai_enabled', 1),
                    'enable_twitch': s.get('enable_twitch', 1),
                    'discord_link': s.get('discord_link', ""),
                    'youtube_link': s.get('youtube_link', ""),
                    'planning': s.get('planning', ""),
                    'response_length': s.get('response_length', 150),
                    'discord_notify_enabled': s.get('discord_notify_enabled', 0),
                    'notif_live_channel_id': s.get('notif_live_channel_id', ""),
                    'streamers_channel_id': s.get('streamers_channel_id', ""),
                    'discord_notify_message': s.get('discord_notify_message', ""),
                    'exp_per_message': s.get('exp_per_message', 2),
                    'exp_per_watchtime': s.get('exp_per_watchtime', 5),
                    'personal_last_live_id': s.get('personal_last_live_id', "")
                }
        except Exception as e:
            logger.error(f"❌ [DB FATAL] Impossible de lire la configuration (get_db_config) : {e}")
            return {}

    async def log_event(self, event_type, username, details_dict):
        try:
            async with get_db_connection() as conn:
                await conn.execute(
                    "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES ($1, $2, $3, NOW())",
                    (event_type, username, json.dumps(details_dict))
                )
        except Exception as e:
            logger.error(f"❌ [LOG ERROR] : {e}")

    async def event_command_error(self, ctx, error):
        from twitchio.ext.commands.errors import CommandNotFound
        if isinstance(error, CommandNotFound):
            pass  # Géré par le router custom
        else:
            logger.error(f"🔥 [CMD ERROR] : {error}")

    async def _enable_irc_keepalive(self):
        """Active les TCP keepalives sur la socket IRC pour détecter les coupures silencieuses.
        L'OS envoie des sondes toutes les 10s après 30s d'inactivité ; 3 échecs = fermeture
        immédiate → twitchio détecte l'erreur et reconnecte automatiquement."""
        try:
            ws = getattr(self._connection, '_websocket', None)
            if ws is None:
                return
            transport = ws._writer.transport
            sock = transport.get_extra_info('socket')
            if sock is None:
                return
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_KEEPALIVE, 1)
            sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_KEEPIDLE, 30)
            sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_KEEPINTVL, 10)
            sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_KEEPCNT, 3)
            logger.info("✅ [IRC] TCP keepalives activés (idle=30s, interval=10s, count=3)")
        except Exception as e:
            logger.warning(f"⚠️ [IRC] TCP keepalives indisponibles : {e}")

    async def event_ready(self):
        print(f"✅ [TWITCH] Connecté en tant que : {self.nick}")
        self.is_ready_flag = True
        self._last_irc_at = time.time()
        await self._enable_irc_keepalive()

        try:
            await init_db()
        except Exception as e:
            print(f"❌ [DB INIT ERROR] Erreur critique lors de l'initialisation : {e}")

        try:
            users = await self.fetch_users(names=[self.channel_name])
            if users:
                self.broadcaster_id = users[0].id
                print(f"🆔 [HELIX] ID Broadcaster : {self.broadcaster_id}")

            if not hasattr(self, "_watchtime_started"):
                print("⏱️ [ROUTINE] Lancement du compteur de présence...")
                self.watchtime_timer.start()
                self._watchtime_started = True

            if not hasattr(self, "_announcements_started"):
                print("📢 [ROUTINE] Lancement de la file d'attente des annonces...")
                self.announcements_timer.start()
                self._announcements_started = True

            if not hasattr(self, "_sync_roles_started"):
                print("🤖 [ROUTINE] Lancement de l'Aspirateur Twitch (Modos/VIPs)...")
                self.sync_roles_timer.start()
                self._sync_roles_started = True

            if not hasattr(self, "_mod_guard_started"):
                print("🛡️ [ROUTINE] Lancement de la protection des modérateurs...")
                self.mod_guard_timer.start()
                self._mod_guard_started = True

            if not hasattr(self, "_sync_subs_started"):
                print("⭐ [ROUTINE] Lancement du compteur d'abonnés...")
                self.sync_subs_timer.start()
                self._sync_subs_started = True

            if not hasattr(self, "_sync_viewers_started"):
                print("👁️ [ROUTINE] Lancement du compteur de viewers...")
                self.sync_viewers_timer.start()
                self._sync_viewers_started = True

            if not hasattr(self, "_watchdog_started"):
                print("🛡️ [ROUTINE] Lancement du Watchdog (Superviseur des routines)...")
                self.watchdog_timer.start()
                self._watchdog_started = True

            if not hasattr(self, "_followers_detector_started"):
                print("💙 [ROUTINE] Lancement du détecteur de Followers (Temps Réel)...")
                self.followers_detector_timer.start()
                self._followers_detector_started = True

            if not hasattr(self, "_special_announcements_started"):
                print("🎉 [ROUTINE] Lancement des annonces Début de Stream / Une seule fois...")
                self.special_announcements_timer.start()
                self._special_announcements_started = True

        except Exception as e:
            print(f"❌ [READY ERROR] : {e}")

    async def event_stream_online(self, channel):
        config = await self.get_db_config()
        if not config.get('discord_notify_enabled'):
            return
        
        channel_id = config.get('notif_live_channel_id')
        if not channel_id:
            return

        await asyncio.sleep(10) 
        streams = await self.fetch_streams(user_logins=[self.channel_name])
        if streams:
            s = streams[0]
            await notification_service.send_discord_live_notification(
                channel_id=channel_id,
                channel_name=self.channel_name,
                title=s.title,
                game=s.game_name,
                custom_message=config.get('discord_notify_message')
            )

    async def event_message(self, message):
        if message.echo or not message.author:
            return
        self._last_irc_at = time.time()

        content = message.content
        content_clean = content.strip()
        content_lower = content_clean.lower()

        await viewer_repo.ensure_viewer(str(message.author.id), message.author.name)
        username = message.author.name.lower()
        display_name = message.author.display_name or message.author.name
        config = await self.get_db_config()

        # Votes du chat : !poll N (sondage Twitch). Le nom, l'activation, le rôle
        # et un éventuel message de confirmation se règlent dans l'admin (page Commandes).
        if content_lower.startswith("!"):
            from app.services.bot_system_commands_service import get_config_by_name, msg as _vote_msg
            vote_hit = await get_config_by_name(content_lower.split(" ", 1)[0][1:])
            if vote_hit and vote_hit[0] == "poll":
                vote_key, vote_cfg = vote_hit
                try:
                    parts = content_clean.split(" ")
                    if len(parts) > 1 and 1 <= int(parts[1]) <= 4:
                        choice_idx = int(parts[1])
                        if not await self._syscmd_allowed(message, vote_key, vote_cfg):
                            return
                        await self._handle_twitch_poll_vote(message, choice_idx)
                        confirm = await _vote_msg(vote_key, "confirm", user=display_name, choice=choice_idx)
                        if confirm:
                            await safe_send(message.channel, confirm)
                        return
                except (ValueError, IndexError):
                    pass

        badges = message.author.badges or {}
        is_owner = username == self.channel_name
        is_mod = message.author.is_mod or ("moderator" in badges) or is_owner
        is_vip = message.author.is_vip or ("vip" in badges)
        is_artist = ("artist-badge" in badges) or ("artist" in badges)
        is_live = bool(config.get('personal_last_live_id', ""))

        # --- DÉBUT DE LA MODIFICATION ---
        # 🛡️ Sécurité : on s'assure que le cache existe bien (au cas où il manquerait dans l'init)
        if not hasattr(self, 'role_cache'):
            self.role_cache = {}

        # 🔄 SYNCHRONISATION INTELLIGENTE (Détecte les changements instantanément)
        current_roles = (is_vip, is_mod, is_artist)
        cached_roles = self.role_cache.get(str(message.author.id))

        if cached_roles != current_roles:
            await self.sync_user_roles(str(message.author.id), is_vip, is_mod, is_artist)
            self.role_cache[str(message.author.id)] = current_roles
        # --- FIN DE LA MODIFICATION ---

        if is_live:
            credits_service.add_watchtime(display_name, 0)
            if is_mod:
                credits_service.log_event("moderators", display_name)
            elif is_vip:
                credits_service.log_event("vips", display_name)
            else:
                credits_service.log_event("chatters", display_name)

        if not is_mod:
            reward_id = message.tags.get('custom-reward-id') if message.tags else None
            violation = await moderation_service.process_message(
                message_id=message.id,
                message=message.content,
                username=message.author.name,
                user_id=message.author.id,
                broadcaster_id=self.broadcaster_id,
                client_id=self._http.client_id,
                token=self.master_token,
                is_vip=is_vip,
                reward_id=reward_id
            )
            if violation:
                return 

        try:
            exp_msg = int(config.get('exp_per_message', 2) or 2)
        except (ValueError, TypeError):
            exp_msg = 2

        if not is_live:
            exp_msg = 0

        await viewer_repo.update_viewer_stats(
            username=username,
            messages_add=1,
            points_add=exp_msg,
            twitch_id=str(message.author.id)
        )

        emotes_tag = message.tags.get('emotes')
        if emotes_tag:
            emote_urls = []
            for emote_data in emotes_tag.split('/'):
                try:
                    emote_id, positions = emote_data.split(':')
                    count = len(positions.split(','))
                    url = f"https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/default/dark/3.0"
                    emote_urls.extend([url] * count)
                except ValueError:
                    continue
            
            if emote_urls:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "type": "emote_rain",
                        "details": { "urls": emote_urls }
                    }
                    try:
                        await session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload)
                    except Exception as e:
                        logger.error(f"Erreur Envoi Emotes OBS : {e}")

        if config.get('ai_enabled') and config.get('enable_twitch'):
            viewer_dict = {}
            try:
                async with get_db_connection() as conn:
                    c = await conn.execute("SELECT * FROM viewers WHERE LOWER(username) = $1", (username.lower(),))
                    row = await c.fetchone()
                    if row:
                        viewer_dict = dict(row)
            except Exception as e:
                logger.error(f"❌ Erreur chargement contexte viewer {username} : {e}")

            triggers = ["félix", "felix", f"@{self.nick.lower()}"]
            custom_bot_name = viewer_dict.get('nickname_for_bot')
            if custom_bot_name and custom_bot_name.strip():
                triggers.append(custom_bot_name.lower().strip())

            content_lower = message.content.lower().replace("mastho2felix", "")
            
            is_mentioned = False
            for t in triggers:
                if t.startswith('@'):
                    if t in content_lower:
                        is_mentioned = True
                        break
                else:
                    if re.search(rf'\b{re.escape(t)}\b', content_lower):
                        is_mentioned = True
                        break
            
            # --- 🎂 DÉTECTION ANNIVERSAIRE (une seule fois par session) ---
            from app.services.ai_service import ai_service, is_birthday_today
            force_birthday = False
            if is_birthday_today(viewer_dict.get('birthday', '')) and username.lower() not in _birthday_wished:
                _birthday_wished.add(username.lower())
                force_birthday = True
                logger.info(f"🎂 Anniversaire détecté pour {username} — Félix va le souhaiter !")

            if force_birthday or is_mentioned or random.randint(1, 100) <= int(config.get('intervention_rate', 20)):
                try:
                    points = viewer_dict.get('points', 0)
                    viewer_level = max(1, int((points / 100) ** (1 / 2.2))) if points > 0 else 1

                    screenshot_base64 = await asyncio.to_thread(obs_service.take_screenshot)

                    msg_for_felix = message.content
                    if force_birthday:
                        msg_for_felix = (
                            f"[SYSTÈME ANNIVERSAIRE : C'EST L'ANNIVERSAIRE DE {username} AUJOURD'HUI ! "
                            f"Tu DOIS absolument lui souhaiter un joyeux anniversaire de manière mémorable et personnalisée, "
                            f"inviter tout le chat à le fêter avec lui, et leur rappeler d'utiliser la commande !anniversaire !] "
                            f"{message.content}"
                        )

                    reply = await ai_service.get_felix_response(
                        username=username,
                        viewer_data=viewer_dict,
                        viewer_level=viewer_level,
                        message_content=msg_for_felix,
                        is_admin=is_mod,
                        roast_level=int(config.get('roast_level', 10)),
                        discord_link=config.get('discord_link'),
                        youtube_link=config.get('youtube_link'),
                        planning=config.get('planning'),
                        system_prompt=config.get('system_prompt'),
                        base_context=config.get('base_context'),
                        response_length=int(config.get('response_length', 150)),
                        image_base64=screenshot_base64
                    )

                    if reply:
                        await self._handle_helix_actions(reply, is_admin=is_mod)
                        final_text = re.sub(r"\[.*?\]", "", reply).strip()
                        if final_text:
                            await safe_send(message.channel, final_text)
                except Exception as e:
                    logger.error(f"🔥 [AI ERROR] : {e}")

        # ⚠️ Les bits (cheers) sont désormais gérés EXCLUSIVEMENT par EventSub
        # (channel.cheer → "Nom | X bits"). On ne les traite plus ici pour éviter le
        # double comptage et l'écrasement du label par le seul nom sans le nombre.

        if message.content.startswith('!'):
            parts = message.content.split(' ', 1)
            cmd_name = parts[0][1:].lower()
            user_input = parts[1].strip() if len(parts) > 1 else ""

            # ── Résolution du nom personnalisé des commandes système ──────────
            # Si le viewer tape !shoutout et que l'admin a renommé 'so' → 'shoutout',
            # on réécrit le contenu du message vers le nom interne ('so') pour que
            # twitchio retrouve le bon handler enregistré par @commands.command.
            from app.services.bot_system_commands_service import get_config_by_name
            syscmd = await get_config_by_name(cmd_name)
            if syscmd:
                internal_key, syscmd_cfg = syscmd
                # Activation ET rôle minimum réglés dans l'admin : appliqués ici, à un seul endroit, pour
                # toutes les commandes système (avant, le rôle du sélecteur n'était lu par aucune commande).
                if not await self._syscmd_allowed(message, internal_key, syscmd_cfg):
                    from app.services.bot_system_commands_service import definition_of, msg as _dmsg
                    if syscmd_cfg.get("enabled", True) and "denied" in (definition_of(internal_key) or {}).get("messages", {}):
                        await safe_send(message.channel, await _dmsg(internal_key, "denied"))
                    return
                if internal_key != cmd_name:
                    # Réécriture vers le nom interne
                    new_content = f"!{internal_key}" + (f" {user_input}" if user_input else "")
                    message._content = new_content
                    cmd_name = internal_key

            # Commandes natives twitchio — ne pas intercepter par le routeur custom
            NATIVE_COMMANDS = {
                'so', 'checkcopains', 'testpoll',
                'level', 'rang', 'timer', 'chrono', 'voteclips', 'addvip', 'vip',
                'permit', 'unpermit', 'play', 'screamer', 'renotif',
                'de', 'uptime', 'counter',
            }
            if cmd_name in NATIVE_COMMANDS:
                await self.handle_commands(message)
                return

            # --- 1. SYSTÈME DE TRADUCTION ---
            from app.services.features_service import handle_translation, LANGUAGES
            if cmd_name in LANGUAGES:
                from app.services.bot_system_commands_service import get_config as _get_syscfg
                if not await self._syscmd_allowed(message, "translate", await _get_syscfg("translate")):
                    return
                reply = await handle_translation(cmd_name, display_name, user_input)
                return await safe_send(message.channel, reply)
            if cmd_name == "translate":          # le nom « traduire » affiche l'aide
                from app.services.bot_system_commands_service import msg as _tmsg
                sample = next(iter(LANGUAGES))
                return await safe_send(message.channel, await _tmsg(
                    "translate", "help", commands=" ".join(f"!{c}" for c in LANGUAGES), example=sample))

            # --- 2. JEU DU MOT SECRET ---
            from app.services.features_service import handle_set_word, handle_guess_word
            if cmd_name == "setword":
                reply = await handle_set_word(display_name, user_input)
                return await message.channel.send(reply)

            if cmd_name == "guess":              # (l'alias « mot » est ramené à « guess » plus haut)
                reply = await handle_guess_word(display_name, user_input)
                if reply: # On n'envoie un message que si c'est la bonne réponse !
                    return await message.channel.send(reply)

            if cmd_name == "game":
                from app.services.features_service import handle_game_info
                import os
                
                # Si l'utilisateur a tapé "!game Cyberpunk 2077", on cherche ce jeu.
                # Sinon, on interroge Twitch pour voir à quoi tu joues en ce moment.
                target_game = user_input
                if not target_game:
                    streams = await self.fetch_streams(user_logins=[self.channel_name])
                    if streams and streams[0].game_name:
                        target_game = streams[0].game_name
                
                if target_game:
                    # On réutilise les identifiants Twitch du bot pour IGDB
                    client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
                    reply = await handle_game_info(target_game, client_id, self.master_token)
                    return await safe_send(message.channel, reply)
                else:
                    from app.services.bot_system_commands_service import msg as _gmsg
                    return await safe_send(message.channel, await _gmsg("game", "no_game"))

            # --- 3. COMMANDES PERSONNALISÉES (Base de données) ---
            from app.services.command_service import handle_custom_command
            result = await handle_custom_command(
                command_name=cmd_name,
                username=username,
                viewer_data=viewer_dict,
                user_input=user_input,
                is_mod=is_mod,
                is_sub=bool(message.tags and message.tags.get('subscriber') == '1'),
                is_vip=is_vip,
                is_admin=is_owner,
                caller_twitch_id=str(message.author.id),
            )
            if result and result.get("content"):
                await safe_send(message.channel, result["content"])

            # --- 4. COMMANDES DÉDIÉES DES ROUES (modos + streameur uniquement) ---
            if not (result and result.get("content")) and (is_mod or is_owner):
                try:
                    from app.services.wheel_service import get_all_wheels
                    from app.services.eventsub_service import _spin_wheel_by_name
                    wheels = await get_all_wheels()
                    matched_wheel = next(
                        (w for w in wheels if w.get("twitch_command") and w["twitch_command"].lower() == cmd_name),
                        None
                    )
                    if matched_wheel:
                        asyncio.create_task(_spin_wheel_by_name(matched_wheel["name"]))
                except Exception as _e:
                    logger.error(f"❌ [WHEEL CMD] Erreur roue commande '!{cmd_name}' : {_e}")

        await self.handle_commands(message)

    async def sync_user_roles(self, twitch_id: str, is_vip: bool, is_mod: bool, is_artist: bool):
        """Met à jour instantanément les rôles d'un utilisateur en base de données."""
        try:
            async with get_db_connection() as conn:
                await conn.execute("""
                    UPDATE viewers 
                    SET is_vip = $1, is_mod = $2, is_artist = $3 
                    WHERE twitch_id = $4
                """, (int(is_vip), int(is_mod), int(is_artist), str(twitch_id)))
                
                # On l'ajoute au cache pour éviter que le chat re-vérifie juste après
                self.role_checked_users.add(str(twitch_id))
                logger.debug(f"🔄 [API SYNC] Rôles synchronisés pour le Twitch ID {twitch_id}")
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Erreur lors de sync_user_roles : {e}")

    def _role_flags(self, message) -> dict:
        """Rôles de l'auteur du message (broadcaster > modo > VIP > abonné), pour le contrôle des commandes."""
        badges = message.author.badges or {}
        name = message.author.name.lower()
        is_owner = name == self.channel_name or name == "felixthebigblackcat"   # le bot agit avec les droits du streamer
        return {
            "is_owner": is_owner,
            "is_mod": bool(message.author.is_mod or "moderator" in badges or is_owner),
            "is_vip": bool(message.author.is_vip or "vip" in badges),
            "is_sub": bool((message.tags and message.tags.get("subscriber") == "1") or "subscriber" in badges or "founder" in badges),
        }

    async def _syscmd_allowed(self, message, key: str, cfg: dict | None) -> bool:
        """La commande système est-elle activée, et l'auteur a-t-il le rôle minimum réglé dans l'admin ?"""
        from app.services.bot_system_commands_service import enforces_role, role_allowed
        if cfg is not None and not cfg.get("enabled", True):
            return False
        # Récompense de points de chaîne « TikTok Replay » : un viewer peut déclencher le lecteur sans être modo.
        if key == "play" and message.tags and message.tags.get("custom-reward-id") == "093cceb1-3c5e-4e8e-bc16-7f27ff6a2d2b":
            return True
        if cfg is None or not enforces_role(key):
            return True
        return role_allowed(cfg["min_role"], **self._role_flags(message))

    async def _handle_helix_actions(self, reply, is_admin=False):
        if not is_admin:
            return

        b_id = self.broadcaster_id
        if not b_id:
            return
        
        master_headers = {
            "Client-ID": self._http.client_id,
            "Authorization": f"Bearer {self.master_token}"
        }

        try:
            async with aiohttp.ClientSession() as session:
                poll_match = re.search(r"\[POLL:(.+?)\|(.+?)\|(\d+)\]", reply)
                if poll_match:
                    p_payload = {
                        "broadcaster_id": b_id,
                        "title": poll_match.group(1),
                        "choices": [{"title": c.strip()[:25]} for c in poll_match.group(2).split(',')],
                        "duration": int(poll_match.group(3))
                    }
                    await session.post('https://api.twitch.tv/helix/polls', headers=master_headers, json=p_payload)

                predict_match = re.search(r"\[PREDICT:(.+?)\|(.+?)\|(\d+)\]", reply)
                if predict_match:
                    pr_payload = {
                        "broadcaster_id": b_id,
                        "title": predict_match.group(1),
                        "outcomes": [{"title": o.strip()[:25]} for o in predict_match.group(2).split(',')],
                        "prediction_window": int(predict_match.group(3))
                    }
                    await session.post('https://api.twitch.tv/helix/predictions', headers=master_headers, json=pr_payload)

                if "[ACTION:CLEAR]" in reply:
                    await session.delete(f"https://api.twitch.tv/helix/moderation/chat?broadcaster_id={b_id}&moderator_id={b_id}", headers=master_headers)

                if "[ACTION:EMOTE_ONLY_ON]" in reply or "[ACTION:EMOTE_ONLY_OFF]" in reply:
                    is_on = "[ACTION:EMOTE_ONLY_ON]" in reply
                    await session.patch(f"https://api.twitch.tv/helix/chat/settings?broadcaster_id={b_id}&moderator_id={b_id}", headers=master_headers, json={"emote_mode": is_on})

                if "[ACTION:SUB_ONLY_ON]" in reply or "[ACTION:SUB_ONLY_OFF]" in reply:
                    is_on = "[ACTION:SUB_ONLY_ON]" in reply
                    await session.patch(f"https://api.twitch.tv/helix/chat/settings?broadcaster_id={b_id}&moderator_id={b_id}", headers=master_headers, json={"subscriber_mode": is_on})

                if "[ACTION:FOLLOW_ONLY_ON]" in reply or "[ACTION:FOLLOW_ONLY_OFF]" in reply:
                    is_on = "[ACTION:FOLLOW_ONLY_ON]" in reply
                    await session.patch(f"https://api.twitch.tv/helix/chat/settings?broadcaster_id={b_id}&moderator_id={b_id}", headers=master_headers, json={"follower_mode": is_on})

        except Exception as e:
            logger.error(f"❌ [HELIX ACTION ERROR] : {e}")

    async def _handle_twitch_poll_vote(self, message, choice_idx):
        """Gère les votes du chat (!poll 1, 2...) pour l'overlay Twitch."""
        try:
            import app.services.twitch_poll_state as poll_state
            
            if choice_idx in poll_state.chat_votes:
                poll_state.chat_votes[choice_idx] += 1
                await trigger_overlay_event({
                    "type": "update_twitch_poll",
                    "payload": poll_state.chat_votes
                })
        except Exception as e:
            logger.error(f"Erreur lors du vote Twitch (!poll) : {e}")

    async def event_poll_begin(self, data):
        try:
            await trigger_overlay_event({"type": "show_twitch_poll"})
        except Exception as e:
            logger.error(f"Erreur lors du signal de sondage Twitch : {e}")

    async def event_prediction_begin(self, data):
        try:
            await trigger_overlay_event({"type": "show_twitch_prediction"})
        except Exception as e:
            logger.error(f"Erreur lors du signal de prédiction Twitch : {e}")

    async def event_raw_usernotice(self, channel, tags: dict):
        """Capte les événements officiels Twitch dans le chat (Subs, Raids, etc.).

        ⚠️ Subs / resubs / sub-gifts / raids sont désormais gérés EXCLUSIVEMENT par
        EventSub (voir eventsub_service.py). On ne fait plus rien ici pour ces events
        afin d'éviter le double comptage (double XP, double entrée générique) et
        l'incohérence du label 'dernier sub' (deux écriveurs aux formats différents).
        """
        return


twitch_bot = MasthbotTwitch()
