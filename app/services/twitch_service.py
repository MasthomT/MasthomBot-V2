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
from app.core.database import init_db

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

        super().__init__(
            token=clean_bot_token,
            prefix='!',
            initial_channels=[settings.TWITCH_CHANNEL]
        )

    def get_db_config(self):
        conn = None # On prépare la variable
        try:
            conn = sqlite3.connect(DB_PATH, timeout=20.0)
            conn.row_factory = sqlite3.Row
            p_row = conn.execute("SELECT * FROM personality LIMIT 1").fetchone()
            s_row = conn.execute("SELECT * FROM settings LIMIT 1").fetchone()

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
            logger.error(f"❌ [DB ERROR] : {e}")
            return {}
        finally:
            # 🛡️ LE SECRET EST ICI : Le bloc "finally" est TOUJOURS exécuté, 
            # même s'il y a eu un bug (Exception) ou un "return" avant !
            if conn:
                conn.close()

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

        except Exception as e:
            print(f"❌ [READY ERROR] : {e}")

    async def event_stream_online(self, channel):
        config = self.get_db_config()
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
        config = self.get_db_config()
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

        # 🤖 ENREGISTREMENT 100% AUTOMATIQUE DES BADGES TWITCH DANS TA BDD
        # FIX : On n'ouvre la base QUE si le viewer a un badge ET qu'on ne l'a pas encore enregistré
        if (is_vip or is_mod or is_artist) and str(message.author.id) not in self.role_checked_users:
            conn = sqlite3.connect(DB_PATH, timeout=20.0)
            try:
                if is_vip:
                    conn.execute("UPDATE viewers SET is_vip = 1 WHERE twitch_id = ?", (str(message.author.id),))
                if is_mod:
                    conn.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = ?", (str(message.author.id),))
                if is_artist:
                    conn.execute("UPDATE viewers SET is_artist = 1 WHERE twitch_id = ?", (str(message.author.id),))
                conn.commit()
                self.role_checked_users.add(str(message.author.id)) # AJOUT : Le bot s'en souvient et ne bloquera plus la BDD
            except Exception as e:
                logger.error(f"Erreur d'enregistrement auto des badges: {e}")
            finally:
                conn.close()

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

        # Nettoyage de l'input (enlève !so et garde le premier mot/lien)
        input_val = content.replace("!so", "").strip().split()[0].split("?")[0]
        target_name = None
        slug_for_node = None

        client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}

        # 1. DÉCODAGE DU LIEN OU DU PSEUDO
        if "twitch.tv" in input_val:
            if "clips.twitch.tv" in input_val:
                # Format: clips.twitch.tv/SlugDuClip
                slug_for_node = input_val.split("clips.twitch.tv/")[-1].strip("/")
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"https://api.twitch.tv/helix/clips?id={slug_for_node}", headers=headers) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get("data"):
                                    target_name = data["data"][0]["broadcaster_name"]
                    except: pass

            elif "/clip/" in input_val:
                # Format: twitch.tv/pseudo/clip/SlugDuClip
                parts = input_val.split("twitch.tv/")[-1].strip("/").split("/")
                target_name = parts[0]
                slug_for_node = parts[2] if len(parts) >= 3 else None

            elif "/videos/" in input_val:
                # Format: twitch.tv/videos/123456789
                video_id = input_val.split("/videos/")[-1].strip("/")
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"https://api.twitch.tv/helix/videos?id={video_id}", headers=headers) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get("data"):
                                    target_name = data["data"][0]["user_name"]
                    except: pass
            else:
                # Format: twitch.tv/pseudo
                target_name = input_val.split("twitch.tv/")[-1].strip("/")
        else:
            # Format direct: pseudo
            target_name = input_val.replace("@", "")

        # Vérification si on a trouvé un nom
        if not target_name:
            return await ctx.send("❌ Impossible de récupérer le pseudo depuis ce lien ! Vérifie ton URL.")

        # 2. ENVOI DES MESSAGES ET DÉCLENCHEMENT DE L'OVERLAY
        target_name_clean = target_name.lower()
        async with aiohttp.ClientSession() as session:
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
                await session.post("http://127.0.0.1:3005/api/shoutout", json={"target": target_name_clean, "slug": slug_for_node})
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

        async with aiohttp.ClientSession() as session:
            try:
                payload = {"slug": slug, "query": query}
                await session.post("http://127.0.0.1:3005/api/replay", json=payload)
            except Exception as e:
                print(f"❌ [REPLAY ERROR] : {e}")

    @commands.command(name='renotif')
    async def cmd_renotif(self, ctx):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster:
            return
        config = self.get_db_config()
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
        config = self.get_db_config()
        channel_id = config.get('streamers_channel_id')
        if not channel_id:
            return await ctx.send("❌ Aucun salon Discord configuré.")

        conn = sqlite3.connect(DB_PATH, timeout=20.0)
        conn.row_factory = sqlite3.Row
        tracked = conn.execute("SELECT * FROM tracked_streamers WHERE is_active=1").fetchall()
        conn.close()

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
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            # 1. On récupère le sondage Fel-X actif
            poll = conn.execute("SELECT * FROM polls WHERE is_active=1 ORDER BY id DESC LIMIT 1").fetchone()
            
            if not poll:
                return await ctx.send("🐾 Aucun sondage en cours. Crée-en un sur ton interface admin !")

            # 2. Calcul des votes actuels pour le chat
            votes = conn.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id=? GROUP BY option_index", (poll['id'],)).fetchall()
            results = {1: 0, 2: 0, 3: 0, 4: 0}
            total = 0
            for v in votes:
                results[v['option_index']] = v['count']
                total += v['count']

            # 3. ✅ LA CORRECTION : On envoie le signal "show_poll" au port 8000
            # On n'utilise plus aiohttp vers le port 3005 ici !
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
            logger.error(f"❌ Erreur cmd_sondage : {e}")
        finally:
            conn.close()

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

        if time_str.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            async with aiohttp.ClientSession() as session:
                try:
                    await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
                    await ctx.send("🛑 Timer effacé de l'écran !")
                except Exception as e:
                    logger.error(f"Erreur Stop Timer OBS : {e}")
            return

        try:
            minutes = int(time_str)
            duration_seconds = minutes * 60
        except ValueError:
            return await ctx.send("❌ La durée doit être un chiffre exact en minutes (ex: !timer 5)")

        async with aiohttp.ClientSession() as session:
            payload = {
                "type": "time_event",
                "details": { "action": "start", "mode": "timer", "duration": duration_seconds, "label": label.upper() }
            }
            try:
                await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
                await ctx.send(f"⏱️ Timer de {minutes} minute(s) lancé à l'écran : {label.upper()}")
            except Exception as e:
                logger.error(f"Erreur Envoi Timer OBS : {e}")

    @commands.command(name='chrono')
    async def cmd_chrono(self, ctx, *, label: str = "CHRONO"):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster: return

        if label and label.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            async with aiohttp.ClientSession() as session:
                try:
                    await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
                    await ctx.send("🛑 Chrono effacé de l'écran !")
                except Exception as e:
                    logger.error(f"Erreur Stop Chrono OBS : {e}")
            return

        async with aiohttp.ClientSession() as session:
            payload = {
                "type": "time_event",
                "details": { "action": "start", "mode": "chrono", "duration": 0, "label": label.upper() }
            }
            try:
                await session.post("http://127.0.0.1:3005/api/trigger", json=payload)
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
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        viewer = conn.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = ?", (target_clean,)).fetchone()
        
        if not viewer:
            conn.close()
            return await ctx.send(f"❌ Le viewer @{target} n'existe pas dans la base de données. Il doit parler au moins une fois.")
            
        expiry = None
        if duration_days > 0:
            expiry = (datetime.now() + timedelta(days=duration_days)).isoformat()
            
        conn.execute("UPDATE viewers SET is_vip = 1, vip_expiry = ? WHERE LOWER(username) = ?", (expiry, target_clean))
        conn.commit()
        conn.close()
        
        try:
            headers = {"Client-ID": self._http.client_id, "Authorization": f"Bearer {self.master_token}"}
            url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&user_id={viewer['twitch_id']}"
            async with aiohttp.ClientSession() as session:
                await session.post(url, headers=headers)
        except Exception as e:
            logger.error(f"Erreur API Twitch !addvip : {e}")
        
        if duration_days > 0:
            await ctx.send(f"💎 L'élite s'agrandit ! @{target} est désormais VIP pour {duration_days} jours !")
        else:
            await ctx.send(f"⭐ Consécration ! @{target} est désormais VIP à vie !")

    @commands.command(name='vip')
    async def cmd_vip(self, ctx):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT is_vip, vip_expiry FROM viewers WHERE twitch_id = ?", (str(ctx.author.id),)).fetchone()
        conn.close()

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
        if not self.broadcaster_id: return

        config = self.get_db_config()
        if not config.get('personal_last_live_id'):
            return

        exp_to_give = config.get('exp_per_watchtime', 5)
        
        try:
            api_success = False
            async with aiohttp.ClientSession() as session:
                client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
                headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
                url = f"https://api.twitch.tv/helix/chat/chatters?broadcaster_id={self.broadcaster_id}&moderator_id={self.broadcaster_id}"
                
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        chatters = data.get('data', [])
                        
                        count = 0
                        for c in chatters:
                            t_id = c['user_id']
                            u_name = c['user_name']
                            
                            if u_name.lower() in [self.nick.lower(), 'nightbot', 'streamelements', 'wizebot']:
                                continue

                            # FIX: Isolation des crashs liés aux changements de pseudos (UNIQUE constraint)
                            try:
                                credits_service.add_watchtime(c['user_name'], 1)
                                await viewer_repo.ensure_viewer(t_id, u_name)
                                await viewer_repo.update_viewer_stats(username=u_name.lower(), watchtime_add=60, points_add=exp_to_give)
                                count += 1
                            except Exception as e:
                                logger.warning(f"⚠️ Impossible d'ajouter le watchtime à {u_name} : {e}")
                                continue
                        
                        if count > 0:
                            logger.info(f"💎 Watchtime distribué à {count} personnes (Lurkers inclus).")
                        api_success = True
                        
                    elif resp.status in [401, 403]:
                        logger.error(f"❌ BLOCAGE TWITCH ({resp.status}) : Ton token n'a pas la permission 'moderator:read:chatters'.")

            if not api_success:
                channel = self.get_channel(self.channel_name)
                if channel and hasattr(channel, 'chatters'):
                    count_fb = 0
                    for chatter in channel.chatters:
                        u_name = chatter.name.lower()
                        if u_name in [self.nick.lower(), 'nightbot', 'streamelements', 'wizebot']: continue
                        
                        try:
                            credits_service.add_watchtime(chatter.name, 1)
                            success = await viewer_repo.update_viewer_stats(username=u_name, watchtime_add=60, points_add=exp_to_give)
                            if success: count_fb += 1
                        except Exception as e:
                            logger.warning(f"⚠️ Impossible d'ajouter le watchtime (secours) à {u_name} : {e}")
                            continue
                            
                    if count_fb > 0:
                        logger.info(f"⚠️ Watchtime (Secours) distribué à {count_fb} personnes actives dans le chat.")

        except Exception as e:
            logger.error(f"❌ Erreur globale routine Watchtime : {e}")

    @routines.routine(hours=1)
    async def vip_expiration_timer(self):
        try:
            if not getattr(self, 'broadcaster_id', None):
                users = await self.fetch_users(names=[self.channel_name])
                if users:
                    self.broadcaster_id = users[0].id
                else:
                    return

            conn = sqlite3.connect(DB_PATH, timeout=20.0)
            conn.row_factory = sqlite3.Row
            
            vips_to_check = conn.execute("""
                SELECT twitch_id, username, vip_expiry FROM viewers 
                WHERE is_vip = 1 AND vip_expiry IS NOT NULL
            """).fetchall()
            
            now = datetime.now()
            expired_vips = []
            
            for v in vips_to_check:
                try:
                    expiry_str = v['vip_expiry'].replace("T", " ")
                    if len(expiry_str) == 16:
                        expiry_str += ":00"
                    
                    expiry_dt = datetime.strptime(expiry_str[:19], '%Y-%m-%d %H:%M:%S')
                    
                    if expiry_dt <= now:
                        expired_vips.append(v)
                except Exception as e:
                    logger.error(f"❌ Erreur lecture date pour {v['username']} : {e}")

            for v in expired_vips:
                t_id = str(v['twitch_id'])
                u_name = v['username']
                
                conn.execute("UPDATE viewers SET is_vip = 0, vip_expiry = NULL WHERE twitch_id = ?", (t_id,))
                conn.commit()
                logger.info(f"💾 [BASE DE DONNÉES] Le grade de {u_name} est supprimé !")

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {self.master_token}"}) as r:
                            data = await r.json()
                            client_id = data.get('client_id', getattr(self._http, 'client_id', ''))

                        headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
                        url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&user_id={t_id}"
                        
                        resp = await session.delete(url, headers=headers)
                        
                        if resp.status in [200, 204]:
                            logger.info(f"✅ [TWITCH API] Le badge de {u_name} a été retiré sur le chat !")
                        else:
                            logger.warning(f"⚠️ [TWITCH API] Twitch a refusé (Code: {resp.status}).")
                except Exception as api_err:
                    logger.error(f"❌ Erreur réseau avec Twitch : {api_err}")

            conn.close()
        except Exception as e:
            logger.error(f"❌ Erreur FATALE routine VIP : {e}")

    # =====================================================================
    # 🤖 ASPIRATEUR AUTOMATIQUE DES MODOS ET VIPs DEPUIS TWITCH
    # =====================================================================
    @routines.routine(hours=1)
    async def sync_roles_timer(self):
        """Aspirateur Automatique de Rôles Twitch (Tourne toutes les heures en fond)"""
        if not self.broadcaster_id: return
        
        #logger.info("🔄 [AUTO-SYNC] Le Raspberry Pi aspire les Modos et VIPs depuis Twitch...")
        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
            
            async with aiohttp.ClientSession() as session:
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
                        
            # 3. Sauvegarde 100% Automatique en Base de Données (SEULEMENT À LA FIN POUR NE PAS BLOQUER)
            def _save_sync():
                conn = sqlite3.connect(DB_PATH, timeout=20.0)
                try: conn.execute("ALTER TABLE viewers ADD COLUMN is_mod INTEGER DEFAULT 0")
                except: pass
                try: conn.execute("ALTER TABLE viewers ADD COLUMN is_artist INTEGER DEFAULT 0")
                except: pass
                
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

            # Exécuter l'écriture SQL de manière asynchrone
            count_mods, count_vips = await asyncio.to_thread(_save_sync)
            #logger.info(f"✅ [AUTO-SYNC] Terminé ! {count_mods} Modérateurs et {count_vips} VIPs mis à jour dans la base.")
        except Exception as e:
            logger.error(f"❌ [AUTO-SYNC] Erreur : {e}")

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
            
            # 2. On interroge Twitch[cite: 3]
            async with aiohttp.ClientSession() as session:
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
            
            async with aiohttp.ClientSession() as session:
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
        try:
            try:
                streams = await self.fetch_streams(user_logins=[self.channel_name])
                if not streams: return
            except Exception: return

            conn = sqlite3.connect(DB_PATH, timeout=20.0)
            conn.row_factory = sqlite3.Row
            
            try:
                conn.execute("ALTER TABLE announcements ADD COLUMN last_triggered DATETIME")
                conn.commit()
            except sqlite3.OperationalError: pass

            announcements = conn.execute("SELECT * FROM announcements WHERE is_enabled = 1 AND trigger_type = 'interval'").fetchall()
            channel = self.get_channel(self.channel_name)
            
            if not channel or not announcements:
                conn.close()
                return

            now = datetime.now()
            min_intervals = []
            for a in announcements:
                try:
                    val = int(a["interval_minutes"])
                    if val > 0: min_intervals.append(val)
                except: pass
            min_interval = min(min_intervals) if min_intervals else 10
            
            global_last_row = conn.execute("SELECT MAX(last_triggered) as max_date FROM announcements WHERE is_enabled = 1 AND trigger_type = 'interval'").fetchone()
            if global_last_row and global_last_row["max_date"]:
                try:
                    global_last = datetime.strptime(global_last_row["max_date"], '%Y-%m-%d %H:%M:%S')
                    global_diff_minutes = (now - global_last).total_seconds() / 60
                    if global_diff_minutes < min_interval:
                        conn.close()
                        return
                except: pass

            valid_anns = []
            for ann in announcements:
                try: interval = int(ann["interval_minutes"])
                except: interval = 10
                
                last_trig_str = ann["last_triggered"]
                if not last_trig_str:
                    valid_anns.append((ann, 999999))
                else:
                    try:
                        last_trig = datetime.strptime(last_trig_str, '%Y-%m-%d %H:%M:%S')
                        diff_minutes = (now - last_trig).total_seconds() / 60
                        if diff_minutes >= interval:
                            valid_anns.append((ann, diff_minutes - interval))
                    except: pass

            if valid_anns:
                valid_anns.sort(key=lambda x: x[1], reverse=True)
                ann_to_send = valid_anns[0][0]
                
                ann_id = ann_to_send["id"]
                msg = ann_to_send["message_template"]
                
                if "{viewers}" in msg:
                    msg = msg.replace("{viewers}", str(len(channel.chatters)) if channel else "0")
                
                if any(t in msg for t in ["{game}", "{title}", "{uptime}"]):
                    if streams:
                        msg = msg.replace("{game}", streams[0].game_name)
                        msg = msg.replace("{title}", streams[0].title)
                        
                        if "{uptime}" in msg:
                            try:
                                start_time = streams[0].started_at
                                now_utc = datetime.utcnow()
                                diff = now_utc - start_time.replace(tzinfo=None)
                                hours, remainder = divmod(int(diff.total_seconds()), 3600)
                                minutes, _ = divmod(remainder, 60)
                                uptime_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes} minutes"
                                msg = msg.replace("{uptime}", uptime_str)
                            except:
                                msg = msg.replace("{uptime}", "Inconnu")
                    else:
                        msg = msg.replace("{game}", "Just Chatting").replace("{title}", "Stream hors ligne").replace("{uptime}", "Hors ligne")
                        
                if any(t in msg for t in ["{top5_xp}", "{top5_msg}", "{levelups}", "{last_sub}", "{last_raid}"]):
                    conn_stats = sqlite3.connect(DB_PATH, timeout=20.0)
                    conn_stats.row_factory = sqlite3.Row
                    exclusion_list = "('masthom_', 'felixthebigblackcat', 'streamelements', 'wizebot', 'nightbot')"
                    
                    if "{top5_xp}" in msg:
                        top = conn_stats.execute(f"SELECT username FROM viewers WHERE LOWER(username) NOT IN {exclusion_list} ORDER BY points DESC LIMIT 5").fetchall()
                        msg = msg.replace("{top5_xp}", ", ".join([f"@{r['username']}" for r in top]))
                        
                    if "{top5_msg}" in msg:
                        top = conn_stats.execute(f"SELECT username FROM viewers WHERE LOWER(username) NOT IN {exclusion_list} ORDER BY messages DESC LIMIT 5").fetchall()
                        msg = msg.replace("{top5_msg}", ", ".join([f"@{r['username']}" for r in top]))

                    if "{last_sub}" in msg:
                        ls = conn_stats.execute("SELECT username FROM stream_events WHERE event_type = 'sub' ORDER BY timestamp DESC LIMIT 1").fetchone()
                        msg = msg.replace("{last_sub}", ls['username'] if ls else "Personne :(")

                    if "{last_raid}" in msg:
                        lr = conn_stats.execute("SELECT username FROM stream_events WHERE event_type = 'raid' ORDER BY timestamp DESC LIMIT 1").fetchone()
                        msg = msg.replace("{last_raid}", lr['username'] if lr else "Aucun raid récent")
                        
                    if "{levelups}" in msg:
                        viewers_db = conn_stats.execute("SELECT twitch_id, username, points FROM viewers WHERE points > 0").fetchall()
                        leveled_up = []
                        excl_py = ["masthom_", "felixthebigblackcat", "streamelements", "wizebot", "nightbot"]
                        
                        for v in viewers_db:
                            tid = str(v['twitch_id'])
                            uname = v['username']
                            pts = v['points'] or 0
                            if uname.lower() in excl_py: continue
                            
                            lvl = max(1, int((pts / 100) ** (1 / 2.2)))
                            if tid not in self.known_levels:
                                self.known_levels[tid] = lvl
                            elif lvl > self.known_levels[tid]:
                                leveled_up.append({"name": uname, "level": lvl})
                                self.known_levels[tid] = lvl
                                
                        if leveled_up:
                            leveled_up.sort(key=lambda x: x["level"], reverse=True)
                            max_disp = 6
                            chunk = [f"@{u['name']} (Lvl {u['level']})" for u in leveled_up[:max_disp]]
                            lvl_str = ", ".join(chunk)
                            if len(leveled_up) > max_disp:
                                lvl_str += f"... et {len(leveled_up) - max_disp} autres !"
                        else:
                            lvl_str = "Personne n'a level up récemment ! Au boulot 💤"
                            
                        msg = msg.replace("{levelups}", lvl_str)
                        
                    conn_stats.close()
                    
                logger.info(f"📢 [ANNONCE] Envoi en rotation : '{ann_to_send['label']}'")
                await channel.send(msg)
                
                conn.execute("UPDATE announcements SET last_triggered = ? WHERE id = ?", (now.strftime('%Y-%m-%d %H:%M:%S'), ann_id))
                conn.commit()
                
            conn.close()
        except Exception as e:
            if "closing transport" not in str(e):
                logger.error(f"❌ [ROUTINE ERROR] Announcements Timer a crashé : {e}")

twitch_bot = MasthbotTwitch()
