import asyncio
import aiohttp
import json
import logging
import os
import time
import collections
from datetime import datetime
import dotenv

# État global consultable par le dashboard de santé
eventsub_connected: bool = False
eventsub_last_event_at: float = 0.0

from app.core.database import get_db_connection
from app.repositories import viewer_repo
from app.services.credits_service import credits_service
from app.routes.overlays import trigger_overlay_event
from app.services import twitch_poll_state

logger = logging.getLogger("masthbot.eventsub")

processed_message_ids = collections.deque(maxlen=200)

async def log_stream_event(event_type, username, details):
    try:
        clean_username = str(username or "Inconnu").strip()
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
            elif event_type == "reward":
                formatted_details = f"Récompense récupérée : {details.get('reward_name', 'Inconnue')}"
            elif event_type == "sanction":
                formatted_details = details.get("reason", "Sanction appliquée")
            else:
                formatted_details = json.dumps(details, ensure_ascii=False)

        async with get_db_connection() as conn:
            await conn.execute(
                "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES ($1, $2, $3, NOW())",
                (event_type, username, str(details))
            )
        logger.info(f"🎉 [EVENT enregistré] {clean_username} -> {event_type.upper()}")
    except Exception as e:
        logger.error(f"❌ [DB EVENT ERROR] : {e}")

ALLOWED_STAT_COLUMNS = {"sub_months", "gifts_count", "bits_count", "rewards_claimed"}

async def update_viewer_stat(user_id, username, stat_column, value, increment=True):
    if not user_id or not username: return
    if stat_column not in ALLOWED_STAT_COLUMNS:
        logger.error(f"❌ [DB STAT ERROR] Colonne non autorisée : {stat_column}")
        return
    try:
        async with get_db_connection() as conn:
            if increment:
                query = f"""
                    INSERT INTO viewers (twitch_id, username, {stat_column})
                    VALUES (?, ?, ?)
                    ON CONFLICT(twitch_id) DO UPDATE SET
                        {stat_column} = COALESCE(viewers.{stat_column}, 0) + ?,
                        username = excluded.username
                """
                await conn.execute(query, (str(user_id), username, value, value))
            else:
                query = f"""
                    INSERT INTO viewers (twitch_id, username, {stat_column})
                    VALUES (?, ?, ?)
                    ON CONFLICT(twitch_id) DO UPDATE SET
                        {stat_column} = ?,
                        username = excluded.username
                """
                await conn.execute(query, (str(user_id), username, value, value))
        logger.info(f"🏆 [STAT MAJ] {username} -> {stat_column} mis à jour (+{value} si inc).")
    except Exception as e:
        logger.error(f"❌ [DB STAT ERROR] Impossible de mettre à jour {stat_column} pour {username}: {e}")

async def get_current_xp_settings():
    try:
        async with get_db_connection() as conn:
            cur = await conn.execute("SELECT * FROM settings WHERE id=1")
            row = await cur.fetchone()
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

async def subscribe_to_event(session, client_id, token, ws_session_id, sub_type, version, condition):
    url = "https://api.twitch.tv/helix/eventsub/subscriptions"
    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "type": sub_type, "version": version, "condition": condition,
        "transport": { "method": "websocket", "session_id": ws_session_id }
    }
    async with session.post(url, headers=headers, json=payload) as resp:
        if resp.status == 202:
            logger.info(f"✅ Abonnement actif : {sub_type}")
        else:
            err = await resp.text()
            logger.error(f"❌ Échec abonnement {sub_type} : {err}")

