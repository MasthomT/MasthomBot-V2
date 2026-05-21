import os
import psutil
import time
import aiohttp
import dotenv
import json

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.database import get_db_connection
from app.core.config import settings
from app.services.shoutout_service import shoutout_service

import logging
logger = logging.getLogger("masthbot.admin")

router = APIRouter(prefix="/admin", tags=["admin"])

# --- CONFIGURATION DES TONS ---
VRAIS_TONS = {
    "neutre": "Tu es Félix, un assistant félin calme et posé.",
    "pervers": "Tu es Félix, un véritable petit chaton pervers, tu aimes faire des allusions et draguer tout ce qui bouge. Tes réponses sont pleines de sous-entendus coquins et tu n'hésites pas à être provocateur.",
    "humoristique": "Tu es Félix, le chat comique. Tes réponses sont pleines d'humour, de jeux de mots et d'absurdités légères.",
    "adorable": "Tu es Félix, le chaton le plus ADORABLE qui existe, tu apportes du soutien aux viewers et tu es toujours adorable avec eux.",
    "sérieux": "Tu es Félix, le conseiller sage. Tes réponses sont structurées et professionnelles.",
    "troll_ultime": "Tu es Félix le Troll Suprême. Tu te moques gentiment de tout, tu provoques de manière drôle.",
    "génie_grincheux": "Tu es Félix, un génie de l'informatique blasé et un peu grincheux.",
    "gameur_rétro": "Tu es Félix, un bot gamer bloqué dans les années 90.",
    "maitre_zen": "Tu es Maître Félix, un chat sage et philosophe.",
    "bad_bot": "Tu es Félix, le 'bad boy' charismatique.",
    "charmeur": "Tu es Félix, le charmeur suave."
}

# --- CONFIGURATION DES CHEMINS ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- ROUTES DE NAVIGATION (GET) ---

@router.get("/")
@router.get("/index")
@router.get("/index.html")
async def read_admin(request: Request):
    """Tableau de bord principal avec statistiques système réelles."""
    try:
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m"
        
        stats = {
            "uptime": uptime_str,
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "twitch_status": "En ligne"
        }
    except Exception:
        stats = {"uptime": "Inconnu", "cpu": 0, "ram": 0, "twitch_status": "Erreur"}
        
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={"stats": stats}
    )

@router.get("/data_logs.html")
async def admin_stats(request: Request):
    try:
        async with get_db_connection() as conn:
            c = await conn.execute("SELECT * FROM viewers ORDER BY messages DESC LIMIT 10")
            top_viewers = await c.fetchall()
            
        uptime_seconds = time.time() - psutil.boot_time()
        
        return templates.TemplateResponse("admin/data_logs.html", {
            "request": request,
            "top_viewers": [dict(v) for v in top_viewers],
            "twitch_stats": {"username": settings.TWITCH_CHANNEL.replace("#", ""), "status": "En ligne"},
            "discord_stats": {"server_name": os.getenv("GUILD_ID", "Serveur Masthom"), "member_count": "N/A"},
            "process_stats": {
                "uptime": f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m",
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent
            },
            "bot_status": {"ping": "24", "status": "Connecté"},
            "tasks_status": {"own_channel": "Actif", "external_channels": "Actif"},
            "event_counts": {
                "follow": 0, "sub": 0, "subgift": 0, "resub": 0, "bits": 0, "raid": 0
            }
        })
    except Exception as e:
        logger.error(f"Erreur data_logs: {e}")
        return HTMLResponse("Erreur interne", status_code=500)

@router.get("/giveaway.html")
async def admin_giveaway(request: Request):
    return templates.TemplateResponse(request=request, name="admin/giveaway.html", context={})

@router.get("/commands.html")
async def admin_commands(request: Request):
    return templates.TemplateResponse(request=request, name="admin/commands.html", context={})

# --- LOGIQUE DES OUTILS (SO, REPLAY, BRB) ---

@router.get("/shoutout", response_class=HTMLResponse)
@router.get("/shoutout.html", response_class=HTMLResponse)
async def admin_shoutout_page(request: Request):
    """Page de contrôle pour les SO, Replays et scènes d'overlay."""
    return templates.TemplateResponse(request=request, name="admin/shoutout.html", context={"request": request})

