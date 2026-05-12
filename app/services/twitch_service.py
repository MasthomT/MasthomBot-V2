import re
import random
import sqlite3
import os
import aiohttp
import json
import logging
import asyncio
from datetime import datetime, timedelta
from twitchio.ext import commands, routines

from app.core.config import settings
from app.repositories import viewer_repo
from app.services.shoutout_service import shoutout_service
from app.services.notification_service import notification_service
from app.services.moderation_service import moderation_service
from app.services.credits_service import credits_service
from app.services.obs_service import obs_service
from app.routes.overlays import trigger_overlay_event
from app.core.database import init_db, get_db_connection

logger = logging.getLogger("masthbot.twitch")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

class MasthbotTwitch(commands.Bot):
    def __init__(self):
        raw_bot_token = settings.TWITCH_BOT_OAUTH_TOKEN
        clean_bot_token = raw_bot_token if raw_bot_token.startswith('oauth:') else f'oauth:{raw_bot_token}'
        
        self.master_token = settings.TWITCH_OAUTH_TOKEN.replace('oauth:', '').strip()
        self.broadcaster_id = None
        self.channel_name = settings.TWITCH_CHANNEL.replace("#", "").lower()
        self.notified_lives = set()
        self.known_levels = {}
        self.role_checked_users = set() # AJOUT : Mémoire pour éviter de spammer la base de données

        self.web_session = None

        super().__init__(
            token=clean_bot_token,
            prefix='!',
            initial_channels=[settings.TWITCH_CHANNEL]
        )

    async def get_web_session(self):
        """Crée ou retourne la session HTTP persistante du bot."""
        if self.web_session is None or self.web_session.closed:
            self.web_session = aiohttp.ClientSession()
        return self.web_session

    async def close(self):
        """S'assure de fermer proprement la session réseau quand le bot s'éteint."""
        if self.web_session and not self.web_session.closed:
            await self.web_session.close()
        await super().close()

    async def get_db_config(self):
        """Récupère la configuration en utilisant le gestionnaire asynchrone centralisé."""
        try:
            async with get_db_connection() as conn:
                # Avec aiosqlite, on doit await l'exécution ET le fetch
                p_cursor = await conn.execute("SELECT * FROM personality LIMIT 1")
                p_row = await p_cursor.fetchone()
                
                s_cursor = await conn.execute("SELECT * FROM settings LIMIT 1")
                s_row = await s_cursor.fetchone()

                p = dict(p_row) if p_row else {}
                s = dict(s_row) if s_row else {}

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
            # 🔥 POINT 5 DU P0 : On logge l'erreur proprement au lieu de la cacher
            logger.error(f"❌ [DB FATAL] Impossible de lire la configuration (get_db_config) : {e}")
            return {}

    def log_event(self, event_type, username, details_dict):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=20.0)
            conn.execute(
                "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (event_type, username, json.dumps(details_dict))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ [LOG ERROR] : {e}")

    async def event_ready(self):
        print(f"✅ [TWITCH] Connecté en tant que : {self.nick}")
        
        # 1. 🔥 INITIALISATION SÉCURISÉE DE LA BASE DE DONNÉES
        try:
            await init_db()
        except Exception as e:
            print(f"❌ [DB INIT ERROR] Erreur critique lors de l'initialisation : {e}")

        # 2. DÉMARRAGE HABITUEL DU BOT ET DES ROUTINES
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

        # === BLOC CONSERVÉ SELON TES INSTRUCTIONS ===
        content = message.content
        content_clean = content.strip()  # On nettoie d'abord
        content_lower = content_clean.lower() # On transforme ensuite

        await viewer_repo.ensure_viewer(str(message.author.id), message.author.name)
        username = message.author.name.lower()
        display_name = message.author.display_name or message.author.name
        config = await self.get_db_config()
        # ============================================

        # --- GESTION DU SYSTÈME FEL-X (VERCEL) ---
        # Commande OBLIGATOIRE : !choix
        if content_lower.startswith("!choix "):
            try:
                parts = content_clean.split(" ")
                if len(parts) > 1:
                    choice_idx = int(parts[1])
                    if 1 <= choice_idx <= 4:
                        await self._handle_chat_vote(message, choice_idx)
                        return
            except (ValueError, IndexError):
                pass

        # --- GESTION DU SYSTÈME TWITCH ---
        # Commande OBLIGATOIRE : !poll
        elif content_lower.startswith("!poll "):
            try:
                parts = content_clean.split(" ")
                if len(parts) > 1:
                    choice_idx = int(parts[1])
                    if 1 <= choice_idx <= 4:
                        # On appelle la fonction dédiée pour Twitch
                        await self._handle_twitch_poll_vote(message, choice_idx)
                        return
            except (ValueError, IndexError):
                pass

        badges = message.author.badges or {}
        is_owner = username == self.channel_name
        is_mod = message.author.is_mod or ("moderator" in badges) or is_owner
        is_vip = message.author.is_vip or ("vip" in badges)
        
        # ⚠️ LE FIX EST ICI : Twitch appelle ce badge 'artist-badge' dans son API, pas 'artist' !
        is_artist = ("artist-badge" in badges) or ("artist" in badges)
        is_live = bool(config.get('personal_last_live_id', ""))

        if (is_vip or is_mod or is_artist) and str(message.author.id) not in self.role_checked_users:
            try:
                # 🔥 On utilise notre super gestionnaire asynchrone !
                async with get_db_connection() as conn:
                    if is_vip:
                        await conn.execute("UPDATE viewers SET is_vip = 1 WHERE twitch_id = ?", (str(message.author.id),))
                    if is_mod:
                        await conn.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = ?", (str(message.author.id),))
                    if is_artist:
                        await conn.execute("UPDATE viewers SET is_artist = 1 WHERE twitch_id = ?", (str(message.author.id),))
                    
                    await conn.commit()
                    self.role_checked_users.add(str(message.author.id))
            except Exception as e:
                # Remplacement du silence par un log structuré (Point 5 du P0)
                logger.error(f"❌ [DB ERROR] Erreur d'enregistrement auto des badges : {e}")

        if is_live:
            credits_service.add_watchtime(display_name, 0)
            if is_mod:
                credits_service.log_event("moderators", display_name)
            elif is_vip:
                credits_service.log_event("vips", display_name)
            else:
                credits_service.log_event("chatters", display_name)

        if not is_mod:
            violation = await moderation_service.process_message(
                message_id=message.id,
                message=message.content,
                username=message.author.name,
                user_id=message.author.id,
                broadcaster_id=self.broadcaster_id,
                client_id=self._http.client_id,
                token=self.master_token,
                is_vip=is_vip
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
            points_add=exp_msg
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
                        await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
                    except Exception as e:
                        logger.error(f"Erreur Envoi Emotes OBS : {e}")

        if config.get('ai_enabled') and config.get('enable_twitch'):
            viewer = await viewer_repo.get_viewer_by_name(username)
            viewer_dict = dict(viewer) if viewer else {}

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
            
            if is_mentioned or random.randint(1, 100) <= int(config.get('intervention_rate', 20)):
                try:
                    from app.services.ai_service import ai_service
                    
                    points = viewer_dict.get('points', 0)
                    viewer_level = max(1, int((points / 100) ** (1 / 2.2))) if points > 0 else 1

                    screenshot_base64 = await asyncio.to_thread(obs_service.take_screenshot)

                    reply = await ai_service.get_felix_response(
                        username=username,
                        viewer_data=viewer_dict,
                        viewer_level=viewer_level,
                        message_content=message.content,
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
                            await message.channel.send(final_text)
                except Exception as e:
                    logger.error(f"🔥 [AI ERROR] : {e}")

        await self.handle_commands(message)

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

    async def _handle_chat_vote(self, message, choice_idx):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            # On récupère le sondage actif
            active_poll = conn.execute("SELECT id, option1, option2, option3, option4 FROM polls WHERE is_active=1 ORDER BY id DESC LIMIT 1").fetchone()

            if not active_poll:
                return # Aucun sondage Fel-X actif, on ignore silencieusement

            # 🛡️ PROTECTION : On ne vote par chat QUE pour les sondages Fel-X
            # Si tu as une colonne 'type' dans ta table polls, on l'utilise.
            # Sinon, on considère que si le bot a trouvé un sondage actif ici, c'est un Fel-X.
            
            opt_key = f"option{choice_idx}"
            if not active_poll[opt_key]:
                return # Choix invalide pour ce sondage

            # Enregistrement du vote pour Vercel/Local
            conn.execute("""
                INSERT INTO poll_votes (poll_id, twitch_id, option_index)
                VALUES (?, ?, ?)
                ON CONFLICT(poll_id, twitch_id) DO UPDATE SET option_index = excluded.option_index
            """, (active_poll['id'], str(message.author.id), choice_idx))
            conn.commit()

            # Mise à jour visuelle immédiate
            await trigger_overlay_event({"type": "show_poll"})

        except Exception as e:
            logger.error(f"Erreur vote chat: {e}")
        finally:
            conn.close()

    async def event_poll_begin(self, data):
        """Se déclenche automatiquement quand un sondage commence sur Twitch."""
        try:
            from app.routes.overlays import trigger_overlay_event
            # On envoie le signal spécifique au bandeau Twitch
            await trigger_overlay_event({"type": "show_twitch_poll"})
        except Exception as e:
            logger.error(f"Erreur lors du signal de sondage Twitch : {e}")

    async def event_prediction_begin(self, data):
        """Se déclenche automatiquement quand une prédiction commence sur Twitch."""
        try:
            from app.routes.overlays import trigger_overlay_event
            # On envoie un signal spécifique pour les prédictions
            await trigger_overlay_event({"type": "show_twitch_prediction"})
        except Exception as e:
            logger.error(f"Erreur lors du signal de prédiction Twitch : {e}")

    @commands.command(name='so')
    async def shoutout_command(self, ctx, *, content: str = None):
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or ctx.author.name.lower() == "felixthebigblackcat"):
            return
        if not content:
            return await ctx.send("Miaou ! Pseudo ou lien requis : !so pseudo")

        # Nettoyage de l'input
        input_val = content.replace("!so", "").strip().split()[0].split("?")[0]
        target_name = None
        slug_for_node = None

        client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}

        # 🔥 NOUVEAU : On allume le moteur réseau une seule fois pour tout le processus
        session = await self.get_web_session()

        # 1. DÉCODAGE DU LIEN OU DU PSEUDO
        if "twitch.tv" in input_val:
            if "clips.twitch.tv" in input_val:
                slug_for_node = input_val.split("clips.twitch.tv/")[-1].strip("/")
                try:
                    async with session.get(f"https://api.twitch.tv/helix/clips?id={slug_for_node}", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"):
                                target_name = data["data"][0]["broadcaster_name"]
                except: pass

            elif "/clip/" in input_val:
                parts = input_val.split("twitch.tv/")[-1].strip("/").split("/")
                target_name = parts[0]
                slug_for_node = parts[2] if len(parts) >= 3 else None

            elif "/videos/" in input_val:
                video_id = input_val.split("/videos/")[-1].strip("/")
                try:
                    async with session.get(f"https://api.twitch.tv/helix/videos?id={video_id}", headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"):
                                target_name = data["data"][0]["user_name"]
                except: pass
            else:
                target_name = input_val.split("twitch.tv/")[-1].strip("/")
        else:
            target_name = input_val.replace("@", "")

        if not target_name:
            return await ctx.send("❌ Impossible de récupérer le pseudo depuis ce lien ! Vérifie ton URL.")

        # 2. ENVOI DES MESSAGES ET DÉCLENCHEMENT DE L'OVERLAY
        target_name_clean = target_name.lower()
        
        # Message Twitch
        try:
            async with session.get(f"https://api.twitch.tv/helix/users?login={target_name_clean}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data"):
                        s_id = data["data"][0]["id"]
                        s_display = data["data"][0]["display_name"]
                        async with session.get(f"https://api.twitch.tv/helix/channels?broadcaster_id={s_id}", headers=headers) as c_resp:
                            last_game = "un jeu inconnu"
                            if c_resp.status == 200:
                                c_data = await c_resp.json()
                                if c_data.get("data") and c_data["data"][0].get("game_name"):
                                    last_game = c_data["data"][0]["game_name"]
                            
                            await ctx.send(f"🎬 Allez donner de la force à @{s_display} qui jouait récemment à {last_game} ! https://twitch.tv/{target_name_clean} 💜")
                    else:
                        await ctx.send(f"Foncez voir @{target_name} ! https://twitch.tv/{target_name_clean}")
        except:
            pass

        # Envoi du signal à l'overlay Node.js (OBS)
        try:
            async with session.post("http://127.0.0.1:3005/api/shoutout", json={"target": target_name_clean, "slug": slug_for_node}) as _:
                pass
        except Exception as e:
            logger.error(f"Erreur Envoi SO Node : {e}")

    @commands.command(name='replay')
    async def cmd_replay(self, ctx, *, content: str = None):
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or ctx.author.name.lower() == 'felixthebigblackcat'):
            return

        slug, query = None, None
        if content:
            content = content.strip()
            if "twitch.tv" in content:
                slug = content
            else:
                query = content

        # 🔥 NOUVEAU : On récupère notre moteur réseau
        session = await self.get_web_session()
        
        try:
            payload = {"slug": slug, "query": query}
            # Envoi instantané via la session globale
            async with session.post("http://127.0.0.1:3005/api/replay", json=payload) as _:
                pass
        except Exception as e:
            print(f"❌ [REPLAY ERROR] : {e}")

    @commands.command(name='renotif')
    async def cmd_renotif(self, ctx):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster:
            return
        config = await self.get_db_config()
        channel_id = config.get('notif_live_channel_id')
        if not channel_id:
            return await ctx.send("❌ Aucun salon Discord n'est configuré.")

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
            await ctx.send(f"✅ Notification renvoyée sur Discord avec la catégorie : {s.game_name} !")
        else:
            await ctx.send("⏳ Twitch ne te voit pas en live. Attends 1 minute et réessaie !")

    @commands.command(name='checkcopains')
    async def cmd_checkcopains(self, ctx):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster:
            return
            
        config = await self.get_db_config()
        channel_id = config.get('streamers_channel_id')
        if not channel_id:
            return await ctx.send("❌ Aucun salon Discord configuré.")

        # 🔥 Nouvelle méthode asynchrone
        try:
            async with get_db_connection() as conn:
                cursor = await conn.execute("SELECT * FROM tracked_streamers WHERE is_active=1")
                tracked = await cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Impossible de lire les copains : {e}")
            return

        if not tracked:
            return await ctx.send("⚠️ Aucun partenaire surveillé.")

        logins = [s["login"] for s in tracked]
        await ctx.send(f"🔍 Scan des {len(logins)} copains...")

        streams = await self.fetch_streams(user_logins=logins)
        if not streams:
            return await ctx.send("💤 Aucun copain n'est en ligne.")

        notified_count = 0
        for s in streams:
            partner_msg = f"**{s.user.name}** est en live sur **{{CATEGORIE}}**, foncez lui donner de la force !"
            await notification_service.send_discord_live_notification(
                channel_id=channel_id,
                channel_name=s.user.name,
                title=s.title,
                game=s.game_name,
                custom_message=partner_msg
            )
            notified_count += 1

        await ctx.send(f"✅ {notified_count} alertes envoyées !")

    @commands.command(name='sondage')
    async def cmd_sondage(self, ctx):
        # 🔥 Nouvelle méthode asynchrone
        try:
            async with get_db_connection() as conn:
                # 1. On récupère le sondage Fel-X actif
                cursor = await conn.execute("SELECT * FROM polls WHERE is_active=1 ORDER BY id DESC LIMIT 1")
                poll = await cursor.fetchone()

                if not poll:
                    return await ctx.send("🐾 Aucun sondage en cours. Crée-en un sur ton interface admin !")

                # 2. Calcul des votes actuels pour le chat
                cursor_votes = await conn.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id=? GROUP BY option_index", (poll['id'],))
                votes = await cursor_votes.fetchall()
                
                results = {1: 0, 2: 0, 3: 0, 4: 0}
                total = 0
                for v in votes:
                    results[v['option_index']] = v['count']
                    total += v['count']

            # 3. On envoie le signal "show_poll" au port 8000
            await trigger_overlay_event({"type": "show_poll"})

            # 4. Préparation du message pour le chat Twitch
            msg = f"📊 SONDAGE : {poll['question']} — "
            options_text = []

            for i in range(1, 5):
                opt_name = poll[f'option{i}']
                if opt_name:
                    count = results[i]
                    pct = round((count / total) * 100) if total > 0 else 0
                    options_text.append(f"{i}. {opt_name} ({pct}%)")

            msg += " | ".join(options_text)
            msg += f" — 🗳️ Vote avec 1, 2, 3... ({total} votes)"

            await ctx.send(msg)

        except Exception as e:
            logger.error(f"❌ [DB ERROR] Erreur cmd_sondage : {e}")

    @commands.command(name='testpoll')
    async def cmd_testpoll(self, ctx):
        """Commande de débogage pour forcer l'affichage de l'overlay Twitch"""
        if not ctx.author.is_mod and not ctx.author.is_broadcaster:
            return

        try:
            # 1. On importe notre mémoire
            import app.services.twitch_poll_state as poll_state
            
            # 2. On injecte un faux sondage dans la mémoire
            poll_state.chat_votes = {1: 0, 2: 0, 3: 0, 4: 0}
            poll_state.current_twitch_poll = {
                "title": "Ceci est un test de Félix !",
                "total_votes": 10,
                "is_prediction": False,
                "choices": [
                    {"title": "Choix A", "votes": 5},
                    {"title": "Choix B", "votes": 5}
                ]
            }

            # 3. On envoie le signal à l'overlay
            from app.routes.overlays import trigger_overlay_event
            await trigger_overlay_event({
                "type": "show_twitch_poll",
                "payload": poll_state.current_twitch_poll
            })
            
            await ctx.send("🛠️ Faux sondage de test envoyé à l'overlay !")
            
        except Exception as e:
            print(f"❌ Erreur testpoll : {e}")

    @commands.command(name='level')
    async def cmd_level(self, ctx):
        username = ctx.author.name.lower()
        conn = sqlite3.connect(DB_PATH, timeout=20.0)
        row = conn.execute("SELECT points FROM viewers WHERE LOWER(username) = ?", (username,)).fetchone()
        conn.close()
        
        points = row[0] if row else 0
        if points <= 0:
            return await ctx.send(f"@{ctx.author.name}, tu es Niveau 1 avec 0 EXP ! Parle dans le chat pour progresser. 🐾")
            
        level = max(1, int((points / 100) ** (1 / 2.2)))
        next_lvl_xp = int(100 * ((level + 1) ** 2.2))
        
        await ctx.send(f"@{ctx.author.name}, tu es Niveau {level} avec {points} EXP ! (Prochain niveau à {next_lvl_xp} EXP) 🌟")

    @commands.command(name='rang')
    async def cmd_rang(self, ctx):
        username = ctx.author.name.lower()
        conn = sqlite3.connect(DB_PATH, timeout=20.0)
        conn.row_factory = sqlite3.Row
        viewers = conn.execute("SELECT username, points FROM viewers WHERE points > 0 ORDER BY points DESC, watchtime DESC").fetchall()
        conn.close()
        
        if not viewers:
            return await ctx.send(f"@{ctx.author.name}, le classement est vide pour le moment !")
            
        user_idx = -1
        for i, v in enumerate(viewers):
            if v["username"].lower() == username:
                user_idx = i
                break
                
        if user_idx == -1:
            return await ctx.send(f"@{ctx.author.name}, tu n'as pas encore d'EXP pour être classé ! 🐾")
            
        rank = user_idx + 1
        start_idx = max(0, user_idx - 2)
        end_idx = min(len(viewers), user_idx + 3)
        
        leaderboard_snippet = []
        for i in range(start_idx, end_idx):
            pos = i + 1
            v_name = viewers[i]["username"]
            v_pts = viewers[i]["points"]
            
            if i == user_idx:
                leaderboard_snippet.append(f"👉 #{pos} {v_name} ({v_pts} pts)")
            else:
                leaderboard_snippet.append(f"#{pos} {v_name} ({v_pts} pts)")
                
        msg = " | ".join(leaderboard_snippet)
        await ctx.send(f"🏆 Classement (Rang #{rank}) : {msg}")

    @commands.command(name='timer')
    async def cmd_timer(self, ctx, time_str: str = None, *, label: str = "OBJECTIF"):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster: return
        if not time_str: return await ctx.send("⏱️ Usage : !timer <minutes> [Nom du timer] (ex: !timer 5 Pause café)")

        # 🔥 NOUVEAU : On récupère notre moteur réseau unique
        session = await self.get_web_session()

        if time_str.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            try:
                # Utilisation du moteur pour envoyer l'ordre à OBS
                async with session.post("http://127.0.0.1:3005/api/trigger", json=payload) as _:
                    pass
                await ctx.send("🛑 Timer effacé de l'écran !")
            except Exception as e:
                logger.error(f"Erreur Stop Timer OBS : {e}")
            return

        try:
            minutes = int(time_str)
            duration_seconds = minutes * 60
        except ValueError:
            return await ctx.send("❌ La durée doit être un chiffre exact en minutes (ex: !timer 5)")

        payload = {
            "type": "time_event",
            "details": { "action": "start", "mode": "timer", "duration": duration_seconds, "label": label.upper() }
        }
        try:
            # Utilisation du moteur pour envoyer l'ordre à OBS
            async with session.post("http://127.0.0.1:3005/api/trigger", json=payload) as _:
                pass
            await ctx.send(f"⏱️ Timer de {minutes} minute(s) lancé à l'écran : {label.upper()}")
        except Exception as e:
            logger.error(f"Erreur Envoi Timer OBS : {e}")

    @commands.command(name='chrono')
    async def cmd_chrono(self, ctx, *, label: str = "CHRONO"):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster: return
        
        # 🔥 NOUVEAU : On récupère notre moteur réseau unique
        session = await self.get_web_session()

        if label and label.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            try:
                # Utilisation du moteur pour envoyer l'ordre à OBS
                async with session.post("http://127.0.0.1:3005/api/trigger", json=payload) as _:
                    pass
                await ctx.send("🛑 Chrono effacé de l'écran !")
            except Exception as e:
                logger.error(f"Erreur Stop Chrono OBS : {e}")
            return

        payload = {
            "type": "time_event",
            "details": { "action": "start", "mode": "chrono", "duration": 0, "label": label.upper() }
        }
        try:
            # Utilisation du moteur pour envoyer l'ordre à OBS
            async with session.post("http://127.0.0.1:3005/api/trigger", json=payload) as _:
                pass
            await ctx.send(f"⏱️ Chronomètre lancé à l'écran : {label.upper()}")
        except Exception as e:
            logger.error(f"Erreur Envoi Chrono OBS : {e}")

    @commands.command(name='addvip')
    async def cmd_addvip(self, ctx, target: str = None, duration_days: int = 0):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster:
            return

        if not target:
            return await ctx.send("❌ Usage: !addvip <pseudo> <jours> (Ex: !addvip Masthom_ 7) Mettre 0 pour Permanent.")

        target_clean = target.lower().replace("@", "")

        try:
            async with get_db_connection() as conn:
                cursor = await conn.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = ?", (target_clean,))
                viewer = await cursor.fetchone()

                if not viewer:
                    return await ctx.send(f"❌ Le viewer @{target} n'existe pas dans la base de données. Il doit parler au moins une fois.")

                expiry = None
                if duration_days > 0:
                    expiry = (datetime.now() + timedelta(days=duration_days)).isoformat()

                await conn.execute("UPDATE viewers SET is_vip = 1, vip_expiry = ? WHERE LOWER(username) = ?", (expiry, target_clean))
                await conn.commit()
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Erreur API Twitch !addvip (Base de données) : {e}")
            return

        # 🔥 NOUVEAU : Appel à l'API Twitch via notre moteur réseau unique
        try:
            headers = {"Client-ID": self._http.client_id, "Authorization": f"Bearer {self.master_token}"}
            url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&user_id={viewer['twitch_id']}"
            
            session = await self.get_web_session()
            async with session.post(url, headers=headers) as _:
                pass
        except Exception as e:
            logger.error(f"Erreur API Twitch !addvip (Réseau) : {e}")

        if duration_days > 0:
            await ctx.send(f"💎 L'élite s'agrandit ! @{target} est désormais VIP pour {duration_days} jours !")
        else:
            await ctx.send(f"⭐ Consécration ! @{target} est désormais VIP à vie !")

    @commands.command(name='vip')
    async def cmd_vip(self, ctx):
        # 🔥 Nouvelle méthode asynchrone
        try:
            async with get_db_connection() as conn:
                cursor = await conn.execute("SELECT is_vip, vip_expiry FROM viewers WHERE twitch_id = ?", (str(ctx.author.id),))
                user = await cursor.fetchone()
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Erreur cmd_vip : {e}")
            return

        if not user or not user['is_vip']:
            return await ctx.send(f"@{ctx.author.name}, tu n'es pas VIP ! 😿")

        if not user['vip_expiry']:
            return await ctx.send(f"⭐ @{ctx.author.name}, ton grade VIP est Permanent ! Merci pour ton soutien éternel 💜")

        try:
            expiry = datetime.fromisoformat(user['vip_expiry'])
            now = datetime.now()

            if expiry < now:
                return await ctx.send(f"🥀 @{ctx.author.name}, ton grade VIP a expiré le {expiry.strftime('%d/%m/%Y')}.")

            diff = expiry - now
            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            time_str = ""
            if days > 0: time_str += f"{days} jours et "
            if hours > 0: time_str += f"{hours}h"
            if minutes > 0 and days == 0: time_str += f"{minutes}m"

            if not time_str: time_str = "quelques secondes"

            await ctx.send(f"💎 @{ctx.author.name}, il te reste {time_str} de VIP ! (Expire le {expiry.strftime('%d/%m/%Y à %H:%M')})")
        except:
            await ctx.send(f"@{ctx.author.name}, ton grade VIP est bien actif ! 💎")

    @routines.routine(seconds=60)
    async def watchtime_timer(self):
        """Distribue l'EXP et le watchtime de façon sécurisée et groupée."""
        if not self.broadcaster_id: 
            return

        config = await self.get_db_config()
        if not config.get('personal_last_live_id'):
            return

        exp_to_give = int(config.get('exp_per_watchtime', 5))
        
        try:
            api_success = False
            # 🔥 NOUVEAU : On utilise notre session réseau unique
            session = await self.get_web_session()
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
            url = f"https://api.twitch.tv/helix/chat/chatters?broadcaster_id={self.broadcaster_id}&moderator_id={self.broadcaster_id}"
            
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    chatters = data.get('data', [])
                    
                    async with get_db_connection() as conn:
                        count = 0
                        for c in chatters:
                            u_name = c['user_name'].lower()
                            t_id = c['user_id']
                            
                            if u_name in [self.nick.lower(), 'nightbot', 'streamelements', 'wizebot']:
                                continue

                            try:
                                await conn.execute(
                                    "INSERT OR IGNORE INTO viewers (twitch_id, username) VALUES (?, ?)",
                                    (t_id, u_name)
                                )
                                await conn.execute(
                                    "UPDATE viewers SET watchtime = watchtime + 60, points = points + ? WHERE twitch_id = ?",
                                    (exp_to_give, t_id)
                                )
                                credits_service.add_watchtime(c['user_name'], 1)
                                count += 1
                            except Exception as e:
                                logger.warning(f"⚠️ Erreur isolée pour {u_name}: {e}")
                        
                        await conn.commit() 
                        if count > 0:
                            logger.info(f"💎 Watchtime distribué à {count} personnes.")
                    api_success = True
                    
                elif resp.status in [401, 403]:
                    logger.error(f"❌ BLOCAGE TWITCH ({resp.status}) : Permissions insuffisantes.")

            if not api_success:
                channel = self.get_channel(self.channel_name)
                if channel and hasattr(channel, 'chatters'):
                    async with get_db_connection() as conn:
                        count_fb = 0
                        for chatter in channel.chatters:
                            u_name = chatter.name.lower()
                            if u_name in [self.nick.lower(), 'nightbot', 'streamelements', 'wizebot']: continue
                            
                            await conn.execute(
                                "UPDATE viewers SET watchtime = watchtime + 60, points = points + ? WHERE LOWER(username) = ?",
                                (exp_to_give, u_name)
                            )
                            credits_service.add_watchtime(chatter.name, 1)
                            count_fb += 1
                        
                        await conn.commit()
                        if count_fb > 0:
                            logger.info(f"⚠️ Watchtime (Secours) distribué à {count_fb} personnes.")

        except Exception as e:
            logger.error(f"❌ [DB FATAL] Erreur critique routine Watchtime : {e}")

    @routines.routine(minutes=1)
    async def vip_expiration_timer(self):
        """Vérifie et supprime les grades VIP expirés de façon sécurisée (DB + Twitch)."""
        try:
            if not getattr(self, 'broadcaster_id', None):
                users = await self.fetch_users(names=[self.channel_name])
                if users:
                    self.broadcaster_id = users[0].id
                else:
                    return

            now = datetime.now()
            expired_vips = []

            async with get_db_connection() as conn:
                cursor = await conn.execute("""
                    SELECT twitch_id, username, vip_expiry FROM viewers
                    WHERE is_vip = 1 AND vip_expiry IS NOT NULL
                """)
                vips_to_check = await cursor.fetchall()

                for v in vips_to_check:
                    twitch_id = v['twitch_id'] if hasattr(v, 'keys') else v[0]
                    username = v['username'] if hasattr(v, 'keys') else v[1]
                    vip_expiry = v['vip_expiry'] if hasattr(v, 'keys') else v[2]

                    try:
                        expiry_str = str(vip_expiry).replace("T", " ")
                        if len(expiry_str) == 16:
                            expiry_str += ":00"
                        expiry_dt = datetime.strptime(expiry_str[:19], '%Y-%m-%d %H:%M:%S')

                        if expiry_dt <= now:
                            expired_vips.append({"twitch_id": twitch_id, "username": username})
                    except Exception as e:
                        logger.error(f"❌ Erreur lecture date pour {username} : {e}")

                if expired_vips:
                    # --- PRÉPARATION DU MOTEUR RÉSEAU POUR TWITCH ---
                    headers = {"Client-ID": self._http.client_id, "Authorization": f"Bearer {self.master_token}"}
                    session = await self.get_web_session()

                    for v in expired_vips:
                        # 1. On l'enlève de la base de données
                        await conn.execute(
                            "UPDATE viewers SET is_vip = 0, vip_expiry = NULL WHERE twitch_id = ?",
                            (str(v['twitch_id']),)
                        )
                        
                        # 2. 🚀 ON L'ENLÈVE EN DIRECT SUR TWITCH !
                        try:
                            url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&user_id={v['twitch_id']}"
                            async with session.delete(url, headers=headers) as resp:
                                if resp.status in (200, 204):
                                    logger.info(f"✅ VIP Temporaire expiré et retiré sur Twitch pour {v['username']}")
                                else:
                                    logger.error(f"⚠️ Impossible de retirer le VIP de {v['username']} sur Twitch (Erreur {resp.status})")
                        except Exception as e:
                            logger.error(f"❌ Erreur réseau API Twitch pour expiration {v['username']} : {e}")

                    await conn.commit()
                    logger.info(f"💾 [DB & TWITCH] Grades de {len(expired_vips)} viewers expirés et retirés avec succès.")
                        
        except Exception as e:
            logger.error(f"💥 CRASH DANS LA ROUTINE VIP : {e}", exc_info=True)

    # =====================================================================
    # 🤖 ASPIRATEUR AUTOMATIQUE DES MODOS ET VIPs DEPUIS TWITCH
    # =====================================================================
    @routines.routine(hours=1)
    async def sync_roles_timer(self):
        """Aspirateur Automatique de Rôles Twitch (Tourne toutes les heures en fond)"""
        if not self.broadcaster_id: return
        
        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
            
            # 🔥 NOUVEAU : On allume le moteur réseau pour toute la routine
            session = await self.get_web_session()
            
            # 1. Aspirer les Modérateurs
            mods = []
            cursor = ""
            while True:
                url = f"https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={self.broadcaster_id}&first=100"
                if cursor: url += f"&after={cursor}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    mods.extend(data.get("data", []))
                    cursor = data.get("pagination", {}).get("cursor")
                    if not cursor: break
                    
            # 2. Aspirer les VIPs
            vips = []
            cursor = ""
            while True:
                url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&first=100"
                if cursor: url += f"&after={cursor}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    vips.extend(data.get("data", []))
                    cursor = data.get("pagination", {}).get("cursor")
                    if not cursor: break
                        
            def _save_sync():
                conn = sqlite3.connect(DB_PATH, timeout=20.0)
                count_mods, count_vips = 0, 0
                for m in mods:
                    conn.execute("INSERT OR IGNORE INTO viewers (twitch_id, username) VALUES (?, ?)", (m['user_id'], m['user_login']))
                    conn.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = ?", (m['user_id'],))
                    count_mods += 1
                for v in vips:
                    conn.execute("INSERT OR IGNORE INTO viewers (twitch_id, username) VALUES (?, ?)", (v['user_id'], v['user_login']))
                    conn.execute("UPDATE viewers SET is_vip = 1 WHERE twitch_id = ?", (v['user_id'],))
                    count_vips += 1
                conn.commit()
                conn.close()
                return count_mods, count_vips

            import asyncio
            count_mods, count_vips = await asyncio.to_thread(_save_sync)

        except Exception as e:
            logger.error(f"❌ [ROUTINE] Erreur dans l'aspirateur Twitch : {e}")

    @routines.routine(minutes=5)
    async def sync_subs_timer(self):
        """Récupère le nombre total de subs et l'écrit dans le fichier pour OBS."""
        if not self.broadcaster_id: return

        try:
            # 1. Préparation de la requête API Twitch
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {self.master_token}"
            }
            url = f"https://api.twitch.tv/helix/subscriptions?broadcaster_id={self.broadcaster_id}"

            # 2. On interroge Twitch avec la session globale
            session = await self.get_web_session()
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    # L'API Twitch renvoie un champ 'total' très pratique !
                    total_subs = data.get("total", 0)

                    # 3. On importe ton service et on écrit le fichier
                    from app.services.label_service import write_label
                    write_label("nombre_subs.txt", str(total_subs))

                    #logger.info(f"⭐ [AUTO-SYNC] Compteur de subs mis à jour : {total_subs}")
                else:
                    logger.warning(f"⚠️ [TWITCH API] Impossible de lire les subs (As-tu l'autorisation 'channel:read:subscriptions' ?) Code: {r.status}")

        except Exception as e:
            logger.error(f"❌ [AUTO-SYNC] Erreur de lecture des abonnés : {e}")

    @routines.routine(minutes=2)
    async def sync_viewers_timer(self):
        """Récupère le nombre de viewers en direct et l'écrit pour OBS."""
        if not self.broadcaster_id: return

        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {self.master_token}"
            }
            # L'API pour récupérer les infos du stream en cours
            url = f"https://api.twitch.tv/helix/streams?user_id={self.broadcaster_id}"

            # Utilisation de la session globale
            session = await self.get_web_session()
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    streams = data.get("data", [])

                    # Si la liste est vide, c'est que le stream est hors ligne (donc 0 viewer)
                    viewers_count = streams[0].get("viewer_count", 0) if streams else 0

                    # On écrit le résultat dans le fichier
                    from app.services.label_service import write_label
                    write_label("viewers.txt", str(viewers_count))

                    #logger.info(f"👁️ [AUTO-SYNC] Viewers mis à jour : {viewers_count}")
        except Exception as e:
            logger.error(f"❌ [AUTO-SYNC] Erreur de lecture des viewers : {e}")

    @routines.routine(seconds=60)
    async def announcements_timer(self):
        """Routine gérant l'envoi des annonces automatiques dans le chat."""
        try:
            # 1. Vérification si le stream est en ligne
            try:
                streams = await self.fetch_streams(user_logins=[self.channel_name])
                if not streams:
                    return
            except Exception:
                return

            # 2. Récupération des annonces en base de données
            async with get_db_connection() as conn:
                cursor = await conn.execute("SELECT * FROM announcements WHERE is_enabled = 1 AND trigger_type = 'interval'")
                announcements = await cursor.fetchall()
                
                channel = self.get_channel(self.channel_name)
                if not channel or not announcements:
                    return

                now = datetime.now()
                
                # 3. Calcul de l'intervalle minimum pour ne pas spammer
                min_intervals = []
                for a in announcements:
                    try:
                        val = int(a["interval_minutes"])
                        if val > 0: min_intervals.append(val)
                    except: pass
                
                min_interval = min(min_intervals) if min_intervals else 10
                
                # Vérification du dernier envoi global
                cursor_last = await conn.execute("SELECT MAX(last_triggered) as max_date FROM announcements WHERE is_enabled = 1 AND trigger_type = 'interval'")
                global_last_row = await cursor_last.fetchone()
                
                if global_last_row and global_last_row["max_date"]:
                    try:
                        global_last = datetime.strptime(global_last_row["max_date"], '%Y-%m-%d %H:%M:%S')
                        global_diff = (now - global_last).total_seconds() / 60
                        if global_diff < min_interval:
                            return
                    except: pass

                # 4. Sélection de l'annonce la plus "en retard"
                valid_anns = []
                for ann in announcements:
                    interval = int(ann["interval_minutes"] or 10)
                    last_trig_str = ann["last_triggered"]
                    
                    if not last_trig_str:
                        valid_anns.append((ann, 999999))
                    else:
                        try:
                            last_trig = datetime.strptime(last_trig_str, '%Y-%m-%d %H:%M:%S')
                            diff = (now - last_trig).total_seconds() / 60
                            if diff >= interval:
                                valid_anns.append((ann, diff - interval))
                        except: pass

                if not valid_anns:
                    return

                valid_anns.sort(key=lambda x: x[1], reverse=True)
                ann_to_send = valid_anns[0][0]
                msg = ann_to_send["message_template"]

                # 5. Remplacement des variables dynamiques (Stats P0)
                if "{viewers}" in msg:
                    msg = msg.replace("{viewers}", str(len(channel.chatters)) if channel else "0")

                if any(t in msg for t in ["{game}", "{title}", "{uptime}"]):
                    msg = msg.replace("{game}", streams[0].game_name)
                    msg = msg.replace("{title}", streams[0].title)
                    if "{uptime}" in msg:
                        start_time = streams[0].started_at
                        diff = datetime.utcnow() - start_time.replace(tzinfo=None)
                        hours, rem = divmod(int(diff.total_seconds()), 3600)
                        minutes, _ = divmod(rem, 60)
                        msg = msg.replace("{uptime}", f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m")

                # 6. Statistiques complexes (Top XP, Subs, etc.)
                if any(t in msg for t in ["{top5_xp}", "{top5_msg}", "{levelups}", "{last_sub}", "{last_raid}"]):
                    excl = "('masthom_', 'felixthebigblackcat', 'streamelements', 'wizebot', 'nightbot')"
                    
                    if "{top5_xp}" in msg:
                        cur = await conn.execute(f"SELECT username FROM viewers WHERE LOWER(username) NOT IN {excl} ORDER BY points DESC LIMIT 5")
                        res = await cur.fetchall()
                        msg = msg.replace("{top5_xp}", ", ".join([f"@{r['username']}" for r in res]))
                        
                    if "{top5_msg}" in msg:
                        cur = await conn.execute(f"SELECT username FROM viewers WHERE LOWER(username) NOT IN {excl} ORDER BY messages DESC LIMIT 5")
                        res = await cur.fetchall()
                        msg = msg.replace("{top5_msg}", ", ".join([f"@{r['username']}" for r in res]))

                    if "{last_sub}" in msg:
                        cur = await conn.execute("SELECT username FROM stream_events WHERE event_type = 'sub' ORDER BY timestamp DESC LIMIT 1")
                        ls = await cur.fetchone()
                        msg = msg.replace("{last_sub}", ls['username'] if ls else "Personne :(")

                    if "{levelups}" in msg:
                        cur = await conn.execute("SELECT twitch_id, username, points FROM viewers WHERE points > 0")
                        v_db = await cur.fetchall()
                        leveled = []
                        for v in v_db:
                            lvl = max(1, int((v['points'] / 100) ** (1 / 2.2)))
                            tid = str(v['twitch_id'])
                            if tid in self.known_levels and lvl > self.known_levels[tid]:
                                leveled.append(f"@{v['username']} (Lvl {lvl})")
                            self.known_levels[tid] = lvl
                        msg = msg.replace("{levelups}", ", ".join(leveled[:6]) if leveled else "Pas de level up récent !")

                # 7. Envoi final et mise à jour
                logger.info(f"📢 [ANNONCE] Envoi : '{ann_to_send['label']}'")
                await channel.send(msg)
                await conn.execute("UPDATE announcements SET last_triggered = ? WHERE id = ?", (now.strftime('%Y-%m-%d %H:%M:%S'), ann_to_send['id']))
                await conn.commit()

        except Exception as e:
            if "closing transport" not in str(e):
                logger.error(f"❌ [ROUTINE ERROR] Announcements Timer : {e}")

    @routines.routine(minutes=5)
    async def watchdog_timer(self):
        """Superviseur : Vérifie que toutes les routines tournent et ping Node.js."""
        
        # 1. Vérification des routines internes (Python)
        routines_to_check = {
            "Watchtime": self.watchtime_timer,
            "Annonces": self.announcements_timer,
            "Aspirateur de Rôles": self.sync_roles_timer,
            "Compteur Subs": self.sync_subs_timer,
            "Compteur Viewers": self.sync_viewers_timer,
            "Expiration VIP": self.vip_expiration_timer
        }

        for name, routine in routines_to_check.items():
            try:
                if routine._task is None:
                    # Si la routine n'a jamais démarré, on l'allume proprement
                    logger.info(f"▶️ [WATCHDOG] Démarrage initial de la routine '{name}'...")
                    routine.start()
                elif routine._task.done():
                    # Si elle avait démarré mais qu'elle s'est arrêtée, c'est un vrai crash
                    logger.warning(f"⚠️ [WATCHDOG] La routine '{name}' a crashé ! Relance de force...")
                    routine.restart()
            except Exception as e:
                logger.error(f"❌ [WATCHDOG] Erreur inattendue lors de la vérification de '{name}' : {e}")

        # 2. 🔥 NOUVEAU : Vérification de la santé du serveur externe (Node.js)
        try:
            # On utilise le timeout=2 pour ne pas bloquer le bot si Node.js est figé
            session = await self.get_web_session()
            async with session.get("http://127.0.0.1:3005/", timeout=2) as resp:
                pass # Si on arrive ici, c'est que Node.js est allumé et répond au réseau !
        except Exception:
            # Si le port 3005 est fermé ou injoignable, on déclenche une alerte rouge
            logger.error("🚨 [WATCHDOG FATAL] Impossible de contacter Node.js (Port 3005) ! L'overlay est probablement éteint ou planté.")

# --- FIN DU FICHIER ---
twitch_bot = MasthbotTwitch()
