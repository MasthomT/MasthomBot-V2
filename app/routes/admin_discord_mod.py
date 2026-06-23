import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.security import require_admin
from app.services.discord_mod_service import discord_mod_bot

logger = logging.getLogger("masthbot.admin_discord_mod")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(prefix="/admin", tags=["admin_discord_mod"], dependencies=[Depends(require_admin)])


class SettingsPayload(BaseModel):
    banned_words_enabled: bool
    banned_words_action: str
    banned_words_duration: int
    spam_enabled: bool
    spam_limit: int
    spam_timeframe: int
    spam_action: str
    spam_duration: int


class WordPayload(BaseModel):
    word: str


class FeaturesPayload(BaseModel):
    tiktok_enabled: bool
    tiktok_username: str
    tiktok_channel_id: str
    leave_enabled: bool
    leave_channel_id: str
    youtube_enabled: bool
    youtube_channel_id: str
    youtube_discord_channel_id: str
    clear_enabled: bool = True
    sondage_enabled: bool = True
    warn_enabled: bool = True
    slowmode_enabled: bool = True
    lock_enabled: bool = True
    userinfo_enabled: bool = True
    giveaway_enabled: bool = True
    annonce_enabled: bool = True
    youtube_announce_message: str = "📺 **Nouvelle vidéo YouTube !**"
    tiktok_announce_message: str = "🎵 **Nouvelle vidéo TikTok !**"
    showtiktok_enabled: bool = True
    showtiktok_message: str = "🎵 TikTok affiché à l'écran ! — {title} {url}"


class WelcomePayload(BaseModel):
    channel_enabled: bool
    channel_id: str
    channel_message: str
    dm_enabled: bool
    dm_message: str
    embed_enabled: bool
    embed_title: str
    embed_description: str
    embed_color: str


class GateSettingsPayload(BaseModel):
    channel_id: str
    rules_text: str
    emoji: str
    general_role_id: str


class GateTogglePayload(BaseModel):
    enabled: bool


class SelfRolePayload(BaseModel):
    channel_id: str
    emoji: str
    role_id: str
    label: str = ""


class BirthdaySettingsPayload(BaseModel):
    enabled: bool
    channel_id: str
    message_template: str


@router.get("/discord_moderation", response_class=HTMLResponse)
async def discord_moderation_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/discord_moderation.html", context={})


@router.get("/api/discord_mod/settings")
async def get_settings():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_moderation_settings WHERE id = 1")
        row = await db.fetchone()
    return dict(row) if row else {}


@router.post("/api/discord_mod/settings")
async def save_settings(payload: SettingsPayload):
    if payload.banned_words_action not in ("delete", "timeout", "ban"):
        raise HTTPException(status_code=400, detail="Action invalide.")
    if payload.spam_action not in ("delete", "timeout", "ban"):
        raise HTTPException(status_code=400, detail="Action invalide.")

    async with get_db_connection() as db:
        await db.execute("""
            UPDATE discord_moderation_settings SET
                banned_words_enabled = ?, banned_words_action = ?, banned_words_duration = ?,
                spam_enabled = ?, spam_limit = ?, spam_timeframe = ?, spam_action = ?, spam_duration = ?
            WHERE id = 1
        """, payload.banned_words_enabled, payload.banned_words_action, payload.banned_words_duration,
            payload.spam_enabled, payload.spam_limit, payload.spam_timeframe, payload.spam_action, payload.spam_duration)
    return {"status": "ok"}


@router.get("/api/discord_mod/words")
async def list_words():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_banned_words ORDER BY word ASC")
        rows = await db.fetchall()
    return {"words": [dict(r) for r in rows]}


@router.post("/api/discord_mod/words")
async def add_word(payload: WordPayload):
    word = payload.word.strip().lower()
    if not word:
        raise HTTPException(status_code=400, detail="Mot vide.")
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO discord_banned_words (word) VALUES (?) ON CONFLICT (word) DO NOTHING",
            word
        )
    return {"status": "ok"}


@router.delete("/api/discord_mod/words/{word_id}")
async def delete_word(word_id: int):
    async with get_db_connection() as db:
        await db.execute("DELETE FROM discord_banned_words WHERE id = ?", word_id)
    return {"status": "ok"}


@router.get("/api/discord_mod/roles")
async def list_roles():
    """Liste les rôles du serveur Discord connecté, avec leur statut d'exemption."""
    if not discord_mod_bot.is_ready() or not discord_mod_bot.guilds:
        raise HTTPException(status_code=503, detail="Bot Discord non connecté pour le moment.")

    guild = discord_mod_bot.guilds[0]
    async with get_db_connection() as db:
        await db.execute("SELECT role_id FROM discord_exempt_roles")
        rows = await db.fetchall()
    exempt_ids = {r["role_id"] for r in rows}

    roles = [
        {"id": str(r.id), "name": r.name, "is_exempt": str(r.id) in exempt_ids}
        for r in sorted(guild.roles, key=lambda r: -r.position)
        if r.name != "@everyone"
    ]
    return {"guild_name": guild.name, "roles": roles}


