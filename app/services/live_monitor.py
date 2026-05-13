import asyncio
import aiohttp
import sqlite3
import logging
import dotenv
import os
from app.services.notification_service import notification_service

logger = logging.getLogger("masthbot.monitor")
DB_PATH = "/home/thomas/masthom/BOT_V2/bot_database.db"

def _upgrade_database_schema():
    """S'assure que les colonnes nécessaires existent dans la base de données."""
    conn = sqlite3.connect(DB_PATH)
    try:
        # Colonnes pour les partenaires
        conn.execute("ALTER TABLE tracked_streamers ADD COLUMN last_message_id TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    try:
        # Colonnes pour ton live perso
        conn.execute("ALTER TABLE settings ADD COLUMN personal_last_live_id TEXT DEFAULT ''")
        conn.execute("ALTER TABLE settings ADD COLUMN personal_last_message_id TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

async def check_twitch_lives_routine():
    """
    Surveille l'état des lives Twitch (Perso + Partenaires).
    Inclut une sécurité au démarrage pour ne pas renvoyer de notifs déjà existantes.
    """
    _upgrade_database_schema()

    # Flag pour ignorer l'envoi de messages lors du tout premier scan (reboot)
    first_run = True

    while True:
        try:
            # Rechargement des variables d'environnement à chaque cycle
            env_vars = dotenv.dotenv_values(".env")
            client_id = env_vars.get("TWITCH_CLIENT_ID", "").strip()
            token = env_vars.get("TWITCH_OAUTH_TOKEN", "").replace("oauth:", "").strip()
            my_channel = env_vars.get("TWITCH_CHANNEL", "masthom_").replace("#", "").strip()

            if not client_id or not token:
                logger.warning("⚠️ Identifiants Twitch manquants pour le moniteur.")
                await asyncio.sleep(60)
                continue

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            settings_row = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
            tracked = conn.execute("SELECT * FROM tracked_streamers WHERE is_active=1").fetchall()

            if not settings_row:
                conn.close()
                await asyncio.sleep(60)
                continue

            # On prépare la liste des logins à vérifier
            logins_to_check = [my_channel] + [s["login"] for s in tracked]

            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {token}"
            }
            url = f"https://api.twitch.tv/helix/streams?user_login={'&user_login='.join(logins_to_check)}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Dictionnaire des streams en ligne : {login: stream_data}
                        online_streams = {stream["user_login"].lower(): stream for stream in data.get("data", [])}

                        # ==========================================================
                        # 1. GESTION DE TON LIVE PERSONNEL
                        # ==========================================================
                        my_login = my_channel.lower()
                        if my_login in online_streams:
                            stream = online_streams[my_login]
                            live_id = stream["id"]

                            # Si c'est un nouveau live_id détecté
                            if settings_row["personal_last_live_id"] != live_id:
                                if first_run:
                                    # Reboot : on met à jour l'ID mais on ne notifie pas (Silence)
                                    logger.info(f"🤫 [MONITOR] Ton live est déjà en cours ({live_id}), synchronisation sans notif.")
                                    conn.execute("UPDATE settings SET personal_last_live_id=? WHERE id=1", (live_id,))
                                elif settings_row["discord_notify_enabled"] == 1:
                                    # C'est un vrai nouveau live pendant que le bot tourne
                                    logger.info(f"🚨 [MONITOR] Ton live commence ! Envoi notif Discord...")
                                    msg_id = await notification_service.send_discord_live_notification(
                                        channel_id=settings_row["notif_live_channel_id"],
                                        channel_name=stream["user_name"],
                                        title=stream["title"],
                                        game=stream["game_name"],
                                        custom_message=settings_row["discord_notify_message"]
                                    )
                                    if msg_id:
                                        conn.execute("UPDATE settings SET personal_last_live_id=?, personal_last_message_id=? WHERE id=1", (live_id, str(msg_id)))
                                conn.commit()
                        else:
                            # Tu es hors ligne
                            if settings_row["personal_last_live_id"] != "":
                                logger.info(f"💤 [MONITOR] Tu n'es plus en live. Conservation de ton message Discord.")
                                
                                # On ne supprime pas ton message Discord, mais on remet la base de données à zéro pour le prochain live
                                conn.execute("UPDATE settings SET personal_last_live_id='' WHERE id=1")
                                conn.commit()

                                # ---- 🎬 AJOUT POUR LE GÉNÉRIQUE DE FIN ----
                                # On réinitialise automatiquement le générique suite à la fin du live
                                try:
                                    from app.services.credits_service import credits_service
                                    credits_service.reset_session()
                                except Exception as e:
                                    logger.error(f"❌ Erreur reset générique auto : {e}")

                        # ==========================================================
                        # 2. GESTION DES PARTENAIRES (SURVEILLANCE)
                        # ==========================================================
                        for streamer in tracked:
                            login = streamer["login"].lower()
                            if login in online_streams:
                                stream = online_streams[login]
                                live_id = stream["id"]

                                # Si le live_id a changé (Nouveau live)
                                if streamer["last_live_id"] != live_id:
                                    if first_run:
                                        # Reboot : Sync sans bruit
                                        logger.info(f"🤫 [MONITOR] {stream['user_name']} déjà en live, sync effectuée.")
                                        conn.execute("UPDATE tracked_streamers SET last_live_id=? WHERE id=?", (live_id, streamer["id"]))
                                    else:
                                        # Nouveau live détecté pendant l'exécution
                                        partner_msg = f"**{stream['user_name']}** est en live sur **{{CATEGORIE}}**, foncez lui donner de la force !"
                                        logger.info(f"🚨 [MONITOR] Nouveau live de partenaire détecté : {stream['user_name']} !")

                                        msg_id = await notification_service.send_discord_live_notification(
                                            channel_id=settings_row["streamers_channel_id"],
                                            channel_name=stream["user_name"],
                                            title=stream["title"],
                                            game=stream["game_name"],
                                            custom_message=partner_msg
                                        )
                                        if msg_id:
                                            conn.execute("UPDATE tracked_streamers SET last_live_id=?, last_message_id=? WHERE id=?", (live_id, str(msg_id), streamer["id"]))
                                    conn.commit()
                            else:
                                # Streamer partenaire hors ligne
                                if streamer["last_live_id"] != "":
                                    logger.info(f"💤 [MONITOR] {streamer['login']} hors ligne. Suppression du message.")
                                    await notification_service.delete_discord_message(
                                        channel_id=settings_row["streamers_channel_id"],
                                        message_id=streamer["last_message_id"]
                                    )
                                    conn.execute("UPDATE tracked_streamers SET last_live_id='', last_message_id='' WHERE id=?", (streamer["id"],))
                                    conn.commit()
                    else:
                        logger.error(f"⚠️ [MONITOR] Erreur API Twitch : {resp.status}")

            conn.close()

            if first_run:
                logger.info("✨ [MONITOR] Synchronisation initiale terminée. Le bot est maintenant attentif aux nouveaux lives sans spammer.")
                first_run = False

        except Exception as e:
            logger.error(f"❌ [MONITOR] Erreur critique dans la routine : {e}")

        # On vérifie toutes les 2 minutes
        await asyncio.sleep(120)
