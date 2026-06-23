import re
import random
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
from app.routes.clips import start_clips_poll
from app.services.label_service import write_label, lire_fichier_label

logger = logging.getLogger("masthbot.twitch")

# Set pour ne souhaiter l'anniversaire qu'une seule fois par session de bot
_birthday_wished: set = set()
_permitted_users: set = set()

async def safe_send(channel, content: str) -> bool:
    """Envoie un message en sécurisant la longueur et le contenu.
    Retourne False en cas d'échec, pour permettre à l'appelant de retenter
    plutôt que de considérer le message comme envoyé à tort."""
    if not content or not content.strip():
        return False # On ne fait rien si le message est vide

    # Tronquage à 500 caractères max
    if len(content) > 500:
        content = content[:497] + "..."

    try:
        await channel.send(content)
        return True
    except Exception as e:
        # "closing transport" : Twitch IRC force une reconnexion périodique, c'est
        # transitoire et attendu — pas la peine de polluer les logs en ERROR pour ça.
        if "closing transport" in str(e):
            logger.warning(f"⚠️ Envoi différé (reconnexion IRC en cours) : {e}")
        else:
            logger.error(f"❌ Erreur lors de l'envoi du message : {e}")
        return False

class MasthbotTwitch(commands.Bot):
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
            async with get_db_connection() as conn:
                c1 = await conn.execute("SELECT * FROM personality LIMIT 1")
                p_row = await c1.fetchone()
                
                c2 = await conn.execute("SELECT * FROM settings LIMIT 1")
                s_row = await c2.fetchone()

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

    async def event_ready(self):
        print(f"✅ [TWITCH] Connecté en tant que : {self.nick}")
        self.is_ready_flag = True

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

        content = message.content
        content_clean = content.strip()
        content_lower = content_clean.lower()

        await viewer_repo.ensure_viewer(str(message.author.id), message.author.name)
        username = message.author.name.lower()
        display_name = message.author.display_name or message.author.name
        config = await self.get_db_config()

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

        elif content_lower.startswith("!poll "):
            try:
                parts = content_clean.split(" ")
                if len(parts) > 1:
                    choice_idx = int(parts[1])
                    if 1 <= choice_idx <= 4:
                        await self._handle_twitch_poll_vote(message, choice_idx)
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

        if message.tags and message.tags.get('bits'):
            bits_amount = message.tags.get('bits')
            # 1. Mise à jour de l'overlay animé OBS (label_anime.html)
            write_label("dernier_bits.txt", display_name)
            # 2. Ajout pour le générique de fin
            credits_service.log_event("bits", display_name, f"{bits_amount} Bits")

        if message.content.startswith('!'):
            parts = message.content.split(' ', 1)
            cmd_name = parts[0][1:].lower()
            user_input = parts[1].strip() if len(parts) > 1 else ""

            # Commandes natives twitchio — ne pas intercepter
            NATIVE_COMMANDS = {
                'checkcopains', 'sondage', 'testpoll',
                'level', 'rang', 'timer', 'chrono', 'voteclips', 'addvip', 'vip',
                'permit', 'unpermit',
            }
            if cmd_name in NATIVE_COMMANDS:
                await self.handle_commands(message)
                return

            # --- 1. SYSTÈME DE TRADUCTION ---
            from app.services.features_service import handle_translation, LANGUAGES
            if cmd_name in LANGUAGES:
                reply = await handle_translation(cmd_name, display_name, user_input)
                return await safe_send(message.channel, reply)

            # --- 2. JEU DU MOT SECRET ---
            from app.services.features_service import handle_set_word, handle_guess_word
            if cmd_name == "setword":
                if is_mod or is_owner: # Réservé à l'élite
                    reply = await handle_set_word(display_name, user_input)
                    return await message.channel.send(reply)
                else:
                    return # Les viewers normaux ne peuvent pas définir le mot
                
            if cmd_name in ["guess", "mot"]: # Commandes pour deviner
                reply = await handle_guess_word(display_name, user_input)
                if reply: # On n'envoie un message que si c'est la bonne réponse !
                    return await message.channel.send(reply)

            if cmd_name in ["game", "infogame"]:
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
                    return await safe_send(message.channel, "❌ Aucun jeu spécifié et le stream est actuellement hors ligne.")

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
            )
            if result and result.get("content"):
                await safe_send(message.channel, result["content"])

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
                logger.info(f"🔄 [API SYNC] Rôles synchronisés pour le Twitch ID {twitch_id}")
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Erreur lors de sync_user_roles : {e}")

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
        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT id, option1, option2, option3, option4 FROM polls WHERE is_active=1 ORDER BY id DESC LIMIT 1")
                active_poll = await c.fetchone()

                if not active_poll:
                    return 

                opt_key = f"option{choice_idx}"
                if not active_poll[opt_key]:
                    return 

                await conn.execute("""
                    INSERT INTO poll_votes (poll_id, twitch_id, option_index)
                    VALUES ($1, $2, $3)
                    ON CONFLICT(poll_id, twitch_id) DO UPDATE SET option_index = EXCLUDED.option_index
                """, (active_poll['id'], str(message.author.id), choice_idx))
                
            await trigger_overlay_event({"type": "show_poll"})

        except Exception as e:
            logger.error(f"Erreur vote chat: {e}")

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
        """Capte les événements officiels Twitch dans le chat (Subs, Raids, etc.)"""
        msg_id = tags.get('msg-id')
        display_name = tags.get('display-name', 'Inconnu')

        # 🌟 ABONNEMENTS ET RESUBS
        if msg_id in ['sub', 'resub']:
            # 1. Label animé OBS
            write_label("dernier_sub.txt", display_name)
            # 2. Générique de fin
            months = tags.get('msg-param-cumulative-months', '1')
            tier = tags.get('msg-param-sub-plan', '1000')
            tier_name = "Tier 1" if tier == "1000" else "Tier 2" if tier == "2000" else "Tier 3" if tier == "3000" else "Prime"
            credits_service.log_event("subscribers", display_name, str(months))

        # 💣 AVALANCHE DE CADEAUX (Mystery Gifts : 5, 10, 20 subs d'un coup !)
        elif msg_id == 'submysterygift':
            amount = tags.get('msg-param-mass-gift-count', '1')
            
            # 1. Labels animés OBS
            write_label("dernier_subgift.txt", display_name)
            
            # 2. Ajout massif au générique
            credits_service.log_event("gifters", display_name, f"{amount} Gifts")

        # 🎁 CADEAUX D'ABONNEMENTS INDIVIDUELS (Subgift ciblé ou distribution)
        elif msg_id == 'subgift':
            recipient = tags.get('msg-param-recipient-display-name', 'Quelqu\'un')
            
            # L'heureux élu s'affiche sur l'overlay
            write_label("dernier_sub.txt", recipient) 
            
            # ⚠️ SÉCURITÉ : On ne compte ce "1 Gift" que si c'est un cadeau unique fait "à la main". 
            # Si le tag 'msg-param-communitygift-id' est là, c'est que c'est Twitch qui distribue la bombe d'au-dessus, donc on ignore pour ne pas compter double !
            if not tags.get('msg-param-communitygift-id'):
                write_label("dernier_subgift.txt", display_name)
                credits_service.log_event("gifters", display_name, "1 Gift")

        # 🚀 RAIDS
        elif msg_id == 'raid':
            viewers = tags.get('msg-param-viewerCount', '0')
            # 1. Label animé OBS
            write_label("dernier_raid.txt", display_name)
            # 2. Générique de fin
            credits_service.log_event("raiders", display_name, f"{viewers} viewers")

    @commands.command(name='so')
    async def shoutout_command(self, ctx, *, content: str = None):
        author_badges = ctx.author.badges or {}
        is_authorized = (
            ctx.author.is_mod
            or ctx.author.is_broadcaster
            or "moderator" in author_badges
            or ctx.author.name.lower() == self.channel_name
            or ctx.author.name.lower() == "felixthebigblackcat"
        )
        if not is_authorized:
            logger.warning(f"⚠️ [SHOUTOUT] !so refusé pour {ctx.author.name} (is_mod={ctx.author.is_mod}, is_broadcaster={ctx.author.is_broadcaster}, badges={author_badges})")
            return
        if not content:
            return await ctx.send("Miaou ! Pseudo ou lien requis : !so pseudo")

        input_val = content.replace("!so", "").strip().split()[0].split("?")[0]
        target_name = None
        slug_for_node = None

        client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
        session = await self.get_web_session()

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

        target_name_clean = target_name.lower()
        
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
        except Exception as e:
            logger.error(f"❌ [SHOUTOUT] Échec récupération infos pour {target_name_clean} : {e}")
            await ctx.send(f"Foncez voir @{target_name} ! https://twitch.tv/{target_name_clean}")

        try:
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/shoutout", json={"target": target_name_clean, "slug": slug_for_node}) as _:
                pass
        except Exception as e:
            logger.error(f"Erreur Envoi SO Node : {e}")

    @commands.command(name='replay')
    async def cmd_replay(self, ctx, *, content: str = None):
        author_badges = ctx.author.badges or {}
        is_authorized = (
            ctx.author.is_mod
            or ctx.author.is_broadcaster
            or "moderator" in author_badges
            or ctx.author.name.lower() == self.channel_name
            or ctx.author.name.lower() == "felixthebigblackcat"
        )
        if not is_authorized:
            logger.warning(f"⚠️ [REPLAY] !replay refusé pour {ctx.author.name} (is_mod={ctx.author.is_mod}, is_broadcaster={ctx.author.is_broadcaster}, badges={author_badges})")
            return

        slug, query = None, None
        if content:
            content = content.strip()
            if "twitch.tv" in content:
                slug = content
            else:
                query = content

        session = await self.get_web_session()

        try:
            payload = {"slug": slug, "query": query}
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/replay", json=payload) as _:
                pass
            
            sound_payload = {
                "type": "play_sound", 
                "file": "/static/uploads/hey_listen.mp3"
            }
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/alert", json=sound_payload) as _:
                pass

        except Exception as e:
             logger.error(f"❌ [REPLAY ERROR] : {e}")

    @commands.command(name='showtiktok')
    async def cmd_show_tiktok(self, ctx, *, content: str = None):
        """!showtiktok -> ressort la dernière vidéo TikTok connue sur l'overlay.
        !showtiktok <lien> -> affiche le TikTok du lien donné sur l'overlay.
        (Distinct de !tiktok, qui reste la commande personnalisée donnant le lien du réseau social.)"""
        TIKTOK_REPLAY_REWARD_ID = "093cceb1-3c5e-4e8e-bc16-7f27ff6a2d2b"
        reward_id = (ctx.message.tags or {}).get("custom-reward-id", "")
        is_reward_redemption = reward_id == TIKTOK_REPLAY_REWARD_ID

        author_badges = ctx.author.badges or {}
        is_owner = (
            ctx.author.is_broadcaster
            or ctx.author.name.lower() == self.channel_name
            or "broadcaster" in author_badges
        )
        is_authorized = (
            is_owner
            or ctx.author.is_mod
            or "moderator" in author_badges
            or ctx.author.name.lower() == "felixthebigblackcat"
            or is_reward_redemption  # viewer via récompense de points de chaîne TikTok Replay
        )
        if not is_authorized:
            logger.warning(f"⚠️ [TIKTOK] !showtiktok refusé pour {ctx.author.name} (is_mod={ctx.author.is_mod}, is_broadcaster={ctx.author.is_broadcaster}, badges={author_badges})")
            return

        async with get_db_connection() as conn:
            c = await conn.execute(
                "SELECT showtiktok_enabled, showtiktok_message, tiktok_username FROM discord_features_settings WHERE id = 1"
            )
            row = await c.fetchone()
        if row and not row["showtiktok_enabled"]:
            return
        message_template = (row["showtiktok_message"] if row else None) or "🎵 TikTok affiché à l'écran ! — {title} {url}"
        channel_tiktok_username = (row["tiktok_username"] if row else "") or ""

        logger.info(
            f"[TIKTOK] is_owner={is_owner} is_reward={is_reward_redemption} | name={ctx.author.name!r} "
            f"| channel_name={self.channel_name!r} | content={content!r}"
        )

        from app.services.tiktok_monitor import get_last_known_tiktok, get_direct_tiktok_video
        from app.routes.overlays import register_tiktok_proxy

        # Si du texte suit la commande mais que ce n'est pas un lien TikTok (ex: une récompense
        # de points de chaîne qui laisse passer le message tapé par le viewer), on affiche
        # simplement le dernier TikTok de la chaîne.
        candidate = content.strip().split()[0] if content and content.strip() else None
        source_url = candidate if candidate and "tiktok.com" in candidate.lower() else None

        if not source_url:
            last = await get_last_known_tiktok()
            if not last:
                return await ctx.send("❌ Aucune vidéo TikTok connue pour le moment.")
            source_url = last["url"]

        logger.info(f"[TIKTOK] Téléchargement en cours : {source_url}")
        video = await get_direct_tiktok_video(source_url)
        if not video:
            logger.error(f"[TIKTOK] Échec download pour {source_url}")
            return await ctx.send("❌ Impossible de récupérer cette vidéo TikTok. Vérifie le lien !")

        logger.info(f"[TIKTOK] Vidéo OK : uploader={video.get('uploader')!r} filepath={video.get('filepath')!r}")

        # Les mods/viewers (récompense) sont limités au compte TikTok de la chaîne.
        if not is_owner and channel_tiktok_username and video.get("uploader") != channel_tiktok_username.lower():
            try:
                os.remove(video["filepath"])
            except OSError:
                pass
            return await ctx.send(f"❌ Seul @{self.channel_name} peut afficher un TikTok d'un autre compte. Les modérateurs sont limités au TikTok de la chaîne (@{channel_tiktok_username}).")

        token = register_tiktok_proxy(video["filepath"])
        await trigger_overlay_event({"type": "show_tiktok", "url": f"/api/v1/tiktok_proxy/{token}"})
        logger.info(f"[TIKTOK] Overlay déclenché avec token={token}")

        reply = message_template.replace("{title}", video["title"]).replace("{url}", source_url)
        await safe_send(ctx.channel, reply)

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

        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT * FROM tracked_streamers WHERE is_active=1")
                tracked = await c.fetchall()
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
        tracked_by_login = {t["login"].lower(): t for t in tracked}
        async with get_db_connection() as conn:
            for s in streams:
                login = (getattr(s.user, "login", None) or s.user.name or "").lower()
                partner_msg = f"**{s.user.name}** est en live sur **{{CATEGORIE}}**, foncez lui donner de la force !"
                msg_id = await notification_service.send_discord_live_notification(
                    channel_id=channel_id,
                    channel_name=s.user.name,
                    title=s.title,
                    game=s.game_name,
                    custom_message=partner_msg,
                )
                if msg_id:
                    notified_count += 1
                    streamer = tracked_by_login.get(login)
                    if streamer:
                        await conn.execute(
                            "UPDATE tracked_streamers SET last_live_id=$1, last_message_id=$2 WHERE id=$3",
                            (str(s.id), str(msg_id), streamer["id"]),
                        )

        await ctx.send(f"✅ {notified_count} alertes envoyées !")

    @commands.command(name='sondage')
    async def cmd_sondage(self, ctx):
        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT * FROM polls WHERE is_active=1 ORDER BY id DESC LIMIT 1")
                poll = await c.fetchone()

                if not poll:
                    return await ctx.send("🐾 Aucun sondage en cours. Crée-en un sur ton interface admin !")

                c2 = await conn.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id=$1 GROUP BY option_index", (poll['id'],))
                votes = await c2.fetchall()
                
                results = {1: 0, 2: 0, 3: 0, 4: 0}
                total = 0
                for v in votes:
                    results[v['option_index']] = v['count']
                    total += v['count']

            await trigger_overlay_event({"type": "show_poll"})

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
        if not ctx.author.is_mod and not ctx.author.is_broadcaster:
            return

        try:
            import app.services.twitch_poll_state as poll_state
            
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
        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT points FROM viewers WHERE LOWER(username) = $1", (username,))
                row = await c.fetchone()
        except Exception as e:
            logger.error(f"Erreur cmd_level : {e}")
            return
        
        points = row['points'] if row else 0
        if points <= 0:
            return await ctx.send(f"@{ctx.author.name}, tu es Niveau 1 avec 0 EXP ! Parle dans le chat pour progresser. 🐾")
            
        level = max(1, int((points / 100) ** (1 / 2.2)))
        next_lvl_xp = int(100 * ((level + 1) ** 2.2))
        
        await ctx.send(f"@{ctx.author.name}, tu es Niveau {level} avec {points} EXP ! (Prochain niveau à {next_lvl_xp} EXP) 🌟")

    @commands.command(name='rang')
    async def cmd_rang(self, ctx):
        username = ctx.author.name.lower()
        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT username, points FROM viewers WHERE points > 0 ORDER BY points DESC, watchtime DESC")
                viewers = await c.fetchall()
        except Exception as e:
            logger.error(f"Erreur cmd_rang : {e}")
            return
        
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

        session = await self.get_web_session()

        if time_str.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            try:
                async with session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload) as _:
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
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload) as _:
                pass
            await ctx.send(f"⏱️ Timer de {minutes} minute(s) lancé à l'écran : {label.upper()}")
        except Exception as e:
            logger.error(f"Erreur Envoi Timer OBS : {e}")

    @commands.command(name='chrono')
    async def cmd_chrono(self, ctx, *, label: str = "CHRONO"):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster: return
        
        session = await self.get_web_session()

        if label and label.lower() in ["stop", "reset", "off", "clear"]:
            payload = { "type": "time_event", "details": { "action": "stop" } }
            try:
                async with session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload) as _:
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
            async with session.post(f"{settings.OVERLAY_NODE_URL}/api/trigger", json=payload) as _:
                pass
            await ctx.send(f"⏱️ Chronomètre lancé à l'écran : {label.upper()}")
        except Exception as e:
            logger.error(f"Erreur Envoi Chrono OBS : {e}")

    @commands.command(name='voteclips')
    async def voteclips_cmd(self, ctx: commands.Context):
        if ctx.author.is_mod or ctx.author.is_broadcaster:
            result = await start_clips_poll()
            if "error" in result:
                await ctx.send(f"❌ Erreur : {result['error']}")
            else:
                await ctx.send("📊 Le sondage est lancé ! Votez pour votre clip préféré en haut du t'chat !")
        else:
            await ctx.send("Désolé, seuls les modérateurs peuvent lancer le vote des clips !")

    @commands.command(name='addvip')
    async def cmd_addvip(self, ctx, target: str = None, duration_days: int = 0):
        if not ctx.author.is_mod and not ctx.author.is_broadcaster:
            return

        if not target:
            return await ctx.send("❌ Usage: !addvip <pseudo> <jours> (Ex: !addvip Masthom_ 7) Mettre 0 pour Permanent.")

        target_clean = target.lower().replace("@", "")

        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = $1", (target_clean,))
                viewer = await c.fetchone()

                if not viewer:
                    return await ctx.send(f"❌ Le viewer @{target} n'existe pas dans la base de données. Il doit parler au moins une fois.")

                expiry = None
                if duration_days > 0:
                    expiry = (datetime.now() + timedelta(days=duration_days)).isoformat()

                await conn.execute("UPDATE viewers SET is_vip = 1, vip_expiry = $1 WHERE LOWER(username) = $2", (expiry, target_clean))
        except Exception as e:
            logger.error(f"❌ [DB ERROR] Erreur API Twitch !addvip (Base de données) : {e}")
            return

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
        try:
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT is_vip, vip_expiry FROM viewers WHERE twitch_id = $1", (str(ctx.author.id),))
                user = await c.fetchone()
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

    @commands.command(name='permit')
    async def cmd_permit(self, ctx, *, target: str = None):
        if not ctx.author.is_mod and ctx.author.name.lower() != self.channel_name:
            return
        if not target:
            return await ctx.send("Usage : !permit <pseudo>")
        target_clean = target.strip().lstrip('@').lower()
        _permitted_users.add(target_clean)
        await ctx.send(f"✅ {target_clean} est autorisé à poster un lien pendant 60 secondes.")
        async def revoke():
            await asyncio.sleep(60)
            _permitted_users.discard(target_clean)
        asyncio.create_task(revoke())

    @commands.command(name='unpermit')
    async def cmd_unpermit(self, ctx, *, target: str = None):
        if not ctx.author.is_mod and ctx.author.name.lower() != self.channel_name:
            return
        if not target:
            return await ctx.send("Usage : !unpermit <pseudo>")
        target_clean = target.strip().lstrip('@').lower()
        _permitted_users.discard(target_clean)
        await ctx.send(f"🚫 {target_clean} n'est plus autorisé à poster des liens.")

    @routines.routine(seconds=60)
    async def watchtime_timer(self):
        if not self.broadcaster_id:
            return

        config = await self.get_db_config()
        if not config.get('personal_last_live_id'):
            return

        exp_to_give = int(config.get('exp_per_watchtime', 5))

        try:
            api_success = False
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
                                await conn.execute("""
                                    INSERT INTO viewers (twitch_id, username, watchtime, points) 
                                    VALUES ($1, $2, 60, $3)
                                    ON CONFLICT(twitch_id) DO UPDATE SET 
                                        watchtime = viewers.watchtime + 60,
                                        points = viewers.points + EXCLUDED.points,
                                        username = EXCLUDED.username
                                """, (t_id, u_name, exp_to_give))
                                
                                await conn.execute("""
                                    INSERT INTO viewer_daily_stats (twitch_id, day, watchtime, points_gained)
                                    VALUES ($1, CURRENT_DATE, 60, $2)
                                    ON CONFLICT(twitch_id, day) DO UPDATE SET
                                        watchtime = viewer_daily_stats.watchtime + 60,
                                        points_gained = viewer_daily_stats.points_gained + EXCLUDED.points_gained
                                """, (t_id, exp_to_give))
                                
                                credits_service.add_watchtime(c['user_name'], 1)
                                count += 1
                            except Exception as e:
                                logger.warning(f"⚠️ Erreur isolée pour {u_name}: {e}")

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

                            c = await conn.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = $1", (u_name,))
                            row = await c.fetchone()
                            
                            if row:
                                t_id = row['twitch_id']
                                await conn.execute(
                                    "UPDATE viewers SET watchtime = watchtime + 60, points = points + $1 WHERE twitch_id = $2",
                                    (exp_to_give, t_id)
                                )
                                await conn.execute("""
                                    INSERT INTO viewer_daily_stats (twitch_id, day, watchtime, points_gained)
                                    VALUES ($1, CURRENT_DATE, 60, $2)
                                    ON CONFLICT(twitch_id, day) DO UPDATE SET
                                        watchtime = viewer_daily_stats.watchtime + 60,
                                        points_gained = viewer_daily_stats.points_gained + EXCLUDED.points_gained
                                """, (t_id, exp_to_give))
                                credits_service.add_watchtime(chatter.name, 1)
                                count_fb += 1

                        if count_fb > 0:
                            logger.info(f"⚠️ Watchtime (Secours) distribué à {count_fb} personnes.")

        except Exception as e:
            logger.error(f"❌ [DB FATAL] Erreur critique routine Watchtime : {e}")

    @routines.routine(minutes=1)
    async def vip_expiration_timer(self):
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
                c = await conn.execute("""
                    SELECT twitch_id, username, vip_expiry FROM viewers
                    WHERE is_vip = 1 AND vip_expiry IS NOT NULL
                """)
                vips_to_check = await c.fetchall()

                for v in vips_to_check:
                    twitch_id = v['twitch_id']
                    username = v['username']
                    vip_expiry = v['vip_expiry']

                    try:
                        if isinstance(vip_expiry, datetime):
                            expiry_dt = vip_expiry
                        else:
                            expiry_str = str(vip_expiry).replace("T", " ")
                            if len(expiry_str) == 16:
                                expiry_str += ":00"
                            expiry_dt = datetime.strptime(expiry_str[:19], '%Y-%m-%d %H:%M:%S')

                        if expiry_dt <= now:
                            expired_vips.append({"twitch_id": twitch_id, "username": username})
                    except Exception as e:
                        logger.error(f"❌ Erreur lecture date pour {username} : {e}")

                if expired_vips:
                    headers = {"Client-ID": self._http.client_id, "Authorization": f"Bearer {self.master_token}"}
                    session = await self.get_web_session()

                    for v in expired_vips:
                        await conn.execute(
                            "UPDATE viewers SET is_vip = 0, vip_expiry = NULL WHERE twitch_id = $1",
                            (str(v['twitch_id']),)
                        )
                        
                        try:
                            url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&user_id={v['twitch_id']}"
                            async with session.delete(url, headers=headers) as resp:
                                if resp.status in (200, 204):
                                    logger.info(f"✅ VIP Temporaire expiré et retiré sur Twitch pour {v['username']}")
                                else:
                                    logger.error(f"⚠️ Impossible de retirer le VIP de {v['username']} sur Twitch (Erreur {resp.status})")
                        except Exception as e:
                            logger.error(f"❌ Erreur réseau API Twitch pour expiration {v['username']} : {e}")

                    logger.info(f"💾 [DB & TWITCH] Grades de {len(expired_vips)} viewers expirés et retirés avec succès.")
                        
        except Exception as e:
            logger.error(f"💥 CRASH DANS LA ROUTINE VIP : {e}", exc_info=True)

    @routines.routine(hours=1)
    async def sync_roles_timer(self):
        if not self.broadcaster_id: return
        
        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {self.master_token}"}
            session = await self.get_web_session()
            
            mods = []
            cursor_tw = ""
            while True:
                url = f"https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={self.broadcaster_id}&first=100"
                if cursor_tw: url += f"&after={cursor_tw}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    mods.extend(data.get("data", []))
                    cursor_tw = data.get("pagination", {}).get("cursor")
                    if not cursor_tw: break
                    
            vips = []
            cursor_tw = ""
            while True:
                url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={self.broadcaster_id}&first=100"
                if cursor_tw: url += f"&after={cursor_tw}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    vips.extend(data.get("data", []))
                    cursor_tw = data.get("pagination", {}).get("cursor")
                    if not cursor_tw: break

            async with get_db_connection() as conn:
                count_mods, count_vips = 0, 0
                for m in mods:
                    await conn.execute("INSERT INTO viewers (twitch_id, username) VALUES ($1, $2) ON CONFLICT(twitch_id) DO NOTHING", (str(m['user_id']), m['user_login']))
                    await conn.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = $1", (str(m['user_id']),))
                    count_mods += 1
                for v in vips:
                    await conn.execute("INSERT INTO viewers (twitch_id, username) VALUES ($1, $2) ON CONFLICT(twitch_id) DO NOTHING", (str(v['user_id']), v['user_login']))
                    await conn.execute("UPDATE viewers SET is_vip = 1 WHERE twitch_id = $1", (str(v['user_id']),))
                    count_vips += 1

            logger.info(f"🔄 [ASPIRATEUR] Synchro Twitch terminée : {count_mods} Modos, {count_vips} VIPs.")

        except Exception as e:
            logger.error(f"❌ [ROUTINE] Erreur dans l'aspirateur Twitch : {e}")

    @routines.routine(minutes=5)
    async def sync_subs_timer(self):
        if not self.broadcaster_id: return

        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {self.master_token}"
            }
            url = f"https://api.twitch.tv/helix/subscriptions?broadcaster_id={self.broadcaster_id}"

            session = await self.get_web_session()
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    total_subs = data.get("total", 0)

                    from app.services.label_service import write_label
                    write_label("nombre_subs.txt", str(total_subs))
                else:
                    logger.warning(f"⚠️ [TWITCH API] Impossible de lire les subs (As-tu l'autorisation 'channel:read:subscriptions' ?) Code: {r.status}")

        except Exception as e:
            logger.error(f"❌ [AUTO-SYNC] Erreur de lecture des abonnés : {e}")

    @routines.routine(minutes=2)
    async def sync_viewers_timer(self):
        if not self.broadcaster_id: return

        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {self.master_token}"
            }
            url = f"https://api.twitch.tv/helix/streams?user_id={self.broadcaster_id}"

            session = await self.get_web_session()
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    streams = data.get("data", [])

                    viewers_count = streams[0].get("viewer_count", 0) if streams else 0

                    from app.services.label_service import write_label
                    write_label("viewers.txt", str(viewers_count))
        except Exception as e:
            logger.error(f"❌ [AUTO-SYNC] Erreur de lecture des viewers : {e}")

    @routines.routine(seconds=60)
    async def announcements_timer(self):
        try:
            try:
                streams = await self.fetch_streams(user_logins=[self.channel_name])
                if not streams:
                    return
            except Exception:
                return

            async with get_db_connection() as conn:
                c1 = await conn.execute("SELECT * FROM announcements WHERE is_enabled = 1 AND trigger_type = 'interval'")
                announcements = await c1.fetchall()
                
                channel = self.get_channel(self.channel_name)
                if not channel or not announcements:
                    return

                now = datetime.now()
                
                min_intervals = []
                for a in announcements:
                    try:
                        val = int(a["interval_minutes"])
                        if val > 0: min_intervals.append(val)
                    except: pass
                
                min_interval = min(min_intervals) if min_intervals else 10
                
                c2 = await conn.execute("SELECT MAX(last_triggered) as max_date FROM announcements WHERE is_enabled = 1 AND trigger_type = 'interval'")
                global_last_row = await c2.fetchone()
                
                if global_last_row and global_last_row["max_date"]:
                    try:
                        global_last = global_last_row["max_date"]
                        if isinstance(global_last, str):
                            global_last = datetime.strptime(global_last, '%Y-%m-%d %H:%M:%S')
                            
                        global_diff = (now - global_last).total_seconds() / 60
                        if global_diff < min_interval:
                            return
                    except: pass

                valid_anns = []
                for ann in announcements:
                    interval = int(ann["interval_minutes"] or 10)
                    last_trig_raw = ann["last_triggered"]
                    
                    if not last_trig_raw:
                        valid_anns.append((ann, 999999))
                    else:
                        try:
                            if isinstance(last_trig_raw, datetime):
                                last_trig = last_trig_raw
                            else:
                                last_trig = datetime.strptime(str(last_trig_raw), '%Y-%m-%d %H:%M:%S')
                                
                            diff = (now - last_trig).total_seconds() / 60
                            if diff >= interval:
                                valid_anns.append((ann, diff - interval))
                        except: pass

                if not valid_anns:
                    return

                valid_anns.sort(key=lambda x: x[1], reverse=True)
                ann_to_send = valid_anns[0][0]
                msg = str(dict(ann_to_send).get("message_template") or "")

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

                if any(t in msg for t in ["{top5_xp}", "{top5_msg}", "{levelups}", "{last_sub}", "{last_raid}"]):
                    excl_list = ['masthom_', 'felixthebigblackcat', 'streamelements', 'wizebot', 'nightbot']
                    
                    if "{top5_xp}" in msg:
                        c_xp = await conn.execute("SELECT username FROM viewers WHERE LOWER(username) != ALL($1) ORDER BY points DESC LIMIT 5", (excl_list,))
                        res_xp = await c_xp.fetchall()
                        msg = msg.replace("{top5_xp}", ", ".join([f"@{r['username']}" for r in res_xp]))
                        
                    if "{top5_msg}" in msg:
                        c_msg = await conn.execute("SELECT username FROM viewers WHERE LOWER(username) != ALL($1) ORDER BY messages DESC LIMIT 5", (excl_list,))
                        res_msg = await c_msg.fetchall()
                        msg = msg.replace("{top5_msg}", ", ".join([f"@{r['username']}" for r in res_msg]))

                    if "{last_sub}" in msg:
                        c_sub = await conn.execute("SELECT username FROM stream_events WHERE event_type = 'sub' ORDER BY timestamp DESC LIMIT 1")
                        ls = await c_sub.fetchone()
                        msg = msg.replace("{last_sub}", ls['username'] if ls else "Personne :(")

                    if "{levelups}" in msg:
                        c_lvl = await conn.execute("SELECT twitch_id, username, points FROM viewers WHERE points > 0")
                        v_db = await c_lvl.fetchall()
                        leveled = []
                        for v in v_db:
                            lvl = max(1, int((v['points'] / 100) ** (1 / 2.2)))
                            tid = str(v['twitch_id'])
                            if tid in self.known_levels and lvl > self.known_levels[tid]:
                                leveled.append(f"@{v['username']} (Lvl {lvl})")
                            self.known_levels[tid] = lvl
                        msg = msg.replace("{levelups}", ", ".join(leveled[:6]) if leveled else "Pas de level up récent !")

                # 1. On cherche le nom de l'annonce peu importe la colonne
                nom_annonce = ann_to_send.get("label") or ann_to_send.get("title") or ann_to_send.get("name", "Annonce sans titre")
                
                # 2. Si le message est totalement vide, on bloque l'envoi et on analyse !
                if not msg or not msg.strip():
                    logger.error(f"❌ ÉCHEC : Le texte de '{nom_annonce}' est vide ! Twitch refuse de l'envoyer.")
                    logger.error(f"🔍 Voici les VRAIES colonnes de ta base de données : {list(ann_to_send.keys())}")
                    # Message vide = problème de config, pas de retry utile : on marque comme traité.
                    await conn.execute("UPDATE announcements SET last_triggered = $1 WHERE id = $2", (now, ann_to_send['id']))
                else:
                    # 3. L'envoi officiel sur Twitch
                    logger.info(f"📢 [ANNONCE] Envoi sur le chat : '{nom_annonce}'")
                    sent = await safe_send(channel, msg) if channel else False

                    # 4. On ne marque comme traité QUE si l'envoi a réussi : un échec transitoire
                    # (ex: reconnexion IRC) déclenche une nouvelle tentative au prochain cycle
                    # plutôt que de perdre l'annonce jusqu'au prochain intervalle complet.
                    if sent:
                        await conn.execute("UPDATE announcements SET last_triggered = $1 WHERE id = $2", (now, ann_to_send['id']))
                    else:
                        logger.warning(f"⚠️ [ANNONCE] '{nom_annonce}' non envoyée, nouvelle tentative au prochain cycle.")

        except Exception as e:
            if "closing transport" not in str(e):
                logger.error(f"❌ [ROUTINE ERROR] Announcements Timer : {e}")

    @routines.routine(seconds=90)
    async def special_announcements_timer(self):
        """Gère les annonces 'Début de Stream' (une fois par session live) et
        'Une seule fois' (une fois pour toujours), qui étaient configurables dans
        le panel admin mais jamais lues par aucune routine jusqu'ici."""
        try:
            streams = await self.fetch_streams(user_logins=[self.channel_name])
            if not streams:
                return

            channel = self.get_channel(self.channel_name)
            if not channel:
                return

            stream_started_at = streams[0].started_at.replace(tzinfo=None)
            now = datetime.now()

            async with get_db_connection() as conn:
                c = await conn.execute(
                    "SELECT * FROM announcements WHERE is_enabled = 1 AND trigger_type IN ('stream_start', 'once')"
                )
                anns = await c.fetchall()

                for ann in anns:
                    ann = dict(ann)
                    last_trig_raw = ann.get("last_triggered")
                    last_trig = None
                    if last_trig_raw:
                        last_trig = last_trig_raw if isinstance(last_trig_raw, datetime) else datetime.strptime(str(last_trig_raw), '%Y-%m-%d %H:%M:%S')

                    should_send = False
                    if ann["trigger_type"] == "once":
                        should_send = last_trig is None
                    elif ann["trigger_type"] == "stream_start":
                        should_send = last_trig is None or last_trig < stream_started_at

                    if not should_send:
                        continue

                    msg = str(ann.get("message_template") or "")
                    if not msg.strip():
                        continue

                    msg = msg.replace("{game}", streams[0].game_name).replace("{title}", streams[0].title)
                    sent = await safe_send(channel, msg)
                    if not sent:
                        logger.warning(f"⚠️ [ANNONCE {ann['trigger_type'].upper()}] '{ann.get('label', 'Sans titre')}' non envoyée, nouvelle tentative au prochain cycle.")
                        continue

                    logger.info(f"📢 [ANNONCE {ann['trigger_type'].upper()}] Envoi : '{ann.get('label', 'Sans titre')}'")

                    if ann["trigger_type"] == "once":
                        await conn.execute("UPDATE announcements SET last_triggered = $1, is_enabled = 0 WHERE id = $2", (now, ann["id"]))
                    else:
                        await conn.execute("UPDATE announcements SET last_triggered = $1 WHERE id = $2", (now, ann["id"]))
        except Exception as e:
            if "closing transport" not in str(e):
                logger.error(f"❌ [ROUTINE ERROR] Special Announcements Timer : {e}")

    @routines.routine(minutes=5)
    async def watchdog_timer(self):
        routines_to_check = {
            "Watchtime": self.watchtime_timer,
            "Annonces": self.announcements_timer,
            "Annonces Spéciales": self.special_announcements_timer,
            "Aspirateur de Rôles": self.sync_roles_timer,
            "Compteur Subs": self.sync_subs_timer,
            "Compteur Viewers": self.sync_viewers_timer,
            "Expiration VIP": self.vip_expiration_timer,
            "Détecteur Followers": self.followers_detector_timer
        }

        for name, routine in routines_to_check.items():
            try:
                if routine._task is None:
                    logger.info(f"▶️ [WATCHDOG] Démarrage initial de la routine '{name}'...")
                    routine.start()
                elif routine._task.done():
                    logger.warning(f"⚠️ [WATCHDOG] La routine '{name}' a crashé ! Relance de force...")
                    routine.restart()
            except Exception as e:
                logger.error(f"❌ [WATCHDOG] Erreur inattendue lors de la vérification de '{name}' : {e}")

        try:
            session = await self.get_web_session()
            async with session.get(f"{settings.OVERLAY_NODE_URL}/", timeout=2) as resp:
                pass
        except Exception:
            logger.error("🚨 [WATCHDOG FATAL] Impossible de contacter Node.js (Port 3005) ! L'overlay est probablement éteint ou planté.")

    @routines.routine(seconds=3)
    async def followers_detector_timer(self):
        """Détecteur ultra-rapide de followers (Instantané)"""
        if not self.broadcaster_id: return

        try:
            client_id = os.getenv("TWITCH_CLIENT_ID", getattr(self._http, 'client_id', ''))
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {self.master_token}"
            }
            # On interroge Twitch pour voir le tout dernier follower
            url = f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={self.broadcaster_id}&first=1"

            session = await self.get_web_session()
            async with session.get(url, headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("data"):
                        latest_follower = data["data"][0]["user_name"]
                        
                        # On lit le dernier enregistré
                        current_follower = lire_fichier_label("dernier_follow.txt")
                        
                        # Si c'est un NOUVEAU follower (Réaction à la seconde près !)
                        if current_follower.lower() != latest_follower.lower():
                            write_label("dernier_follow.txt", latest_follower)
                            credits_service.log_event("followers", latest_follower, "Bienvenue !")
                            logger.info(f"💙 Nouveau Follower instantané : {latest_follower}")
        except Exception as e:
            logger.error(f"❌ [DETECTOR] Erreur Follow : {e}")

twitch_bot = MasthbotTwitch()
