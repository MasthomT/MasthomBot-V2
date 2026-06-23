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
import time
from datetime import datetime, timezone

import aiohttp
import psutil

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.health")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CRASH_MARKER_PATH = os.path.join(BASE_DIR, ".bot_running_marker")
PROCESS_START_TIME = time.time()


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


def _format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days: parts.append(f"{days}j")
    if hours or days: parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


async def _get_db_status() -> dict:
    try:
        async with get_db_connection() as db:
            await db.execute("SELECT 1")
            counts = {}
            for table, key in [
                ("viewers", "viewers"), ("partners", "partners"), ("wheels", "wheels"),
                ("custom_commands", "custom_commands"), ("trophy_list", "trophies"),
                ("discord_warnings", "discord_warnings"),
            ]:
                try:
                    await db.execute(f"SELECT COUNT(*) AS n FROM {table}")
                    row = await db.fetchone()
                    counts[key] = row["n"] if row else 0
                except Exception:
                    counts[key] = None
        return {"connected": True, "counts": counts}
    except Exception as e:
        logger.error(f"❌ [HEALTH] Échec ping base de données : {e}")
        return {"connected": False, "counts": {}}


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

        await db.execute(
            "SELECT youtube_enabled, youtube_channel_id, youtube_discord_channel_id, "
            "tiktok_enabled, tiktok_username, tiktok_channel_id, "
            "leave_enabled, clear_enabled, sondage_enabled, warn_enabled, showtiktok_enabled "
            "FROM discord_features_settings WHERE id = 1"
        )
        features_row = await db.fetchone()

        await db.execute("SELECT enabled FROM discord_gate_settings WHERE id = 1")
        gate_row = await db.fetchone()
        await db.execute("SELECT enabled FROM discord_birthday_settings WHERE id = 1")
        bday_row = await db.fetchone()
        await db.execute("SELECT channel_enabled, dm_enabled FROM discord_welcome_settings WHERE id = 1")
        welcome_row = await db.fetchone()

    # --- OBS / overlay Node (via /api/health) ---
    obs_connected = False
    obs_scene = None
    obs_brb_active = None
    overlay_reachable = False
    overlay_uptime = None
    try:
        overlay_url = settings.OVERLAY_NODE_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{overlay_url}/api/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    overlay_reachable = True
                    data = await resp.json()
                    obs_connected = bool(data.get("obs_connected"))
                    obs_scene = data.get("current_scene")
                    obs_brb_active = data.get("brb_loop_active")
                    overlay_uptime = data.get("uptime_seconds")
    except Exception as e:
        logger.warning(f"⚠️ [HEALTH] Impossible de joindre l'overlay Node pour le statut OBS : {e}")

    # --- Twitch ---
    twitch_connected = bool(getattr(twitch_bot, "is_ready_flag", False))
    twitch_channel = getattr(twitch_bot, "channel_name", None)
    twitch_nick = getattr(twitch_bot, "nick", None)

    # --- Discord ---
    discord_ready = discord_mod_bot.is_ready() if not discord_mod_bot.is_closed() else False
    discord_guild_name = None
    discord_member_count = None
    discord_latency_ms = None
    if discord_ready and discord_mod_bot.guilds:
        guild = discord_mod_bot.guilds[0]
        discord_guild_name = guild.name
        discord_member_count = guild.member_count
        try:
            discord_latency_ms = round(discord_mod_bot.latency * 1000) if discord_mod_bot.latency else None
        except Exception:
            discord_latency_ms = None

    # --- Process (RAM, uptime) ---
    process = psutil.Process(os.getpid())
    mem_mb = round(process.memory_info().rss / (1024 * 1024), 1)
    uptime_seconds = time.time() - PROCESS_START_TIME

    db_status = await _get_db_status()

    return {
        # Connexions principales
        "twitch_connected": twitch_connected,
        "twitch_channel": twitch_channel,
        "twitch_nick": twitch_nick,
        "discord_connected": discord_ready,
        "discord_guild_name": discord_guild_name,
        "discord_member_count": discord_member_count,
        "discord_latency_ms": discord_latency_ms,
        "obs_connected": obs_connected,
        "obs_scene": obs_scene,
        "obs_brb_active": obs_brb_active,
        "overlay_node_reachable": overlay_reachable,
        "overlay_node_uptime": _format_uptime(overlay_uptime) if overlay_uptime else None,

        # Intégrations YouTube / TikTok
        "youtube_enabled": bool(features_row["youtube_enabled"]) if features_row else False,
        "youtube_channel_configured": bool(features_row["youtube_channel_id"]) if features_row else False,
        "last_youtube_check": yt_row["updated_at"].isoformat() if yt_row and yt_row["updated_at"] else None,
        "tiktok_enabled": bool(features_row["tiktok_enabled"]) if features_row else False,
        "tiktok_username": features_row["tiktok_username"] if features_row else None,
        "last_tiktok_check": tt_row["updated_at"].isoformat() if tt_row and tt_row["updated_at"] else None,
        "showtiktok_command_enabled": bool(features_row["showtiktok_enabled"]) if features_row else False,

        # Modules Discord
        "discord_gate_enabled": bool(gate_row["enabled"]) if gate_row else False,
        "discord_birthdays_enabled": bool(bday_row["enabled"]) if bday_row else False,
        "discord_welcome_channel_enabled": bool(welcome_row["channel_enabled"]) if welcome_row else False,
        "discord_welcome_dm_enabled": bool(welcome_row["dm_enabled"]) if welcome_row else False,

        # Process / DB
        "process_uptime": _format_uptime(uptime_seconds),
        "process_memory_mb": mem_mb,
        "db_connected": db_status["connected"],
        "db_counts": db_status["counts"],

        # Crash
        "last_crash_at": crash_row["last_crash_at"].isoformat() if crash_row and crash_row["last_crash_at"] else None,
        "last_crash_note": crash_row["last_crash_note"] if crash_row else "",
    }