@router.post("/api/discord_mod/roles/{role_id}/toggle")
async def toggle_role_exempt(role_id: str):
    async with get_db_connection() as db:
        await db.execute("SELECT id FROM discord_exempt_roles WHERE role_id = ?", role_id)
        existing = await db.fetchone()
        if existing:
            await db.execute("DELETE FROM discord_exempt_roles WHERE role_id = ?", role_id)
        else:
            role_name = ""
            if discord_mod_bot.is_ready() and discord_mod_bot.guilds:
                role = discord_mod_bot.guilds[0].get_role(int(role_id))
                role_name = role.name if role else ""
            await db.execute(
                "INSERT INTO discord_exempt_roles (role_id, role_name) VALUES (?, ?)",
                role_id, role_name
            )
    return {"status": "ok"}


@router.get("/api/discord_mod/channels")
async def list_channels():
    """Liste les salons textuels du serveur, pour les menus déroulants (TikTok, départs...)."""
    if not discord_mod_bot.is_ready() or not discord_mod_bot.guilds:
        raise HTTPException(status_code=503, detail="Bot Discord non connecté pour le moment.")

    guild = discord_mod_bot.guilds[0]
    channels = [
        {"id": str(c.id), "name": c.name}
        for c in guild.text_channels
    ]
    return {"guild_name": guild.name, "channels": channels}


@router.get("/api/discord_mod/features")
async def get_features():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_features_settings WHERE id = 1")
        row = await db.fetchone()
    return dict(row) if row else {}


@router.post("/api/discord_mod/features")
async def save_features(payload: FeaturesPayload):
    async with get_db_connection() as db:
        await db.execute("""
            UPDATE discord_features_settings SET
                tiktok_enabled = ?, tiktok_username = ?, tiktok_channel_id = ?,
                leave_enabled = ?, leave_channel_id = ?,
                youtube_enabled = ?, youtube_channel_id = ?, youtube_discord_channel_id = ?,
                clear_enabled = ?, sondage_enabled = ?,
                warn_enabled = ?, slowmode_enabled = ?, lock_enabled = ?,
                userinfo_enabled = ?, giveaway_enabled = ?, annonce_enabled = ?,
                youtube_announce_message = ?, tiktok_announce_message = ?,
                showtiktok_enabled = ?, showtiktok_message = ?
            WHERE id = 1
        """, payload.tiktok_enabled, payload.tiktok_username.lstrip("@").strip(), payload.tiktok_channel_id,
            payload.leave_enabled, payload.leave_channel_id,
            payload.youtube_enabled, payload.youtube_channel_id.strip(), payload.youtube_discord_channel_id,
            payload.clear_enabled, payload.sondage_enabled,
            payload.warn_enabled, payload.slowmode_enabled, payload.lock_enabled,
            payload.userinfo_enabled, payload.giveaway_enabled, payload.annonce_enabled,
            payload.youtube_announce_message, payload.tiktok_announce_message,
            payload.showtiktok_enabled, payload.showtiktok_message)
    return {"status": "ok"}


# ── Bienvenue ────────────────────────────────────────────────────────────────

@router.get("/api/discord_mod/welcome")
async def get_welcome():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_welcome_settings WHERE id = 1")
        row = await db.fetchone()
    return dict(row) if row else {}


@router.post("/api/discord_mod/welcome")
async def save_welcome(payload: WelcomePayload):
    async with get_db_connection() as db:
        await db.execute("""
            UPDATE discord_welcome_settings SET
                channel_enabled = ?, channel_id = ?, channel_message = ?,
                dm_enabled = ?, dm_message = ?,
                embed_enabled = ?, embed_title = ?, embed_description = ?, embed_color = ?
            WHERE id = 1
        """, payload.channel_enabled, payload.channel_id, payload.channel_message,
            payload.dm_enabled, payload.dm_message,
            payload.embed_enabled, payload.embed_title, payload.embed_description, payload.embed_color)
    return {"status": "ok"}


# ── Portail règlement ────────────────────────────────────────────────────────

@router.get("/api/discord_mod/gate")
async def get_gate():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_gate_settings WHERE id = 1")
        row = await db.fetchone()
    return dict(row) if row else {}


@router.post("/api/discord_mod/gate")
async def save_gate(payload: GateSettingsPayload):
    async with get_db_connection() as db:
        await db.execute("""
            UPDATE discord_gate_settings SET
                channel_id = ?, rules_text = ?, emoji = ?, general_role_id = ?
            WHERE id = 1
        """, payload.channel_id, payload.rules_text, payload.emoji, payload.general_role_id)
    return {"status": "ok"}