async def eventsub_routine():
    env = dotenv.dotenv_values("/home/thomas/masthom/BOT_V2/.env")
    client_id = env.get("TWITCH_CLIENT_ID", "").strip()
    token = env.get("TWITCH_OAUTH_TOKEN", "").replace("oauth:", "").strip()
    channel_name = env.get("TWITCH_CHANNEL", "").replace("#", "").strip()
    bot_name = env.get("TWITCH_BOT_USERNAME", "Felix").lower()

    if not client_id or not token:
        logger.error("❌ Identifiants Twitch manquants dans le .env.")
        return

    async with aiohttp.ClientSession() as session:
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        async with session.get(f"https://api.twitch.tv/helix/users?login={channel_name}", headers=headers) as resp:
            data = await resp.json()
            if not data.get("data"):
                return
            broadcaster_id = data["data"][0]["id"]

        ws_url = "wss://eventsub.wss.twitch.tv/ws"
        already_subscribed = False  # un session_reconnect garde les abonnements existants, pas besoin de les recréer

        while True:
            reconnect_to = None
            async with session.ws_connect(ws_url, heartbeat=20) as ws:
                logger.info("📡 [WebSocket] Connexion établie. Écoute du direct lancée...")
                global eventsub_connected, eventsub_last_event_at
                eventsub_connected = True
                async for msg in ws:
                    eventsub_last_event_at = time.time()
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        msg_type = data.get("metadata", {}).get("message_type")
                        msg_id = data.get("metadata", {}).get("message_id")

                        if msg_id:
                            if msg_id in processed_message_ids: continue
                            processed_message_ids.append(msg_id)

                        if msg_type == "session_welcome":
                            ws_id = data["payload"]["session"]["id"]
                            logger.info(f"🆔 Session EventSub validée : {ws_id}")

                            if not already_subscribed:
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
                                await subscribe_to_event(session, client_id, token, ws_id, "channel.channel_points_custom_reward_redemption.add", "1", c_broad)
                                await subscribe_to_event(session, client_id, token, ws_id, "channel.poll.begin", "1", c_broad)
                                await subscribe_to_event(session, client_id, token, ws_id, "channel.poll.progress", "1", c_broad)
                                await subscribe_to_event(session, client_id, token, ws_id, "channel.poll.end", "1", c_broad)
                                await subscribe_to_event(session, client_id, token, ws_id, "channel.prediction.begin", "1", c_broad)
                                await subscribe_to_event(session, client_id, token, ws_id, "channel.prediction.progress", "1", c_broad)
                                await subscribe_to_event(session, client_id, token, ws_id, "channel.prediction.end", "1", c_broad)
                                already_subscribed = True
                            else:
                                logger.info("🔄 Reconnexion EventSub terminée — abonnements déjà actifs, pas de resouscription.")

                        elif msg_type == "notification":
                            sub_type = data["metadata"]["subscription_type"]
                            event = data["payload"]["event"]
                            conf = await get_current_xp_settings()

                            if sub_type in ["channel.subscribe", "channel.subscription.message"]:
                                user_name = event.get("user_name", "Inconnu")
                                user_id = event.get("user_id")
                                tier = event.get("tier", "1000")[0] 
                            
                                cumulative_months = event.get("cumulative_months", 1)
                                await update_viewer_stat(user_id, user_name, "sub_months", cumulative_months, increment=False)

                                if not event.get("is_gift"):
                                    # Vrai sub (nouveau ou resub) → label "dernier sub" + XP + générique
                                    from app.services.label_service import write_label
                                    write_label("dernier_sub.txt", f"{user_name} | {cumulative_months} mois")
                                    xp = int(conf.get(f"exp_sub_t{tier}") or 500)
                                    await viewer_repo.add_experience(user_id, user_name, xp, "SUB", f"Abonnement Tier {tier}")
                                    await log_stream_event("sub", user_name, {"tier": tier, "xp": xp, "is_gift": False})
                                    credits_service.log_event("subscribers", user_name, str(cumulative_months))
                                else:
                                    # Sub OFFERT : le destinataire n'apparaît PAS dans "dernier sub"
                                    # (le donateur est géré par channel.subscription.gift). On l'ajoute
                                    # quand même au générique comme abonné présent sur le live.
                                    await log_stream_event("sub", user_name, {"tier": tier, "is_gift": True})
                                    credits_service.log_event("subscribers", user_name, str(cumulative_months))

                            elif sub_type == "channel.subscription.gift":
                                if not event.get("is_anonymous"):
                                    user_name = event.get("user_name", "Anonyme")
                                    user_id = event.get("user_id")
                                    count = int(event.get("total", 1))
                                    tier = event.get("tier", "1000")[0]
                                    val_per_sub = int(conf.get(f"exp_subgift_t{tier}") or 500)
                                    total_xp = val_per_sub * count

                                    from app.services.label_service import write_label
                                    write_label("dernier_subgift.txt", f"{user_name} | {count} subgifts")

                                    await update_viewer_stat(user_id, user_name, "gifts_count", count, increment=True)

                                    credits_service.log_event("gifters", user_name, f"{count} Subs offerts")
                                    await viewer_repo.add_experience(user_id, user_name, total_xp, "SUBGIFT", f"Offre {count} Subs Tier {tier}")
                                    await log_stream_event("subgift", user_name, {"count": count, "tier": tier, "xp": total_xp})

                            elif sub_type == "channel.raid":
                                raider_name = event.get("from_broadcaster_user_name", "Inconnu")
                                raider_id = event.get("from_broadcaster_user_id")
                                v_count = int(event.get("viewers", 0))
                                xp_per_head = int(conf.get("exp_raid_per_viewer") or 10)
                                total_xp = v_count * xp_per_head

                                from app.services.label_service import write_label
                                write_label("dernier_raid.txt", f"{raider_name} | {v_count} viewers")

                                if raider_id:
                                    await viewer_repo.add_experience(raider_id, raider_name, total_xp, "RAID", f"Raid de {v_count} personnes")
                                await log_stream_event("raid", raider_name, {"viewers": v_count, "xp": total_xp})
                                credits_service.log_event("raiders", raider_name, f"{v_count} Viewers")

                            elif sub_type == "channel.cheer":
                                is_anon = event.get("is_anonymous", False)
                                user_name = "Anonyme" if is_anon else event.get("user_name", "Anonyme")
                                user_id = event.get("user_id")
                                bits = int(event.get("bits", 0))
                                total_xp = bits * 5

                                from app.services.label_service import write_label
                                write_label("dernier_bits.txt", f"{user_name} | {bits} bits")

                                if not is_anon and user_id:
                                    await update_viewer_stat(user_id, user_name, "bits_count", bits, increment=True)
                                    await viewer_repo.add_experience(user_id, user_name, total_xp, "CHEER", f"Don de {bits} bits")

                                await log_stream_event("cheer", user_name, {"bits": bits, "xp_gained": total_xp})
                                credits_service.log_event("bits", user_name, f"{bits} Bits")

                            elif sub_type == "channel.channel_points_custom_reward_redemption.add":
                                user_name = event.get("user_name", "Inconnu")
                                user_id = event.get("user_id")
                                reward_title = event.get("reward", {}).get("title", "Inconnue")

                                await update_viewer_stat(user_id, user_name, "rewards_claimed", 1, increment=True)
                                await log_stream_event("reward", user_name, {"reward_name": reward_title})

                                if reward_title == "Polaroïd":
                                    from app.services.polaroid_service import send_polaroid
                                    asyncio.create_task(send_polaroid(user_name, event.get("user_input", "")))

                            elif sub_type == "channel.follow":
                                user_name = event.get("user_name", "Inconnu")
                                from app.services.label_service import write_label
                                write_label("dernier_follow.txt", f"{user_name}")
                                await log_stream_event("follow", user_name, {"msg": "Bienvenue !"})
                                credits_service.log_event("followers", user_name)

                            elif sub_type == "channel.ban":
                                user_name = event.get("user_name", "Inconnu")
                                mod = event.get("moderator_user_name", "Modo")
                                if mod.lower() != bot_name:
                                    action = "Ban" if event.get("is_permanent") else "Timeout"
                                    reason = event.get("reason") or "Aucune raison"
                                    await log_stream_event("sanction", user_name, {"reason": f"{action} par {mod} : {reason}"})

                            elif sub_type in [
                                "channel.poll.begin", "channel.poll.progress", "channel.poll.end",
                                "channel.prediction.begin", "channel.prediction.progress", "channel.prediction.end"
                            ]:
                                import app.services.twitch_poll_state as poll_state
                                from app.routes.overlays import trigger_overlay_event

                                is_prediction = "prediction" in sub_type
                                is_end_event = "end" in sub_type
                                is_begin_event = "begin" in sub_type 
                                status = "end" if is_end_event else "update"
                            
                                if is_begin_event:
                                    poll_state.chat_votes = {1: 0, 2: 0, 3: 0, 4: 0}
                            
                                title = event.get("title", "")
                                ends_at = event.get("locks_at") if is_prediction else event.get("ends_at")
                                total_votes = 0
                                choices = []
                            
                                raw_choices = event.get("outcomes", []) if is_prediction else event.get("choices", [])
                                for c in raw_choices:
                                    title_choice = c.get("title", "")
                                    native_votes = c.get("channel_points", 0) if is_prediction else c.get("votes", 0) + c.get("channel_points_votes", 0)
                                    total_votes += native_votes
                                    choices.append({"title": title_choice, "votes": native_votes})

                                try:
                                    from app.services.twitch_service import twitch_bot 
                                    channel = twitch_bot.get_channel(twitch_bot.channel_name)
                                
                                    if channel:
                                        prefixe = "🔮 PRÉDICTION" if is_prediction else "📊 SONDAGE"
                                        if is_begin_event:
                                            await channel.send(f"{prefixe} EN COURS : {title} ! Participez en haut du t'chat ! ⏳")
                                        elif is_end_event:
                                            if poll_state.current_twitch_poll is not None:
                                                if total_votes > 0:
                                                    winner = max(choices, key=lambda x: x["votes"])
                                                    pct = round((winner["votes"] / total_votes) * 100)
                                                    await channel.send(f"✅ {prefixe} TERMINÉ : {title} | 🏆 Gagnant : {winner['title']} avec {pct}% des votes ! GG !")
                                                else:
                                                    await channel.send(f"✅ {prefixe} TERMINÉ : {title} | 🤷‍♂️ Aucun participant pour cette fois !")
                                except Exception as e:
                                    print(f"⚠️ Erreur chat (Sondage) : {e}")

                                if is_end_event:
                                    final_poll_data = {
                                        "title": f"✅ {title} (Terminé)", "total_votes": total_votes,
                                        "is_prediction": is_prediction, "choices": choices, "ends_at": ends_at
                                    }
                                    await trigger_overlay_event({"type": "twitch_event_end", "payload": final_poll_data})
                                    poll_state.current_twitch_poll = None
                                else:
                                    poll_state.current_twitch_poll = {
                                        "title": title, "total_votes": total_votes, "is_prediction": is_prediction,
                                        "choices": choices, "ends_at": ends_at
                                    }
                                    await trigger_overlay_event({"type": f"twitch_event_{status}", "payload": poll_state.current_twitch_poll})

                        elif msg_type == "session_reconnect":
                            reconnect_to = data["payload"]["session"]["reconnect_url"]
                            logger.info(f"🔄 Reconnexion requise : {reconnect_to}")
                            break
                    elif msg.type in [aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR]:
                        break

            if reconnect_to:
                # Twitch demande de basculer vers cette URL précise pour garder les abonnements
                # existants — pas besoin de se resouscrire (cf. already_subscribed plus haut).
                ws_url = reconnect_to
                continue
            break

async def start_eventsub():
    global eventsub_connected
    while True:
        try:
            await eventsub_routine()
        except Exception as e:
            logger.error(f"🔥 [CRASH] : {e}. Redémarrage dans 15s...")
            eventsub_connected = False
            await asyncio.sleep(15)
