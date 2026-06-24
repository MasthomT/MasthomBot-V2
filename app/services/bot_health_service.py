"""
app/services/bot_health_service.py — Détection de crash + agrégation de statut exhaustif
pour le dashboard de santé du bot (/admin/bot_health).
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


def _fmt_action(action: str, duration: int) -> str:
    labels = {"delete": "Suppression", "timeout": f"Timeout {duration}s", "ban": "Ban"}
    return labels.get(action, action)


async def _get_db_counts() -> dict:
    counts = {}
    try:
        async with get_db_connection() as db:
            await db.execute("SELECT 1")
            for table, key in [
                ("viewers", "viewers"),
                ("partners", "partners"),
                ("wheels", "wheels"),
                ("custom_commands", "custom_commands"),
                ("trophy_list", "trophies"),
                ("discord_warnings", "discord_warnings"),
                ("announcements", "announcements"),
                ("banned_words", "banned_words_twitch"),
                ("discord_banned_words", "banned_words_discord"),
                ("unfollows", "unfollows"),
                ("stream_events", "stream_events"),
                ("felixdle_words", "felixdle_words"),
            ]:
                try:
                    await db.execute(f"SELECT COUNT(*) AS n FROM {table}")
                    row = await db.fetchone()
                    counts[key] = row["n"] if row else 0
                except Exception:
                    counts[key] = None
        counts["_connected"] = True
    except Exception:
        counts["_connected"] = False
    return counts


async def get_bot_health_status() -> dict:
    from app.core.config import settings
    from app.services.twitch_service import twitch_bot
    from app.services.discord_mod_service import discord_mod_bot
    import app.services.eventsub_service as eventsub_svc

    # ── DB queries ────────────────────────────────────────────────────────────
    async with get_db_connection() as db:
        await db.execute("SELECT last_crash_at, last_crash_note FROM bot_health WHERE id = 1")
        crash_row = await db.fetchone()

        await db.execute("SELECT updated_at FROM youtube_state WHERE id = 1")
        yt_row = await db.fetchone()
        await db.execute("SELECT updated_at, last_video_url, last_video_title FROM tiktok_state WHERE id = 1")
        tt_row = await db.fetchone()

        await db.execute("""
            SELECT tiktok_enabled, tiktok_username, tiktok_channel_id,
                   leave_enabled, clear_enabled, sondage_enabled, warn_enabled,
                   slowmode_enabled, lock_enabled, userinfo_enabled,
                   giveaway_enabled, annonce_enabled,
                   youtube_enabled, youtube_channel_id, youtube_discord_channel_id,
                   showtiktok_enabled, showtiktok_message
            FROM discord_features_settings WHERE id = 1
        """)
        feat = await db.fetchone()

        await db.execute("""
            SELECT ai_enabled, enable_twitch, enable_discord, ai_can_poll,
                   discord_notify_enabled, discord_notify_message,
                   notif_live_channel_id, exp_per_message, exp_per_watchtime
            FROM settings WHERE id = 1
        """)
        cfg = await db.fetchone()

        await db.execute("""
            SELECT caps_enabled, links_enabled, spam_enabled, banned_words_enabled,
                   links_f_act, links_f_dur, links_nf_act, links_nf_dur,
                   caps_f_act, caps_nf_act, spam_f_act, spam_nf_act,
                   spam_limit, spam_timeframe, caps_min_length, caps_percent
            FROM moderation_settings WHERE id = 1
        """)
        mod_twitch = await db.fetchone()

        await db.execute("""
            SELECT banned_words_enabled, banned_words_action,
                   spam_enabled, spam_limit, spam_timeframe, spam_action
            FROM discord_moderation_settings WHERE id = 1
        """)
        mod_discord = await db.fetchone()

        await db.execute("SELECT enabled FROM discord_gate_settings WHERE id = 1")
        gate_row = await db.fetchone()
        await db.execute("SELECT enabled FROM discord_birthday_settings WHERE id = 1")
        bday_row = await db.fetchone()
        await db.execute("SELECT channel_enabled, dm_enabled FROM discord_welcome_settings WHERE id = 1")
        welcome_row = await db.fetchone()

        # Jeux actifs
        await db.execute("SELECT game_type, name FROM games_daily WHERE game_date = CURRENT_DATE")
        games_rows = await db.fetchall()
        await db.execute("SELECT word FROM felixdle_daily WHERE game_date = CURRENT_DATE")
        felixdle_row = await db.fetchone()

        # Annonces auto
        await db.execute("SELECT COUNT(*) AS n FROM announcements WHERE is_enabled = 1")
        ann_row = await db.fetchone()

    # ── Overlay Node / OBS ────────────────────────────────────────────────────
    obs_connected = False
    obs_scene = None
    obs_brb_active = None
    overlay_reachable = False
    overlay_uptime = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.OVERLAY_NODE_URL}/api/health",
                timeout=aiohttp.ClientTimeout(total=3)
            ) as resp:
                if resp.status == 200:
                    overlay_reachable = True
                    d = await resp.json()
                    obs_connected = bool(d.get("obs_connected"))
                    obs_scene = d.get("current_scene")
                    obs_brb_active = d.get("brb_loop_active")
                    overlay_uptime = d.get("uptime_seconds")
    except Exception:
        pass

    # ── Twitch IRC ────────────────────────────────────────────────────────────
    twitch_connected = bool(getattr(twitch_bot, "is_ready_flag", False))
    last_irc_at = getattr(twitch_bot, "_last_irc_at", None)
    irc_silence_min = round((time.time() - last_irc_at) / 60, 1) if last_irc_at else None

    # ── EventSub ──────────────────────────────────────────────────────────────
    eventsub_connected = eventsub_svc.eventsub_connected
    eventsub_last = eventsub_svc.eventsub_last_event_at
    eventsub_silence_min = round((time.time() - eventsub_last) / 60, 1) if eventsub_last else None

    # ── Discord ───────────────────────────────────────────────────────────────
    discord_ready = discord_mod_bot.is_ready() if not discord_mod_bot.is_closed() else False
    discord_guild_name = None
    discord_member_count = None
    discord_latency_ms = None
    if discord_ready and discord_mod_bot.guilds:
        guild = discord_mod_bot.guilds[0]
        discord_guild_name = guild.name
        discord_member_count = guild.member_count
        try:
            discord_latency_ms = round(discord_mod_bot.latency * 1000)
        except Exception:
            pass

    # ── Process ───────────────────────────────────────────────────────────────
    process = psutil.Process(os.getpid())
    mem_mb = round(process.memory_info().rss / (1024 * 1024), 1)
    uptime_seconds = time.time() - PROCESS_START_TIME

    db_counts = await _get_db_counts()

    def b(row, key, default=False):
        return bool(row[key]) if row and key in row.keys() else default

    return {
        # ── Connexions ──────────────────────────────────────────────────────
        "twitch_connected": twitch_connected,
        "twitch_channel": getattr(twitch_bot, "channel_name", None),
        "twitch_nick": getattr(twitch_bot, "nick", None),
        "irc_silence_min": irc_silence_min,

        "eventsub_connected": eventsub_connected,
        "eventsub_silence_min": eventsub_silence_min,

        "discord_connected": discord_ready,
        "discord_guild_name": discord_guild_name,
        "discord_member_count": discord_member_count,
        "discord_latency_ms": discord_latency_ms,

        "obs_connected": obs_connected,
        "obs_scene": obs_scene,
        "obs_brb_active": obs_brb_active,
        "overlay_node_reachable": overlay_reachable,
        "overlay_node_uptime": _format_uptime(overlay_uptime) if overlay_uptime else None,

        # ── Process / DB ────────────────────────────────────────────────────
        "process_uptime": _format_uptime(uptime_seconds),
        "process_memory_mb": mem_mb,
        "db_connected": db_counts.get("_connected", False),
        "db_counts": {k: v for k, v in db_counts.items() if not k.startswith("_")},

        # ── Modération Twitch ───────────────────────────────────────────────
        "mod_twitch_links": b(mod_twitch, "links_enabled"),
        "mod_twitch_links_1st": _fmt_action(mod_twitch["links_f_act"], mod_twitch["links_f_dur"]) if mod_twitch else "—",
        "mod_twitch_links_2nd": _fmt_action(mod_twitch["links_nf_act"], mod_twitch["links_nf_dur"]) if mod_twitch else "—",
        "mod_twitch_caps": b(mod_twitch, "caps_enabled"),
        "mod_twitch_caps_threshold": f"{mod_twitch['caps_percent']}% / {mod_twitch['caps_min_length']} cars" if mod_twitch else "—",
        "mod_twitch_spam": b(mod_twitch, "spam_enabled"),
        "mod_twitch_spam_limit": f"{mod_twitch['spam_limit']} msgs / {mod_twitch['spam_timeframe']}s" if mod_twitch else "—",
        "mod_twitch_words": b(mod_twitch, "banned_words_enabled"),
        "mod_twitch_words_count": db_counts.get("banned_words_twitch", 0),

        # ── Modération Discord ──────────────────────────────────────────────
        "mod_discord_words": b(mod_discord, "banned_words_enabled"),
        "mod_discord_words_action": mod_discord["banned_words_action"] if mod_discord else "—",
        "mod_discord_spam": b(mod_discord, "spam_enabled"),
        "mod_discord_spam_limit": f"{mod_discord['spam_limit']} msgs / {mod_discord['spam_timeframe']}s" if mod_discord else "—",
        "mod_discord_words_count": db_counts.get("banned_words_discord", 0),

        # ── Commandes / Modules Twitch ──────────────────────────────────────
        "ai_enabled": b(cfg, "ai_enabled"),
        "ai_can_poll": b(cfg, "ai_can_poll"),
        "showtiktok_enabled": b(feat, "showtiktok_enabled"),
        "sondage_enabled": b(feat, "sondage_enabled"),
        "giveaway_enabled": b(feat, "giveaway_enabled"),
        "annonce_enabled": b(feat, "annonce_enabled"),
        "announcements_active": ann_row["n"] if ann_row else 0,
        "exp_per_message": cfg["exp_per_message"] if cfg else 0,
        "exp_per_watchtime": cfg["exp_per_watchtime"] if cfg else 0,
        "discord_notify_enabled": b(cfg, "discord_notify_enabled"),

        # ── Modules Discord ─────────────────────────────────────────────────
        "discord_gate_enabled": b(gate_row, "enabled"),
        "discord_birthdays_enabled": b(bday_row, "enabled"),
        "discord_welcome_channel_enabled": b(welcome_row, "channel_enabled"),
        "discord_welcome_dm_enabled": b(welcome_row, "dm_enabled"),
        "discord_leave_enabled": b(feat, "leave_enabled"),
        "discord_clear_enabled": b(feat, "clear_enabled"),
        "discord_warn_enabled": b(feat, "warn_enabled"),
        "discord_slowmode_enabled": b(feat, "slowmode_enabled"),
        "discord_lock_enabled": b(feat, "lock_enabled"),
        "discord_userinfo_enabled": b(feat, "userinfo_enabled"),

        # ── YouTube ─────────────────────────────────────────────────────────
        "youtube_enabled": b(feat, "youtube_enabled"),
        "youtube_channel_configured": bool(feat["youtube_channel_id"]) if feat else False,
        "last_youtube_check": yt_row["updated_at"].isoformat() if yt_row and yt_row["updated_at"] else None,

        # ── TikTok ──────────────────────────────────────────────────────────
        "tiktok_enabled": b(feat, "tiktok_enabled"),
        "tiktok_username": feat["tiktok_username"] if feat else None,
        "last_tiktok_check": tt_row["updated_at"].isoformat() if tt_row and tt_row["updated_at"] else None,
        "last_tiktok_title": tt_row["last_video_title"] if tt_row else None,

        # ── Jeux ────────────────────────────────────────────────────────────
        "games_today": [dict(r) for r in games_rows] if games_rows else [],
        "felixdle_today": felixdle_row["word"] if felixdle_row else None,

        # ── Crash ────────────────────────────────────────────────────────────
        "last_crash_at": crash_row["last_crash_at"].isoformat() if crash_row and crash_row["last_crash_at"] else None,
        "last_crash_note": crash_row["last_crash_note"] if crash_row else "",
    }