@router.post("/api/discord_mod/gate/publish")
async def publish_gate():
    """Poste (ou republie) le message de règlement et active le portail."""
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_gate_settings WHERE id = 1")
        gate = await db.fetchone()

    if not gate or not gate["channel_id"] or not gate["rules_text"]:
        raise HTTPException(status_code=400, detail="Configure le salon et le texte du règlement avant de publier.")
    if not gate["general_role_id"]:
        raise HTTPException(status_code=400, detail="Choisis le rôle général à attribuer avant de publier.")
    if not discord_mod_bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord non connecté pour le moment.")

    try:
        message_id = await discord_mod_bot.publish_rules_message(gate["channel_id"], gate["rules_text"], gate["emoji"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Échec de la publication : {e}")

    async with get_db_connection() as db:
        await db.execute(
            "UPDATE discord_gate_settings SET message_id = ?, enabled = TRUE WHERE id = 1",
            message_id
        )
    return {"status": "ok", "message_id": message_id}


@router.post("/api/discord_mod/gate/toggle")
async def toggle_gate(payload: GateTogglePayload):
    async with get_db_connection() as db:
        await db.execute("UPDATE discord_gate_settings SET enabled = ? WHERE id = 1", payload.enabled)
    return {"status": "ok"}


# ── Rôles auto-attribuables ──────────────────────────────────────────────────

@router.get("/api/discord_mod/self_roles")
async def list_self_roles():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_self_roles ORDER BY channel_id, id ASC")
        rows = await db.fetchall()
    return {"self_roles": [dict(r) for r in rows]}


@router.post("/api/discord_mod/self_roles")
async def add_self_role(payload: SelfRolePayload):
    role_name = ""
    if discord_mod_bot.is_ready() and discord_mod_bot.guilds:
        role = discord_mod_bot.guilds[0].get_role(int(payload.role_id))
        role_name = role.name if role else ""

    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO discord_self_roles (channel_id, emoji, role_id, role_name, label) VALUES (?, ?, ?, ?, ?)",
            payload.channel_id, payload.emoji, payload.role_id, role_name, payload.label or role_name
        )
    return {"status": "ok"}


@router.put("/api/discord_mod/self_roles/{role_entry_id}")
async def update_self_role(role_entry_id: int, payload: SelfRolePayload):
    role_name = ""
    if discord_mod_bot.is_ready() and discord_mod_bot.guilds:
        role = discord_mod_bot.guilds[0].get_role(int(payload.role_id))
        role_name = role.name if role else ""

    async with get_db_connection() as db:
        await db.execute(
            "UPDATE discord_self_roles SET channel_id = ?, emoji = ?, role_id = ?, role_name = ?, label = ? WHERE id = ?",
            payload.channel_id, payload.emoji, payload.role_id, role_name, payload.label or role_name, role_entry_id
        )
    return {"status": "ok"}


@router.delete("/api/discord_mod/self_roles/{role_entry_id}")
async def delete_self_role(role_entry_id: int):
    async with get_db_connection() as db:
        await db.execute("DELETE FROM discord_self_roles WHERE id = ?", role_entry_id)
    return {"status": "ok"}


@router.post("/api/discord_mod/self_roles/publish/{channel_id}")
async def publish_self_roles(channel_id: str):
    if not discord_mod_bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot Discord non connecté pour le moment.")
    try:
        message_id = await discord_mod_bot.publish_self_roles_panel(channel_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Échec de la publication : {e}")
    return {"status": "ok", "message_id": message_id}


# ── Anniversaires ────────────────────────────────────────────────────────────

@router.get("/api/discord_mod/birthdays")
async def get_birthdays_config():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM discord_birthday_settings WHERE id = 1")
        settings_row = await db.fetchone()
        await db.execute("SELECT * FROM discord_birthdays ORDER BY month ASC, day ASC")
        people = await db.fetchall()
    return {
        "settings": dict(settings_row) if settings_row else {},
        "birthdays": [dict(p) for p in people],
    }


@router.post("/api/discord_mod/birthdays/settings")
async def save_birthday_settings(payload: BirthdaySettingsPayload):
    async with get_db_connection() as db:
        await db.execute("""
            UPDATE discord_birthday_settings SET enabled = ?, channel_id = ?, message_template = ?
            WHERE id = 1
        """, payload.enabled, payload.channel_id, payload.message_template)
    return {"status": "ok"}


@router.delete("/api/discord_mod/birthdays/{birthday_id}")
async def delete_birthday(birthday_id: int):
    async with get_db_connection() as db:
        await db.execute("DELETE FROM discord_birthdays WHERE id = ?", birthday_id)
    return {"status": "ok"}
