import asyncio
import aiohttp
import json
import logging
import sqlite3
import os
from datetime import datetime
import dotenv

from app.repositories import viewer_repo
from app.services.credits_service import credits_service

# Configuration du logger pour le débogage
logger = logging.getLogger("masthbot.eventsub")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

# =====================================================================
# 🛠️ UTILITAIRES DE JOURNALISATION ET CONFIGURATION
# =====================================================================

def log_stream_event(event_type, username, details):
    """Enregistre un événement dans la table stream_events pour l'historique du dashboard."""
    try:
        conn = sqlite3.connect(DB_PATH)
        # Nettoyage systématique du pseudo pour les recherches SQL
        clean_username = str(username or "Inconnu").strip()
        
        conn.execute(
            "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES (?, ?, ?, ?)",
            (event_type, clean_username, json.dumps(details), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()
        logger.info(f"🎉 [EVENT enregistré] {clean_username} -> {event_type.upper()}")
    except Exception as e:
        logger.error(f"❌ [DB EVENT ERROR] : {e}")

def get_current_xp_settings():
    """Récupère les paliers d'EXP configurés. Sécurité : remplace le vide par les valeurs par défaut."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
        conn.close()
        if row:
            d = dict(row)
            # Protection contre les valeurs NULL en base de données
            return {k: (v if v is not None else 0) for k, v in d.items()}
    except Exception as e:
        logger.error(f"❌ [SETTINGS ERROR] : {e}")
    
    # Valeurs de secours si la BDD est inaccessible ou vide
    return {
        "exp_sub_t1": 500, "exp_sub_t2": 1000, "exp_sub_t3": 2500,
        "exp_subgift_t1": 500, "exp_subgift_t2": 1000, "exp_subgift_t3": 2500,
        "exp_raid_per_viewer": 10
    }

# =====================================================================
# 📡 GESTION DES ABONNEMENTS WEBSOCKET (S'ABONNER AUX SIGNAUX TWITCH)
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

                    # --- A. INITIALISATION DE LA SESSION (On s'abonne à tout) ---
                    if msg_type == "session_welcome":
                        ws_id = data["payload"]["session"]["id"]
                        logger.info(f"🆔 Session EventSub validée : {ws_id}")

                        # Définition des conditions
                        c_broad = {"broadcaster_user_id": broadcaster_id}
                        c_raid = {"to_broadcaster_user_id": broadcaster_id}
                        c_mod = {"broadcaster_user_id": broadcaster_id, "moderator_user_id": broadcaster_id}

                        # Enregistrement des "oreilles" du bot
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.subscribe", "1", c_broad)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.subscription.gift", "1", c_broad)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.raid", "1", c_raid)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.cheer", "1", c_broad)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.follow", "2", c_mod)
                        await subscribe_to_event(session, client_id, token, ws_id, "channel.ban", "1", c_broad)

                    # --- B. RÉCEPTION D'UNE NOTIFICATION (L'ÉVÉNEMENT EST ARRIVÉ !) ---
                    elif msg_type == "notification":
                        sub_type = data["metadata"]["subscription_type"]
                        event = data["payload"]["event"]
                        conf = get_current_xp_settings()

                        # 1. GESTION DES SUBS (Abonnements personnels)
                        if sub_type == "channel.subscribe":
                            # On ignore si c'est un cadeau pour éviter de donner l'EXP deux fois
                            if not event.get("is_gift"):
                                user_name = event.get("user_name", "Inconnu")
                                user_id = event.get("user_id")
                                tier = event.get("tier", "1000")[0] # "1", "2" ou "3"
                                xp = int(conf.get(f"exp_sub_t{tier}") or 500)
                                
                                await viewer_repo.add_experience(user_id, user_name, xp, "SUB", f"Abonnement Tier {tier}")
                                log_stream_event("sub", user_name, {"tier": tier, "xp": xp})
                                credits_service.log_event("subscribers", user_name, f"Tier {tier}")

                        # 2. GESTION DES SUBGIFTS (Cadeaux offerts à la commu)
                        elif sub_type == "channel.subscription.gift":
                            if not event.get("is_anonymous"):
                                user_name = event.get("user_name", "Anonyme")
                                user_id = event.get("user_id")
                                count = int(event.get("total", 1))
                                tier = event.get("tier", "1000")[0]
                                val_per_sub = int(conf.get(f"exp_subgift_t{tier}") or 500)
                                total_xp = val_per_sub * count

                                credits_service.log_event("gifters", user_name, f"{count} Subs offerts")
                                await viewer_repo.add_experience(user_id, user_name, total_xp, "SUBGIFT", f"Offre {count} Subs Tier {tier}")
                                log_stream_event("subgift", user_name, {"count": count, "tier": tier, "xp": total_xp})

                        # 3. GESTION DES RAIDS (Le streamer qui arrive gagne l'EXP)
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

                        # 4. GESTION DES BITS (CHEERS) -> RÈGLE : 1 BIT = 5 XP
                        elif sub_type == "channel.cheer":
                            is_anon = event.get("is_anonymous", False)
                            user_name = "Anonyme" if is_anon else event.get("user_name", "Anonyme")
                            user_id = event.get("user_id")
                            bits = int(event.get("bits", 0))
                            
                            # CALCUL FIXE DEMANDÉ : 5 XP par Bit
                            total_xp = bits * 5

                            if not is_anon and user_id:
                                await viewer_repo.add_experience(user_id, user_name, total_xp, "CHEER", f"Don de {bits} bits")
                            
                            log_stream_event("cheer", user_name, {"bits": bits, "xp_gained": total_xp})
                            credits_service.log_event("bits", user_name, f"{bits} Bits")
                            logger.info(f"💎 [CHEER] {user_name} : {bits} bits -> +{total_xp} EXP (Barème 1:5)")

                        # 5. GESTION DES FOLLOWS
                        elif sub_type == "channel.follow":
                            user_name = event.get("user_name", "Inconnu")
                            log_stream_event("follow", user_name, {"msg": "Bienvenue !"})
                            credits_service.log_event("followers", user_name)

                        # 6. GESTION DES SANCTIONS (Logs modération)
                        elif sub_type == "channel.ban":
                            user_name = event.get("user_name", "Inconnu")
                            mod = event.get("moderator_user_name", "Modo")
                            if mod.lower() != bot_name:
                                action = "Ban" if event.get("is_permanent") else "Timeout"
                                reason = event.get("reason") or "Aucune raison"
                                log_stream_event("sanction", user_name, {"reason": f"{action} par {mod} : {reason}"})

                    # --- C. GESTION DE LA RECONNEXION (Demandée par Twitch) ---
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