@router.post("/execute_tool")
async def execute_tool(
    action: str = Form(...),
    target: str = Form(None),
    clip_link: str = Form(None),
    query: str = Form(None)
):
    """Déclenche les actions de stream via les services ou l'overlay Node.js."""
    overlay_url = settings.OVERLAY_NODE_URL

    async with aiohttp.ClientSession() as session:
        if action == "shoutout" and target:
            clean_target = target.replace('@', '').strip()
            try:
                await shoutout_service.trigger_shoutout(target=clean_target, slug=clip_link)
            except Exception as e:
                logger.error(f"⚠️ Erreur Service SO : {e}")
        
        elif action == "replay":
            try:
                await shoutout_service.trigger_replay(slug=clip_link, query=query)
            except Exception as e:
                logger.error(f"⚠️ Erreur Service Replay : {e}")
            
        elif action == "brb_on":
            try:
                await session.post(f"{overlay_url}/api/overlay/scene", json={"scene": "brb"})
            except Exception as e:
                logger.error(f"❌ Erreur de connexion au serveur Node (3005) : {e}")
            
        elif action == "brb_off":
            try:
                await session.post(f"{overlay_url}/api/overlay/scene", json={"scene": "main"})
            except Exception as e:
                logger.error(f"❌ Erreur de connexion au serveur Node (3005) : {e}")

    return RedirectResponse(url="/admin/shoutout", status_code=303)

@router.get("/notifications")
async def get_notifications(request: Request):
    async with get_db_connection() as conn:
        c1 = await conn.execute("SELECT * FROM settings WHERE id=1")
        settings_db = await c1.fetchone()
        
        c2 = await conn.execute("SELECT * FROM tracked_streamers ORDER BY login ASC")
        tracked = await c2.fetchall()

    tracked_list = [dict(s) for s in tracked]
    
    # Vérification en direct pour les points Vert/Rouge
    if tracked_list:
        try:
            logins = [s['login'] for s in tracked_list]
            async with aiohttp.ClientSession() as session:
                url = f"https://api.twitch.tv/helix/streams?user_login={'&user_login='.join(logins)}"
                headers = {
                    "Client-ID": settings.TWITCH_CLIENT_ID,
                    "Authorization": f"Bearer {settings.TWITCH_OAUTH_TOKEN.replace('oauth:', '')}"
                }
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        online_logins = [s['user_login'].lower() for s in (await resp.json()).get('data', [])]
                        for s in tracked_list:
                            s['is_online'] = s['login'].lower() in online_logins
        except: pass

    return templates.TemplateResponse(request=request, name="admin/notifications.html", context={"request": request, "settings": dict(settings_db) if settings_db else {}, "tracked_streamers": tracked_list})

@router.post("/notifications/settings")
async def save_notifications_settings(
    discord_notify_enabled: str = Form("off"),
    discord_notify_message: str = Form(""),
    notif_live_channel_id: str = Form(""),
    streamers_channel_id: str = Form("")
):
    notif_val = 1 if discord_notify_enabled == "on" else 0
    async with get_db_connection() as conn:
        await conn.execute("""
            UPDATE settings 
            SET discord_notify_enabled=$1, discord_notify_message=$2, 
                notif_live_channel_id=$3, streamers_channel_id=$4 
            WHERE id=1
        """, (notif_val, discord_notify_message, notif_live_channel_id, streamers_channel_id))
    return RedirectResponse(url="/admin/notifications?saved=true", status_code=303)

@router.post("/notifications/streamer/add")
async def add_tracked_streamer(login: str = Form(...)):
    login = login.lower().strip()
    if login:
        try:
            async with get_db_connection() as conn:
                await conn.execute("INSERT INTO tracked_streamers (login) VALUES ($1)", (login,))
        except: pass
    return RedirectResponse(url="/admin/notifications", status_code=303)

@router.post("/notifications/streamer/delete/{streamer_id}")
async def delete_tracked_streamer(streamer_id: int):
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM tracked_streamers WHERE id = $1", (streamer_id,))
    return RedirectResponse(url="/admin/notifications", status_code=303)

# --- LOGIQUE CERVEAU FÉLIX IA ---

@router.get("/felix_ai", response_class=HTMLResponse)
async def get_felix_ai(request: Request):
    async with get_db_connection() as conn:
        c1 = await conn.execute("SELECT * FROM personality WHERE id = 1")
        p_results = await c1.fetchone()
        p_data = dict(p_results) if p_results else {}
        
        c2 = await conn.execute("SELECT * FROM settings WHERE id = 1")
        s_results = await c2.fetchone()
        s_data = dict(s_results) if s_results else {}
        
    return templates.TemplateResponse(request=request, name="admin/felix_ai.html", context={
        "request": request,
        "tones": VRAIS_TONS,
        "settings": s_data,
        "personality": p_data
    })

