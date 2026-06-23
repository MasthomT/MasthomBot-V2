"""
app/services/tiktok_monitor.py — Annonce sur Discord chaque nouvelle vidéo TikTok.

TikTok n'a pas d'API publique officielle pour ça (contrairement à YouTube et
son flux RSS). On s'appuie sur yt-dlp (déjà utilisé ailleurs dans le projet
pour les clips Twitch), dont les mainteneurs suivent activement les
changements anti-scraping de TikTok — bien plus robuste qu'un scraping
artisanal. Ça reste un point plus fragile que le reste du bot par nature :
si TikTok change significativement son site, une mise à jour de yt-dlp peut
être nécessaire (`pip install -U yt-dlp`).
"""

import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone

import yt_dlp

from app.core.database import get_db_connection
from app.services.discord_service import send_message_to_discord

logger = logging.getLogger("masthbot.tiktok")

CHECK_INTERVAL_SECONDS = 20 * 60  # 20 minutes : pas besoin d'être instantané pour ce genre d'annonce
TIKTOK_PINK = 0xFE2C55


async def init_tiktok_state_table() -> None:
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tiktok_state (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                last_video_id   TEXT,
                last_video_url  TEXT,
                last_video_title TEXT,
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("INSERT INTO tiktok_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
        for col, coltype in [("last_video_url", "TEXT"), ("last_video_title", "TEXT")]:
            try:
                await db.execute(f"ALTER TABLE tiktok_state ADD COLUMN IF NOT EXISTS {col} {coltype}")
            except Exception:
                pass


async def _get_tiktok_settings() -> dict | None:
    """Réglages gérés depuis /admin/discord_moderation (table discord_features_settings),
    plus depuis tiktok_monitor pour éviter une dépendance circulaire avec discord_mod_service."""
    async with get_db_connection() as db:
        await db.execute(
            "SELECT tiktok_enabled, tiktok_username, tiktok_channel_id, tiktok_announce_message "
            "FROM discord_features_settings WHERE id = 1"
        )
        return await db.fetchone()


def _fetch_latest_videos(username: str, limit: int = 5) -> list[dict]:
    """Appel bloquant (yt-dlp) — à exécuter via asyncio.to_thread."""
    ydl_opts = {"quiet": True, "extract_flat": True, "playlistend": limit, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"https://www.tiktok.com/@{username}", download=False)
        return info.get("entries", []) or []


async def check_new_tiktok_video() -> None:
    feature_settings = await _get_tiktok_settings()
    if not feature_settings or not feature_settings["tiktok_enabled"]:
        return

    username = feature_settings["tiktok_username"]
    channel_id = feature_settings["tiktok_channel_id"]
    announce_message = feature_settings["tiktok_announce_message"] or "🎵 **Nouvelle vidéo TikTok !**"
    if not username or not channel_id:
        logger.warning("⚠️ [TIKTOK] Activé mais nom d'utilisateur ou salon manquant — configure ça depuis /admin/discord_moderation.")
        return

    try:
        videos = await asyncio.to_thread(_fetch_latest_videos, username)
    except Exception as e:
        logger.error(f"❌ [TIKTOK] Échec récupération des vidéos pour @{username} : {e}")
        return

    if not videos:
        logger.warning(f"⚠️ [TIKTOK] Aucune vidéo trouvée pour @{username} (compte privé/inexistant/protection anti-bot ?).")
        return

    latest = videos[0]
    latest_id = str(latest.get("id"))
    latest_title = (latest.get("title") or "Nouvelle vidéo").strip()
    latest_url = latest.get("url") or f"https://www.tiktok.com/@{username}/video/{latest_id}"

    async with get_db_connection() as db:
        await db.execute("SELECT last_video_id FROM tiktok_state WHERE id = 1")
        row = await db.fetchone()
        last_seen_id = row["last_video_id"] if row else None

        if last_seen_id is None:
            # Premier lancement : on mémorise la dernière vidéo SANS annoncer,
            # pour ne pas spammer Discord avec tout l'historique au démarrage.
            await db.execute(
                "UPDATE tiktok_state SET last_video_id = ?, last_video_url = ?, last_video_title = ?, updated_at = NOW() WHERE id = 1",
                latest_id, latest_url, latest_title
            )
            logger.info(f"🎵 [TIKTOK] Initialisation : dernière vidéo connue = {latest_id}")
            return

        if latest_id == last_seen_id:
            # Pas de nouvelle vidéo, mais on rafraîchit quand même l'horodatage de la dernière vérif
            # (affiché sur le dashboard de santé du bot) et l'url/titre au cas où ils auraient changé.
            await db.execute(
                "UPDATE tiktok_state SET last_video_url = ?, last_video_title = ?, updated_at = NOW() WHERE id = 1",
                latest_url, latest_title
            )
            return

        # Nouvelle(s) vidéo(s) : on annonce celles pas encore vues, de la plus ancienne à la plus récente
        # (pour avoir un ordre chronologique cohérent sur Discord si plusieurs sont sorties d'un coup).
        new_videos = []
        found_last_seen = False
        for v in videos:
            if str(v.get("id")) == last_seen_id:
                found_last_seen = True
                break
            new_videos.append(v)

        if not found_last_seen:
            # last_seen_id introuvable dans le flux actuel (changement de pseudo, vidéo supprimée
            # qui a fait défiler la liste...) : on se recale silencieusement plutôt que de spammer
            # tout le flux d'un coup.
            logger.warning(
                f"⚠️ [TIKTOK] Dernière vidéo connue ({last_seen_id}) introuvable dans le flux actuel "
                f"— recalage silencieux sur {latest_id} sans annonce, pour éviter un spam."
            )
            await db.execute(
                "UPDATE tiktok_state SET last_video_id = ?, last_video_url = ?, last_video_title = ?, updated_at = NOW() WHERE id = 1",
                latest_id, latest_url, latest_title
            )
            return

        new_videos.reverse()

        for v in new_videos:
            title = (v.get("title") or "Nouvelle vidéo").strip()
            url = v.get("url") or f"https://www.tiktok.com/@{username}/video/{v.get('id')}"
            thumbnails = v.get("thumbnails") or []
            thumbnail_url = v.get("thumbnail") or (thumbnails[-1].get("url") if thumbnails else None)

            embed = {
                "title": title,
                "url": url,
                "color": TIKTOK_PINK,
                "author": {"name": f"@{username}"},
                "footer": {"text": "TikTok"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if thumbnail_url:
                embed["image"] = {"url": thumbnail_url}

            try:
                await send_message_to_discord(channel_id, announce_message, embed=embed)
                logger.info(f"✅ [TIKTOK] Annonce envoyée : {title}")
            except Exception as e:
                logger.error(f"❌ [TIKTOK] Échec envoi annonce Discord : {e}")

        await db.execute(
            "UPDATE tiktok_state SET last_video_id = ?, last_video_url = ?, last_video_title = ?, updated_at = NOW() WHERE id = 1",
            latest_id, latest_url, latest_title
        )


async def tiktok_monitor_routine():
    logger.info("🎵 [TIKTOK] Démarrage de la surveillance des nouvelles vidéos.")
    await init_tiktok_state_table()
    while True:
        try:
            await check_new_tiktok_video()
        except Exception as e:
            logger.error(f"❌ [TIKTOK] Erreur dans la boucle de surveillance : {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


# ==========================================
# COMMANDE CHAT !showtiktok (overlay)
# ==========================================

async def get_last_known_tiktok() -> dict | None:
    """Dernière vidéo TikTok connue (mise à jour à chaque vérif périodique), pour !showtiktok sans lien."""
    async with get_db_connection() as db:
        await db.execute("SELECT last_video_id, last_video_url, last_video_title FROM tiktok_state WHERE id = 1")
        row = await db.fetchone()
    if not row or not row["last_video_url"]:
        return None
    return {"id": row["last_video_id"], "url": row["last_video_url"], "title": row["last_video_title"]}


TIKTOK_DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "masthbot_tiktok")
os.makedirs(TIKTOK_DOWNLOAD_DIR, exist_ok=True)


def _download_video(url: str) -> dict | None:
    """Appel bloquant (yt-dlp) — à exécuter via asyncio.to_thread.
    Télécharge réellement la vidéo plutôt que de juste extraire son URL CDN directe :
    rejouer l'URL CDN telle quelle (même avec les bons en-têtes capturés) renvoie un 403,
    le CDN TikTok faisant visiblement aussi une vérification d'empreinte de requête que
    yt-dlp seul sait satisfaire. Le fichier téléchargé est ensuite servi via /api/v1/tiktok_proxy."""
    file_id = uuid.uuid4().hex
    outtmpl = os.path.join(TIKTOK_DOWNLOAD_DIR, f"{file_id}.%(ext)s")
    ydl_opts = {"quiet": True, "no_warnings": True, "noprogress": True, "format": "best", "outtmpl": outtmpl}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        if not os.path.exists(filepath):
            return None
        return {
            "filepath": filepath,
            "title": info.get("title") or "Vidéo TikTok",
            "uploader": (info.get("uploader") or "").lower(),
        }


async def get_direct_tiktok_video(url: str) -> dict | None:
    """Résout n'importe quel lien TikTok (y compris vm.tiktok.com/vt.tiktok.com) et télécharge
    la vidéo localement pour qu'elle soit servie de façon fiable à l'overlay."""
    try:
        return await asyncio.to_thread(_download_video, url)
    except Exception as e:
        logger.error(f"❌ [TIKTOK] Échec téléchargement vidéo pour '{url}' : {e}")
        return None
