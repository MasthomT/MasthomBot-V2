"""
clip_discord_service.py

Surveille en continu les nouveaux clips Twitch et les poste sur Discord
dès qu'ils sont créés (polling toutes les 60s).
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timezone, timedelta
from app.core.database import get_db_connection
from app.core.config import settings

logger = logging.getLogger("masthbot.clip_discord")

POLL_INTERVAL = 60   # secondes entre chaque vérification
LOOKBACK_DAYS  = 30  # fenêtre de recherche — couvre les 30 derniers jours


async def _init_table():
    async with get_db_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS discord_notified_clips (
                clip_id     TEXT PRIMARY KEY,
                notified_at TIMESTAMP DEFAULT NOW()
            )
        """)


async def _fetch_recent_clips(session, headers: dict, broadcaster_id: str, since: datetime) -> list:
    """Récupère tous les clips créés depuis `since` (pagination automatique)."""
    all_clips: list = []
    cursor: str | None = None
    started_at = since.strftime('%Y-%m-%dT%H:%M:%SZ')

    while True:
        url = (
            f"https://api.twitch.tv/helix/clips"
            f"?broadcaster_id={broadcaster_id}"
            f"&first=100"
            f"&started_at={started_at}"
        )
        if cursor:
            url += f"&after={cursor}"
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.error(f"❌ [CLIP_DISCORD] Erreur API Twitch {resp.status}")
                    break
                body = await resp.json()
                page = body.get("data", [])
                all_clips.extend(page)
                cursor = body.get("pagination", {}).get("cursor")
                if not cursor or len(page) < 100:
                    break
        except Exception as e:
            logger.error(f"❌ [CLIP_DISCORD] Impossible de récupérer les clips : {e}")
            break

    return all_clips


async def _fetch_creator_info(session, headers: dict, creator_ids: list) -> dict:
    """Récupère les infos (nom, avatar) d'une liste de créateurs en une requête."""
    try:
        url = "https://api.twitch.tv/helix/users?" + "&".join(f"id={uid}" for uid in creator_ids)
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                return {
                    u["id"]: {"name": u["display_name"], "avatar": u["profile_image_url"]}
                    for u in (await resp.json()).get("data", [])
                }
    except Exception as e:
        logger.warning(f"⚠️ [CLIP_DISCORD] Impossible de récupérer les avatars : {e}")
    return {}


async def _post_clip(session, webhook_url: str, clip: dict, creator_info: dict):
    """Envoie un clip sur Discord via webhook et l'enregistre en DB."""
    creator_id   = clip["creator_id"]
    creator_name = creator_info.get(creator_id, {}).get("name", clip["creator_name"])
    avatar       = creator_info.get(creator_id, {}).get("avatar", "")

    # Les salons Forum Discord exigent thread_name (nouveau fil) ou thread_id (fil existant).
    # On crée un fil par clip en utilisant le titre du clip comme nom du fil.
    thread_name = (clip.get("title") or f"Clip de {creator_name}")[:100]

    payload = {
        "content":     clip["url"],
        "username":    creator_name,
        "avatar_url":  avatar,
        "thread_name": thread_name,
    }

    try:
        async with session.post(webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status in (200, 204):
                logger.info(f"✅ [CLIP_DISCORD] Posté : '{clip['title']}' par {creator_name}")
                async with get_db_connection() as conn:
                    await conn.execute(
                        "INSERT INTO discord_notified_clips (clip_id) VALUES ($1) ON CONFLICT DO NOTHING",
                        (clip["id"],)
                    )
            else:
                body = await resp.text()
                logger.error(f"❌ [CLIP_DISCORD] Webhook Discord {resp.status} : {body}")
    except Exception as e:
        logger.error(f"❌ [CLIP_DISCORD] Exception webhook : {e}")


async def clip_monitor_routine():
    """Boucle principale : vérifie les nouveaux clips toutes les 60s."""
    await _init_table()

    broadcaster_id = settings.TWITCH_BROADCASTER_ID
    webhook_url    = settings.DISCORD_CLIPS_WEBHOOK_URL
    client_id      = settings.TWITCH_CLIENT_ID
    token          = settings.TWITCH_OAUTH_TOKEN.replace("oauth:", "").strip()

    if not all([broadcaster_id, webhook_url, client_id, token]):
        logger.warning("⚠️ [CLIP_DISCORD] Config incomplète — monitor désactivé.")
        return

    logger.info("🎬 [CLIP_DISCORD] Monitor démarré — vérification toutes les 60s.")

    while True:
        try:
            since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}

            async with aiohttp.ClientSession() as session:
                clips = await _fetch_recent_clips(session, headers, broadcaster_id, since)

                if clips:
                    # Filtrer les clips déjà postés
                    async with get_db_connection() as conn:
                        rows = await (await conn.execute("SELECT clip_id FROM discord_notified_clips")).fetchall()
                        already_seen = {r["clip_id"] for r in rows}

                    new_clips = [c for c in clips if c["id"] not in already_seen]

                    if new_clips:
                        # Du plus ancien au plus récent
                        new_clips.sort(key=lambda c: c.get("created_at", ""))

                        logger.info(f"🎬 [CLIP_DISCORD] {len(new_clips)} nouveau(x) clip(s) détecté(s).")
                        creator_ids  = list({c["creator_id"] for c in new_clips})
                        creator_info = await _fetch_creator_info(session, headers, creator_ids)

                        for clip in new_clips:
                            await _post_clip(session, webhook_url, clip, creator_info)
                            await asyncio.sleep(1.5)  # anti rate-limit Discord

        except Exception as e:
            logger.error(f"❌ [CLIP_DISCORD] Erreur monitor : {e}")

        await asyncio.sleep(POLL_INTERVAL)