@router.post("/felix_ai")
async def save_felix_ai(
    ai_enabled: str = Form("off"),
    enable_twitch: str = Form("off"),
    tone_selector: str = Form("neutre"),
    system_prompt: str = Form(""),
    base_context: str = Form(""),
    intervention_rate: int = Form(20),
    roast_level: int = Form(10),
    response_length: int = Form(150),
    temperature: float = Form(0.7),
    frequency_penalty: float = Form(0.3),
    presence_penalty: float = Form(0.3),
    discord_link: str = Form(""),
    youtube_link: str = Form(""),
    planning: str = Form("")
):
    rate_float = float(intervention_rate) / 100.0 
    ai_val = 1 if ai_enabled == "on" else 0
    twitch_val = 1 if enable_twitch == "on" else 0
    final_prompt = system_prompt if tone_selector == "neutre" else VRAIS_TONS.get(tone_selector, system_prompt)

    async with get_db_connection() as conn:
        await conn.execute("""
            UPDATE personality 
            SET system_prompt=$1, base_context=$2, intervention_rate=$3, roast_level=$4, 
                temperature=$5, frequency_penalty=$6, presence_penalty=$7
            WHERE id=1
        """, (final_prompt, base_context, rate_float, roast_level, temperature, frequency_penalty, presence_penalty))
        
        await conn.execute("""
            UPDATE settings 
            SET ai_enabled=$1, enable_twitch=$2, selected_tone=$3, response_length=$4, 
                discord_link=$5, youtube_link=$6, planning=$7
            WHERE id=1
        """, (ai_val, twitch_val, tone_selector, str(response_length), discord_link, youtube_link, planning))
    
    return RedirectResponse(url="/admin/felix_ai?saved=true", status_code=303)

# ==========================================
# ROUTES DATA & LOGS (Gestion du .env)
# ==========================================

@router.get("/data_logs")
@router.get("/data_logs.html")
async def get_data_logs(request: Request):
    import dotenv
    return templates.TemplateResponse(request=request, name="admin/data_logs.html", context={"request": request, "env": dotenv.dotenv_values(".env")})

@router.post("/data_logs/save")
async def save_env_config(request: Request):
    import dotenv
    form_data = await request.form()
    for key, value in form_data.items():
        if value: dotenv.set_key(".env", key, str(value))
    return RedirectResponse(url="/admin/data_logs?saved=true", status_code=303)

# ==========================================
# ROUTES ANNONCES (Doublons potentiels de l'API)
# ==========================================

@router.get("/admin/announcements", response_class=HTMLResponse)
async def admin_announcements_page_alt(request: Request):
    return templates.TemplateResponse(request=request, name="admin/announcements.html", context={"request": request})

@router.get("/api/announcements")
async def api_get_announcements():
    try:
        async with get_db_connection() as conn:
            c = await conn.execute("SELECT * FROM auto_announcements ORDER BY id DESC")
            announcements = await c.fetchall()
            return [dict(ann) for ann in announcements]
    except Exception as e:
        return []

@router.post("/api/announcements/save")
async def api_save_announcement(request: Request):
    try:
        data = await request.json()
        ann_id = data.get("id")
        label = data.get("label", "Annonce")
        msg_template = data.get("message_template", "")
        trigger = data.get("trigger_type", "interval")
        interval = data.get("interval_minutes", 30)
        group = data.get("group_name", "")
        
        async with get_db_connection() as conn:
            if ann_id:
                await conn.execute("""
                    UPDATE auto_announcements 
                    SET label=$1, message_template=$2, trigger_type=$3, interval_minutes=$4, group_name=$5
                    WHERE id=$6
                """, (label, msg_template, trigger, interval, group, ann_id))
            else:
                await conn.execute("""
                    INSERT INTO auto_announcements (label, message_template, trigger_type, interval_minutes, group_name, is_enabled)
                    VALUES ($1, $2, $3, $4, $5, 1)
                """, (label, msg_template, trigger, interval, group))
            
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@router.delete("/api/announcements/delete/{ann_id}")
async def api_delete_announcement(ann_id: int):
    try:
        async with get_db_connection() as conn:
            await conn.execute("DELETE FROM auto_announcements WHERE id=$1", (ann_id,))
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# ==========================================
# ROUTES MODÉRATION
# ==========================================

