import asyncio
import aiohttp
import logging
import dotenv
import os
from app.services.notification_service import notification_service
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.monitor")

async def _upgrade_database_schema():
    try:
        async with get_db_connection() as conn:
            await conn.execute("ALTER TABLE tracked_streamers ADD COLUMN IF NOT EXISTS last_message_id TEXT DEFAULT ''")
            await conn.execute("ALTER TABLE tracked_streamers ADD COLUMN IF NOT EXISTS last_live_id TEXT DEFAULT ''")
            await conn.execute("ALTER TABLE tracked_streamers ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1")
            
            await conn.execute("ALTER TABLE settings ADD COLUMN IF NOT EXISTS personal_last_live_id TEXT DEFAULT ''")
            await conn.execute("ALTER TABLE settings ADD COLUMN IF NOT EXISTS personal_last_message_id TEXT DEFAULT ''")
    except Exception as e:
        pass

async def check_twitch_lives_routine():
    await _upgrade_database_schema()

    while True:
        try:
            env_vars = dotenv.dotenv_values(".env")
            client_id = env_vars.get("TWITCH_CLIENT_ID", "").strip()
            token = env_vars.get("TWITCH_OAUTH_TOKEN", "").replace("oauth:", "").strip()
            my_channel = env_vars.get("TWITCH_CHANNEL", "masthom_").replace("#", "").strip()

            if not client_id or not token:
                logger.warning("⚠️ Identifiants Twitch manquants pour le moniteur.")
                await asyncio.sleep(60)
                continue

            async with get_db_connection() as conn:
                c1 = await conn.execute("SELECT * FROM settings WHERE id=1")
                settings_row_raw = await c1.fetchone()
                
                c2 = await conn.execute("SELECT * FROM tracked_streamers WHERE is_active=1")
                tracked_raw = await c2.fetchall()
                tracked = [dict(t) for t in tracked_raw]

                if not settings_row_raw:
                    await asyncio.sleep(60)
                    continue
                    
                settings_row = dict(settings_row_raw)
                logins_to_check = [my_channel] + [s["login"] for s in tracked]

                headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
                url = f"https://api.twitch.tv/helix/streams?user_login={'&user_login='.join(logins_to_check)}"

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            online_streams = {stream["user_login"].lower(): stream for stream in data.get("data", [])}

                            # ==========================================================
                            # 1. GESTION DE TON LIVE PERSONNEL (Inchangée)
                            # ==========================================================
                            my_login = my_channel.lower()
                            if my_login in online_streams:
                                stream = online_streams[my_login]
                                live_id = stream["id"]
                                if settings_row.get("personal_last_live_id") != live_id:
                                    logger.info("🚨 [MONITOR] Ton live commence ! Envoi notif Discord...")
                                    try:
                                        msg_id = await notification_service.send_discord_live_notification(
                                            channel_id=settings_row["notif_live_channel_id"],
                                            channel_name=stream["user_name"],
                                            title=stream["title"],
                                            game=stream["game_name"],
                                            custom_message=settings_row["discord_notify_message"]
                                        )
                                        if msg_id:
                                            await conn.execute("UPDATE settings SET personal_last_live_id=$1, personal_last_message_id=$2 WHERE id=1", (live_id, str(msg_id)))
                                    except Exception as e:
                                        logger.error(f"❌ [DISCORD ERROR] Impossible d'envoyer ta notif : {e}")
                            else:
                                if settings_row.get("personal_last_live_id") != "":
                                    await conn.execute("UPDATE settings SET personal_last_live_id='' WHERE id=1")
                                    try:
                                        from app.services.credits_service import credits_service
                                        credits_service.reset_session()
                                    except: pass

                            # ==========================================================
                            # 2. GESTION DES PARTENAIRES (SÉCURITÉ ANTI-SPAM DÉSACTIVÉE !)
                            # ==========================================================
                            for streamer in tracked:
                                login = streamer["login"].lower()
                                if login in online_streams:
                                    stream = online_streams[login]
                                    live_id = stream["id"]

                                    # S'il est en live et que l'ID ne correspond pas à la BDD, ON FORCE LE TIR !
                                    if streamer.get("last_live_id") != live_id:
                                        partner_msg = f"**{stream['user_name']}** est en live sur **{stream['game_name']}**, foncez lui donner de la force !"
                                        logger.info(f"🔥 [MONITOR FORCE] Nouveau live de {stream['user_name']} détecté ! Tentative d'envoi Discord...")

                                        try:
                                            msg_id = await notification_service.send_discord_live_notification(
                                                channel_id=settings_row["streamers_channel_id"],
                                                channel_name=stream["user_name"],
                                                title=stream["title"],
                                                game=stream["game_name"],
                                                custom_message=partner_msg
                                            )
                                            logger.info(f"✅ [DISCORD SUCCÈS] Le message pour {stream['user_name']} a bien été posté ! (ID: {msg_id})")
                                            
                                            if msg_id:
                                                await conn.execute("UPDATE tracked_streamers SET last_live_id=$1, last_message_id=$2 WHERE id=$3", (live_id, str(msg_id), streamer["id"]))
                                        except Exception as e:
                                            logger.error(f"❌ [DISCORD CRASH] Le service Discord a planté pour {stream['user_name']} : {e}")
                                else:
                                    if streamer.get("last_live_id") != "":
                                        logger.info(f"💤 [MONITOR] {streamer['login']} hors ligne.")
                                        if streamer.get("last_message_id"):
                                            try:
                                                await notification_service.delete_discord_message(
                                                    channel_id=settings_row["streamers_channel_id"],
                                                    message_id=streamer["last_message_id"]
                                                )
                                            except Exception as e:
                                                logger.error(f"⚠️ Erreur suppression msg Discord : {e}")
                                        await conn.execute("UPDATE tracked_streamers SET last_live_id='', last_message_id='' WHERE id=$1", (streamer["id"],))

                        else:
                            logger.error(f"⚠️ [MONITOR] Erreur API Twitch : {resp.status}")

        except Exception as e:
            logger.error(f"❌ [MONITOR CRASH GLOBAL] : {e}")

        # Pause plus courte (30 secondes au lieu de 2 minutes) pour tester vite !
        await asyncio.sleep(30)
