"""
app/services/bot_health_service.py — Détection de crash + agrégation de statut pour le
dashboard de santé du bot (/admin/bot_health).

Détection de crash : un fichier marqueur est créé au démarrage et supprimé proprement
à l'arrêt (lifespan shutdown). S'il existe déjà au démarrage, c'est que le process
précédent ne s'est PAS arrêté proprement (crash, kill -9, OOM...) plutôt qu'un arrêt
normal (systemctl stop/restart envoie SIGTERM, qui déclenche le shutdown propre).
"""

import logging
import os
from datetime import datetime, timezone

import aiohttp

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.health")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CRASH_MARKER_PATH = os.path.join(BASE_DIR, ".bot_running_marker")


async def init_bot_health_table() -> None:
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_health (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                last_crash_at       TIMESTAMPTZ,
                last_crash_note     TEXT NOT NULL DEFAULT ''
            )
        """)
        await db.execute("INSERT INTO bot_health (id) VALUES (1) ON CONFLICT (id) DO NOTHING")


async def check_for_previous_crash_and_alert() -> None:
    """À appeler tout au début du lifespan, avant de recréer le marqueur."""
    if os.path.exists(CRASH_MARKER_PATH):
        logger.warning("⚠️ [HEALTH] Marqueur de démarrage trouvé au boot — le process précédent ne s'est pas arrêté proprement.")
        async with get_db_connection() as db:
            await db.execute(
                "UPDATE bot_health SET last_crash_at = NOW(), last_crash_note = ? WHERE id = 1",
                "Redémarrage inattendu détecté (process tué sans arrêt propre)"
            )
        await _alert_discord_crash()

    with open(CRASH_MARKER_PATH, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())


def clear_crash_marker() -> None:
    """À appeler dans le finally du lifespan, lors d'un arrêt propre."""
    if os.path.exists(CRASH_MARKER_PATH):
        os.remove(CRASH_MARKER_PATH)


async def _alert_discord_crash() -> None:
    try:
        from app.core.config import settings
        from app.services.discord_service import send_message_to_discord
        channel_id = settings.MODERATION_LOG_CHANNEL_ID
        if not channel_id:
            return
        embed = {
            "title": "🔥 Redémarrage inattendu du bot",
            "description": "Masthbot s'est relancé sans s'être arrêté proprement — probablement un crash. Vérifie les logs (`journalctl -u masthbot -n 100`).",
            "color": 0xEF4444,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await send_message_to_discord(channel_id, "⚠️ **Alerte bot**", embed=embed)
    except Exception as e:
        logger.error(f"❌ [HEALTH] Échec envoi alerte crash sur Discord : {e}")


async def get_bot_health_status() -> dict:
    from app.core.config import settings
    from app.services.twitch_service import twitch_bot
    from app.services.discord_mod_service import discord_mod_bot

    async with get_db_connection() as db:
        await db.execute("SELECT last_crash_at, last_crash_note FROM bot_health WHERE id = 1")
        crash_row = await db.fetchone()
        await db.execute("SELECT updated_at FROM youtube_state WHERE id = 1")
        yt_row = await db.fetchone()
        await db.execute("SELECT updated_at FROM tiktok_state WHERE id = 1")
        tt_row = await db.fetchone()

    obs_connected = False
    try:
        overlay_url = settings.OVERLAY_NODE_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{overlay_url}/api/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    obs_connected = bool(data.get("obs_connected"))
    except Exception as e:
        logger.warning(f"⚠️ [HEALTH] Impossible de joindre l'overlay Node pour le statut OBS : {e}")

    return {
        "twitch_connected": bool(getattr(twitch_bot, "is_ready_flag", False)),
        "discord_connected": discord_mod_bot.is_ready() if not discord_mod_bot.is_closed() else False,
        "obs_connected": obs_connected,
        "last_youtube_check": yt_row["updated_at"].isoformat() if yt_row and yt_row["updated_at"] else None,
        "last_tiktok_check": tt_row["updated_at"].isoformat() if tt_row and tt_row["updated_at"] else None,
        "last_crash_at": crash_row["last_crash_at"].isoformat() if crash_row and crash_row["last_crash_at"] else None,
        "last_crash_note": crash_row["last_crash_note"] if crash_row else "",
    }
