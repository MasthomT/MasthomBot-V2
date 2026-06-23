"""
app/services/youtube_monitor.py — Annonce sur Discord chaque nouvelle vidéo YouTube.

Contrairement à TikTok, YouTube propose un flux RSS officiel et stable par
chaîne (`/feeds/videos.xml?channel_id=...`) — pas de scraping fragile ici.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import aiohttp

from app.core.database import get_db_connection
from app.services.discord_service import send_message_to_discord

logger = logging.getLogger("masthbot.youtube")

CHECK_INTERVAL_SECONDS = 10 * 60  # 10 minutes
ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"
YOUTUBE_RED = 0xFF0000


async def init_youtube_state_table() -> None:
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS youtube_state (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                last_video_id   TEXT,
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("INSERT INTO youtube_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING")


async def _get_youtube_settings() -> dict | None:
    async with get_db_connection() as db:
        await db.execute(
            "SELECT youtube_enabled, youtube_channel_id, youtube_discord_channel_id, youtube_announce_message "
            "FROM discord_features_settings WHERE id = 1"
        )
        return await db.fetchone()


async def _fetch_latest_videos(channel_id: str) -> list[dict]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            raw = await resp.text()

    root = ET.fromstring(raw)
    videos = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        video_id = entry.findtext(f"{YT_NS}videoId")
        title = entry.findtext(f"{ATOM_NS}title")
        link_el = entry.find(f"{ATOM_NS}link")
        url_ = link_el.get("href") if link_el is not None else f"https://www.youtube.com/watch?v={video_id}"
        author_el = entry.find(f"{ATOM_NS}author/{ATOM_NS}name")
        channel_name = author_el.text if author_el is not None else "YouTube"
        if video_id:
            videos.append({
                "id": video_id,
                "title": title or "Nouvelle vidéo",
                "url": url_,
                "channel_name": channel_name,
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            })
    return videos


async def check_new_youtube_video() -> None:
    feature_settings = await _get_youtube_settings()
    if not feature_settings or not feature_settings["youtube_enabled"]:
        return

    yt_channel_id = feature_settings["youtube_channel_id"]
    discord_channel_id = feature_settings["youtube_discord_channel_id"]
    announce_message = feature_settings["youtube_announce_message"] or "📺 **Nouvelle vidéo YouTube !**"
    if not yt_channel_id or not discord_channel_id:
        logger.warning("⚠️ [YOUTUBE] Activé mais ID de chaîne ou salon Discord manquant — configure ça depuis /admin/discord_moderation.")
        return

    try:
        videos = await _fetch_latest_videos(yt_channel_id)
    except Exception as e:
        logger.error(f"❌ [YOUTUBE] Échec récupération du flux RSS : {e}")
        return

    if not videos:
        return

    latest_id = videos[0]["id"]

    async with get_db_connection() as db:
        await db.execute("SELECT last_video_id FROM youtube_state WHERE id = 1")
        row = await db.fetchone()
        last_seen_id = row["last_video_id"] if row else None

        if last_seen_id is None:
            await db.execute("UPDATE youtube_state SET last_video_id = ?, updated_at = NOW() WHERE id = 1", latest_id)
            logger.info(f"📺 [YOUTUBE] Initialisation : dernière vidéo connue = {latest_id}")
            return

        if latest_id == last_seen_id:
            return

        new_videos = []
        found_last_seen = False
        for v in videos:
            if v["id"] == last_seen_id:
                found_last_seen = True
                break
            new_videos.append(v)

        if not found_last_seen:
            # last_seen_id ne correspond à AUCUNE vidéo du flux actuel (ex: l'ID de chaîne a été
            # changé entre deux vérifs, ou le flux RSS a tourné). Annoncer tout le flux d'un coup
            # serait un spam massif de vidéos potentiellement déjà vues — on se recale silencieusement
            # sur la plus récente à la place, comme une ré-initialisation.
            logger.warning(
                f"⚠️ [YOUTUBE] Dernière vidéo connue ({last_seen_id}) introuvable dans le flux actuel "
                f"— recalage silencieux sur {latest_id} sans annonce, pour éviter un spam."
            )
            await db.execute(
                "UPDATE youtube_state SET last_video_id = ?, updated_at = NOW() WHERE id = 1", latest_id
            )
            return

        new_videos.reverse()

        for v in new_videos:
            embed = {
                "title": v["title"],
                "url": v["url"],
                "color": YOUTUBE_RED,
                "author": {"name": v["channel_name"]},
                "image": {"url": v["thumbnail"]},
                "footer": {"text": "YouTube"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await send_message_to_discord(discord_channel_id, announce_message, embed=embed)
                logger.info(f"✅ [YOUTUBE] Annonce envoyée : {v['title']}")
            except Exception as e:
                logger.error(f"❌ [YOUTUBE] Échec envoi annonce Discord : {e}")

        await db.execute("UPDATE youtube_state SET last_video_id = ?, updated_at = NOW() WHERE id = 1", latest_id)


async def youtube_monitor_routine():
    logger.info("📺 [YOUTUBE] Démarrage de la surveillance des nouvelles vidéos.")
    await init_youtube_state_table()
    while True:
        try:
            await check_new_youtube_video()
        except Exception as e:
            logger.error(f"❌ [YOUTUBE] Erreur dans la boucle de surveillance : {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