@router.get("/moderation")
@router.get("/moderation.html")
async def get_moderation_page(request: Request):
    async with get_db_connection() as conn:
        c1 = await conn.execute("SELECT * FROM moderation_settings WHERE id=1")
        settings_db = await c1.fetchone()
        
        c2 = await conn.execute("SELECT * FROM banned_words ORDER BY word ASC")
        banned_words = await c2.fetchall()
        
        c3 = await conn.execute("SELECT * FROM stream_events WHERE event_type = 'sanction' ORDER BY id DESC LIMIT 30")
        raw_sanctions = await c3.fetchall()
        
    recent_sanctions = []
    for s in raw_sanctions:
        item = dict(s)
        try:
            parsed = json.loads(item['details'])
        except:
            parsed = {"reason": item['details'], "source": "Système"}
            
        raw_reason = parsed.get("reason", "Raison non spécifiée")
        modo = parsed.get("bot", parsed.get("source", "Félix"))
        
        sanction = "Modération"
        raison = raw_reason

        if " : " in raw_reason and any(x in raw_reason for x in ["Suppression", "Timeout", "Ban"]):
            parts = raw_reason.split(" : ", 1)
            sanction = parts[0].strip()
            raison = parts[1].strip()
            
        elif raw_reason.startswith("[") and "] par " in raw_reason:
            parts = raw_reason.split("] par ", 1)
            sanction = parts[0].replace("[", "").strip()
            rest = parts[1]
            if " : " in rest:
                modo, raison = rest.split(" : ", 1)
            else:
                raison = rest

        item['details_json'] = {
            "raison": raison,
            "sanction": sanction,
            "modo": modo.strip()
        }
        recent_sanctions.append(item)
    
    return templates.TemplateResponse(
        request=request,
        name="admin/moderation.html", 
        context={
            "request": request, 
            "settings": dict(settings_db) if settings_db else {}, 
            "banned_words": [dict(w) for w in banned_words],
            "recent_sanctions": recent_sanctions 
        }
    )

@router.post("/admin/moderation/settings")
async def update_mod_settings(request: Request):
    form_data = await request.form()
    
    caps = 1 if form_data.get("caps_enabled") else 0
    links = 1 if form_data.get("links_enabled") else 0
    spam = 1 if form_data.get("spam_enabled") else 0
    banned = 1 if form_data.get("banned_words_enabled") else 0
    
    caps_min = int(form_data.get("caps_min_length") or 10)
    caps_pct = int(form_data.get("caps_percent") or 70)
    spam_lim = int(form_data.get("spam_limit") or 4)
    spam_time = int(form_data.get("spam_timeframe") or 30)

    updates = {
        "caps_enabled": caps, "links_enabled": links, "spam_enabled": spam, "banned_words_enabled": banned,
        "caps_min_length": caps_min, "caps_percent": caps_pct, "spam_limit": spam_lim, "spam_timeframe": spam_time
    }

    for key, value in form_data.items():
        final_key = key
        if key.startswith("banned_words_"):
            final_key = key.replace("banned_words_", "words_")
            
        if final_key.endswith("_act"):
            updates[final_key] = value
        elif final_key.endswith("_dur"):
            updates[final_key] = int(value or 0)

    # Création dynamique des index PostgreSQL ($1, $2...)
    set_clause = ", ".join([f"{k}=${i+1}" for i, k in enumerate(updates.keys())])
    values = tuple(updates.values())

    async with get_db_connection() as conn:
        await conn.execute(f"UPDATE moderation_settings SET {set_clause} WHERE id=1", values)
    
    return RedirectResponse(url="/admin/moderation?saved=true", status_code=303)

@router.post("/moderation/words/add")
async def add_banned_word(request: Request):
    form_data = await request.form()
    word = form_data.get("word", "").strip().lower()
    
    if word:
        try:
            async with get_db_connection() as conn:
                await conn.execute("INSERT INTO banned_words (word) VALUES ($1) ON CONFLICT(word) DO NOTHING", (word,))
        except Exception:
            pass
            
    return RedirectResponse(url="/admin/moderation", status_code=303)

@router.post("/moderation/words/delete/{word_id}")
async def delete_banned_word(word_id: int):
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM banned_words WHERE id=$1", (word_id,))
    
    return RedirectResponse(url="/admin/moderation", status_code=303)
