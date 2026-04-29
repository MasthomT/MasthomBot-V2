import asyncio
import aiohttp
import json
import logging
import sqlite3
import os
import collections
from datetime import datetime
import dotenv

from app.repositories import viewer_repo
from app.services.credits_service import credits_service

# Configuration du logger pour le débogage
logger = logging.getLogger("masthbot.eventsub")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

# 🛡️ BOUCLIER ANTI-DOUBLONS (Garde en mémoire les 200 derniers ID d'événements Twitch)
processed_message_ids = collections.deque(maxlen=200)

# =====================================================================
# 🛠️ UTILITAIRES DE JOURNALISATION ET CONFIGURATION
# =====================================================================

def log_stream_event(event_type, username, details):
    """Enregistre un événement dans la table stream_events pour l'historique du dashboard."""
    try:
        conn = sqlite3.connect(DB_PATH)
        clean_username = str(username or "Inconnu").strip()

        # Formatage intelligent en français pour le Dashboard Vercel/Admin
        formatted_details = details
        if isinstance(details, dict):
            if event_type == "sub":
                if details.get("is_gift"):
                    formatted_details = f"A reçu un abonnement cadeau (Tier {details.get('tier', '1')})"
                else:
                    formatted_details = f"Abonnement Tier {details.get('tier', '1')} (+{details.get('xp', 0)} EXP)"
            elif event_type == "subgift":
                formatted_details = f"A offert {details.get('count', 1)} abonnement(s) Tier {details.get('tier', '1')} (+{details.get('xp', 0)} EXP)"
            elif event_type == "raid":
                formatted_details = f"Raid de {details.get('viewers', 0)} personnes (+{details.get('xp', 0)} EXP)"
            elif event_type == "cheer":
                formatted_details = f"Don de {details.get('bits', 0)} Bits (+{details.get('xp_gained', 0)} EXP)"
            elif event_type == "follow":
                formatted_details = details.get("msg", "Bienvenue !")
            elif event_type == "sanction":
                formatted_details = details.get("reason", "Sanction appliquée")
            else:
                formatted_details = json.dumps(details, ensure_ascii=False)

        conn.execute(
            "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES (?, ?, ?, ?)",
            (event_type, clean_username, str(formatted_details), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()
        logger.info(f"🎉 [EVENT enregistré] {clean_username} -> {event_type.upper()}")
    except Exception as e:
        logger.error(f"❌ [DB EVENT ERROR] : {e}")

def update_viewer_stat(user_id, username, stat_column, value, increment=True):
    """
    Met à jour spécifiquement les statistiques de trophées d'un viewer (Mois de sub, Bits, Cadeaux).
    - increment=True : Additionne la valeur (ex: pour les bits et subgifts)
    - increment=False : Écrase la valeur (ex: pour les mois de sub cumulés envoyés par Twitch)
    """
    if not user_id or not username:
        return
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if increment:
            query = f"""
                INSERT INTO viewers (twitch_id, username, {stat_column})
                VALUES (?, ?, ?)
                ON CONFLICT(twitch_id) DO UPDATE SET
                    {stat_column} = COALESCE({stat_column}, 0) + ?,
                    username = excluded.username
            """
            cursor.execute(query, (user_id, username, value, value))
        else:
            query = f"""
                INSERT INTO viewers (twitch_id, username, {stat_column})
                VALUES (?, ?, ?)
                ON CONFLICT(twitch_id) DO UPDATE SET
                    {stat_column} = ?,
                    username = excluded.username
            """
            cursor.execute(query, (user_id, username, value, value))
            
        conn.commit()
        conn.close()
        logger.info(f"🏆 [TROPHÉE MAJ] {username} -> {stat_column} mis à jour avec {value}.")
    except Exception as e:
        logger.error(f"❌ [DB TROPHY ERROR] Impossible de mettre à jour {stat_column} pour {username}: {e}")

def get_current_xp_settings():
    """Récupère les paliers d'EXP configurés. Sécurité : remplace le vide par les valeurs par défaut."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
        conn.close()
        if row:
            d = dict(row)
            return {k: (v if v is not None else 0) for k, v in d.items()}
    except Exception as e:
        logger.error(f"❌ [SETTINGS ERROR] : {e}")

    return {
        "exp_sub_t1": 500, "exp_sub_t2": 1000, "exp_sub_t3": 2500,
        "exp_subgift_t1": 500, "exp_subgift_t2": 1000, "exp_subgift_t3": 2500,
        "exp_raid_per_viewer": 10
    }

# =====================================================================
# 📡 GESTION DES ABONNEMENTS WEBSOCKET
# =====================================================================

async def subscribe_to_event(session, client_id, token, ws_session_id, sub_type, version, condition):
    """Envoie une requête à Twitch pour s'abonner à un événement précis."""
    url = "https://api.twitch.tv/helix/eventsub/subscriptions"
    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "type": sub_type,
        "version": version,
        "condition": condition,
        "transport": {
            "method": "websocket",
            "session_id": ws_session_id
        }
    }
    async with session.post(url, headers=headers, json=payload) as resp:
        if resp.status == 202:
            logger.info(f"✅ Abonnement validé : {sub_type} (v{version})")
        else:
            err = await resp.text()
            logger.error(f"❌ Échec abonnement {sub_type} : {err}")

# =====================================================================
# 🌀 BOUCLE PRINCIPALE EVENTSUB
# =====================================================================

async def eventsub_routine():
    """Gère la connexion permanente et le traitement des messages Twitch."""
    env = dotenv.dotenv_values("/home/masthom/BOT_V2/.env")
    client_id = env.get("TWITCH_CLIENT_ID", "").strip()
    token = env.get("TWITCH_OAUTH_TOKEN", "").replace("oauth:", "").strip()
    channel_name = env.get("TWITCH_CHANNEL", "masthom_").replace("#", "").strip()
    bot_name = env.get("TWITCH_BOT_USERNAME", "Felix").lower()

    if not client_id or not token:
        logger.error("❌ Identifiants Twitch manquants dans le .env. EventSub ne peut pas démarrer.")
        return

    async with aiohttp.ClientSession() as session:
        # 1. Récupération du Broadcaster ID
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        async with session.get(f"https://api.twitch.tv/helix/users?login={channel_name}", headers=headers) as resp:
            data = await resp.json()
            if not data.get("data") or len(data["data"]) == 0:
                logger.error(f"❌ Impossible de trouver l'ID Twitch pour {channel_name}")
                return
            broadcaster_id = data["data"][0]["id"]

        # 2. Ouverture du tunnel WebSocket avec Twitch
        async with session.ws_connect("wss://eventsub.wss.twitch.tv/ws") as ws:
            logger.info("📡 [WebSocket] Tunnel ouvert avec Twitch. Écoute des événements...")

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get("metadata", {}).get("message_type")
                    msg_id = data.get("metadata", {}).get("message_id")

                    # 🛡️ LE BOUCLIER ANTI-DOUBLONS ENTRE EN ACTION
                    if msg_id:
                        if msg_id in processed_message_ids:
                            logger.info(f"🛡️ [ANTI-DOUBLON] L'événement {msg_id} a été ignoré car déjà traité.")
                            continue 
                        processed_message_ids.append(msg_id)

                    # --- A. INITIALISATION DE LA SESSION ---
                    if msg_type == "session_welcome":
                        ws_id = data["payload"]["session"]["id"]
                        logger.info(f"🆔 Session EventSub validée : {ws_id}")

                        c_broad = {"broadcaster_user_id": broadcaster_id}
                        c_raid = {"to_broadcaster_user_id": broadcaster_id}
                        c_mod = {"broadcaster_user_id": broadcaster_id, "moderator_user_id": broadcaster_id}

                        await subscribe_to_event(session, client_id, token, ws_id, "channel.subscribe", "1", c_broad)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.subscription.message", "1", c_broad)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.subscription.gift", "1", c_broad)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.raid", "1", c_raid)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.cheer", "1", c_broad)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.follow", "2", c_mod)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.ban", "1", c_broad)

                    # --- B. RÉCEPTION D'UNE NOTIFICATION ---
                    elif msg_type == "notification":
                        sub_type = data["metadata"]["subscription_type"]
                        event = data["payload"]["event"]
                        conf = get_current_xp_settings()

                        # 1. GESTION DES SUBS ET RÉABONNEMENTS
                        if sub_type in ["channel.subscribe", "channel.subscription.message"]:
                            user_name = event.get("user_name", "Inconnu")
                            user_id = event.get("user_id")
                            tier = event.get("tier", "1000")[0] 
                            
                            # 🏆 AJOUT : Traque les mois cumulés (Twitch envoie le total direct)
                            cumulative_months = event.get("cumulative_months", 1)
                            update_viewer_stat(user_id, user_name, "sub_months", cumulative_months, increment=False)
                            
                            if not event.get("is_gift"):
                                xp = int(conf.get(f"exp_sub_t{tier}") or 500)
                                await viewer_repo.add_experience(user_id, user_name, xp, "SUB", f"Abonnement Tier {tier}")
                                log_stream_event("sub", user_name, {"tier": tier, "xp": xp, "is_gift": False})
                                credits_service.log_event("subscribers", user_name, f"Tier {tier}")
                            else:
                                log_stream_event("sub", user_name, {"tier": tier, "is_gift": True})
                                credits_service.log_event("subscribers", user_name, f"Cadeau Reçu")

                        # 2. GESTION DES SUBGIFTS
                        elif sub_type == "channel.subscription.gift":
                            if not event.get("is_anonymous"):
                                user_name = event.get("user_name", "Anonyme")
                                user_id = event.get("user_id")
                                count = int(event.get("total", 1))
                                tier = event.get("tier", "1000")[0]
                                val_per_sub = int(conf.get(f"exp_subgift_t{tier}") or 500)
                                total_xp = val_per_sub * count

                                # 🏆 AJOUT : Additionne les cadeaux offerts au total historique
                                update_viewer_stat(user_id, user_name, "gifts_count", count, increment=True)

                                credits_service.log_event("gifters", user_name, f"{count} Subs offerts")
                                await viewer_repo.add_experience(user_id, user_name, total_xp, "SUBGIFT", f"Offre {count} Subs Tier {tier}")
                                log_stream_event("subgift", user_name, {"count": count, "tier": tier, "xp": total_xp})

                        # 3. GESTION DES RAIDS
                        elif sub_type == "channel.raid":
                            raider_name = event.get("from_broadcaster_user_name", "Inconnu")
                            raider_id = event.get("from_broadcaster_user_id")
                            v_count = int(event.get("viewers", 0))
                            xp_per_head = int(conf.get("exp_raid_per_viewer") or 10)
                            total_xp = v_count * xp_per_head

                            if raider_id:
                                await viewer_repo.add_experience(raider_id, raider_name, total_xp, "RAID", f"Raid de {v_count} personnes")
                            log_stream_event("raid", raider_name, {"viewers": v_count, "xp": total_xp})
                            credits_service.log_event("raiders", raider_name, f"{v_count} Viewers")

                        # 4. GESTION DES BITS (CHEERS)
                        elif sub_type == "channel.cheer":
                            is_anon = event.get("is_anonymous", False)
                            user_name = "Anonyme" if is_anon else event.get("user_name", "Anonyme")
                            user_id = event.get("user_id")
                            bits = int(event.get("bits", 0))

                            total_xp = bits * 5

                            if not is_anon and user_id:
                                # 🏆 AJOUT : Additionne les bits donnés au total historique
                                update_viewer_stat(user_id, user_name, "bits_count", bits, increment=True)
                                await viewer_repo.add_experience(user_id, user_name, total_xp, "CHEER", f"Don de {bits} bits")

                            log_stream_event("cheer", user_name, {"bits": bits, "xp_gained": total_xp})
                            credits_service.log_event("bits", user_name, f"{bits} Bits")

                        # 5. GESTION DES FOLLOWS
                        elif sub_type == "channel.follow":
                            user_name = event.get("user_name", "Inconnu")
                            log_stream_event("follow", user_name, {"msg": "Bienvenue !"})
                            credits_service.log_event("followers", user_name)

                        # 6. GESTION DES SANCTIONS
                        elif sub_type == "channel.ban":
                            user_name = event.get("user_name", "Inconnu")
                            mod = event.get("moderator_user_name", "Modo")
                            if mod.lower() != bot_name:
                                action = "Ban" if event.get("is_permanent") else "Timeout"
                                reason = event.get("reason") or "Aucune raison"
                                log_stream_event("sanction", user_name, {"reason": f"{action} par {mod} : {reason}"})

                    # --- C. GESTION DE LA RECONNEXION ---
                    elif msg_type == "session_reconnect":
                        new_url = data["payload"]["session"]["reconnect_url"]
                        logger.info(f"🔄 Twitch demande une reconnexion : {new_url}")
                        break

                elif msg.type in [aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR]:
                    logger.warning("⚠️ WebSocket fermé ou erreur réseau. Relance de la routine...")
                    break

async def start_eventsub():
    """Lance la routine et assure la survie du service avec reconnexion auto."""
    while True:
        try:
            await eventsub_routine()
        except Exception as e:
            logger.error(f"🔥 [CRASH EVENTSUB] : {e}. Tentative de redémarrage dans 15 secondes...")
            await asyncio.sleep(15)
