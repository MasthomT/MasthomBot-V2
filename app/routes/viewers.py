import logging
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.repositories import viewer_repo
from app.models.viewer import ViewerResponse
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.viewers")
router = APIRouter(tags=["viewers"])
templates = Jinja2Templates(directory="app/templates")

# --- MÉTHODES UTILITAIRES ---
def format_to_hhmm(seconds):
    try:
        sec = int(seconds or 0)
        if sec < 0: return "00:00"
        return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}"
    except:
        return "00:00"

def calculate_level(xp):
    """Formule mathématique officielle (XP = 100 * lvl^2.2)"""
    try:
        xp = int(xp or 0)
        if xp <= 0: return 1
        return max(1, int((xp / 100) ** (1 / 2.2)))
    except:
        return 1

# =====================================================================
# 🖥️ INTERFACES HTML (ADMIN DASHBOARD)
# =====================================================================

@router.get("/admin/viewer_manager.html", response_class=HTMLResponse)
async def admin_viewers_page(request: Request):
    try:
        async with get_db_connection() as conn:
            c1 = await conn.execute("SELECT * FROM viewers ORDER BY points DESC, watchtime DESC")
            viewers_raw = await c1.fetchall()
            
            c2 = await conn.execute("SELECT * FROM settings WHERE id=1")
            s_row = await c2.fetchone()

        viewers = []
        for v in viewers_raw:
            item = dict(v)
            item['watchtime_hhmm'] = format_to_hhmm(item.get('watchtime', 0))
            item['level'] = calculate_level(item.get('points', 0))
            viewers.append(item)

        exp_settings = dict(s_row) if s_row else {}
        return templates.TemplateResponse(request=request, name="admin/viewer_manager.html", context={
            "request": request, 
            "viewers": viewers, 
            "exp_settings": exp_settings
        })
    except Exception as e:
        logger.error(f"❌ Erreur viewer manager : {e}")
        return HTMLResponse(content=f"<h1>Erreur Serveur</h1><p>{e}</p>", status_code=500)

@router.get("/admin/viewer/{twitch_id}/history", response_class=HTMLResponse)
async def admin_viewer_history(request: Request, twitch_id: str):
    async with get_db_connection() as conn:
        c1 = await conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,))
        viewer_row = await c1.fetchone()
        
        if not viewer_row:
            return RedirectResponse(url="/admin/viewer_manager.html")
            
        viewer = dict(viewer_row)
        viewer['level'] = calculate_level(viewer.get('points', 0))
        viewer['watchtime_readable'] = format_to_hhmm(viewer.get('watchtime', 0))
        
        c2 = await conn.execute("SELECT * FROM viewer_daily_stats WHERE twitch_id = ? ORDER BY day DESC LIMIT 30", (twitch_id,))
        daily_stats_raw = await c2.fetchall()
        daily_stats = []
        for d in daily_stats_raw:
            day_dict = dict(d)
            day_dict["watchtime_readable"] = format_to_hhmm(day_dict.get("watchtime", 0))
            if day_dict.get('day') and hasattr(day_dict['day'], 'isoformat'):
                day_dict['day'] = day_dict['day'].isoformat()
            daily_stats.append(day_dict)

        c3 = await conn.execute("SELECT * FROM viewer_exp_log WHERE twitch_id = ? ORDER BY timestamp DESC LIMIT 50", (twitch_id,))
        special_events_raw = await c3.fetchall()
        special_events = []
        for e in special_events_raw:
            ed = dict(e)
            # 🛡️ FIX : On convertit la date Postgres en Texte pour le HTML
            if ed.get('timestamp') and hasattr(ed['timestamp'], 'isoformat'):
                ed['timestamp'] = ed['timestamp'].isoformat()
            elif ed.get('timestamp'):
                ed['timestamp'] = str(ed['timestamp'])
            special_events.append(ed)
        
        c4 = await conn.execute("""
            SELECT t.label, t.icon, t.tier, vt.earned_at
            FROM viewer_trophies vt
            JOIN trophy_list t ON vt.trophy_id = t.id
            WHERE vt.twitch_id = ?
            ORDER BY vt.earned_at DESC
        """, (twitch_id,))
        trophies_raw = await c4.fetchall()
        viewer_trophies = []
        for t in trophies_raw:
            td = dict(t)
            # 🛡️ FIX : On convertit la date Postgres en Texte
            if td.get('earned_at') and hasattr(td['earned_at'], 'isoformat'):
                td['earned_at'] = td['earned_at'].isoformat()
            elif td.get('earned_at'):
                td['earned_at'] = str(td['earned_at'])
            viewer_trophies.append(td)

    return templates.TemplateResponse(request=request, name="admin/viewer_history.html", context={
        "request": request,
        "viewer": viewer,
        "daily_stats": daily_stats,
        "special_events": special_events,
        "viewer_trophies": viewer_trophies
    })

# =====================================================================
# ⚙️ ACTIONS DE GESTION (FORMULAIRES)
# =====================================================================

@router.post("/admin/viewer/{twitch_id}/save")
async def save_viewer_profile(request: Request, twitch_id: str,
    nickname: str = Form(None), nickname_for_bot: str = Form(None), 
    birthday: str = Form(None), sleep_pattern: str = Form(None), 
    pronouns: str = Form(None), vibe: str = Form(None), 
    favorite_game: str = Form(None), comfort_game: str = Form(None), 
    signature_emote: str = Form(None), play_style: str = Form(None), 
    useless_talent: str = Form(None), favorite_feature: str = Form(None), 
    favorite_food: str = Form(None), favorite_drink: str = Form(None), 
    free_message: str = Form(None), roast_level: int = Form(5)):
    
    async with get_db_connection() as conn:
        await conn.execute("""
            UPDATE viewers SET 
                nickname=?, nickname_for_bot=?, birthday=?, sleep_pattern=?, 
                pronouns=?, vibe=?, favorite_game=?, comfort_game=?, 
                signature_emote=?, play_style=?, useless_talent=?, 
                favorite_feature=?, favorite_food=?, favorite_drink=?, 
                free_message=?, roast_level=?
            WHERE twitch_id=?
        """, (nickname, nickname_for_bot, birthday, sleep_pattern, pronouns, vibe, favorite_game, comfort_game, signature_emote, play_style, useless_talent, favorite_feature, favorite_food, favorite_drink, free_message, roast_level, twitch_id))
        
    return RedirectResponse(url=f"/admin/viewer/{twitch_id}/history?saved=1", status_code=303)

@router.post("/admin/viewer/update_exp_settings")
async def update_exp_settings(request: Request):
    form_data = await request.form()
    async with get_db_connection() as conn:
        await conn.execute("""
            UPDATE settings 
            SET exp_sub_t1=?, exp_sub_t2=?, exp_sub_t3=?, 
                exp_subgift_t1=?, exp_subgift_t2=?, exp_subgift_t3=?,
                exp_raid_per_viewer=?, exp_bits_multiplier=?,
                exp_per_message=?, exp_per_watchtime=?
            WHERE id=1
        """, (
            int(form_data.get("exp_sub_t1") or 500), int(form_data.get("exp_sub_t2") or 1000), int(form_data.get("exp_sub_t3") or 2500),
            int(form_data.get("exp_subgift_t1") or 500), int(form_data.get("exp_subgift_t2") or 1000), int(form_data.get("exp_subgift_t3") or 2500),
            int(form_data.get("exp_raid_per_viewer") or 10), int(form_data.get("exp_bits_multiplier") or 1),
            int(form_data.get("exp_per_message") or 2), int(form_data.get("exp_per_watchtime") or 5)
        ))
    return RedirectResponse(url="/admin/viewer_manager.html?settings_saved=1", status_code=303)

@router.post("/admin/viewer/update_exp")
async def update_exp(request: Request, twitch_id: str = Form(...), amount: int = Form(...), action: str = Form(...)):
    async with get_db_connection() as conn:
        if action == "add":
            await conn.execute("UPDATE viewers SET points = points + ? WHERE twitch_id = ?", (amount, twitch_id))
        elif action == "remove":
            # GREATEST est l'équivalent Postgres de MAX dans ce contexte
            await conn.execute("UPDATE viewers SET points = GREATEST(0, points - ?) WHERE twitch_id = ?", (amount, twitch_id))
        elif action == "set":
            await conn.execute("UPDATE viewers SET points = ? WHERE twitch_id = ?", (amount, twitch_id))
    
    return RedirectResponse(url="/admin/viewer_manager.html?success=1", status_code=303)

# =====================================================================
# 🤖 ROUTES API JSON (FRONTEND / OUTILS EXTERNES)
# =====================================================================

@router.get("/api/viewers", response_model=list[ViewerResponse])
async def get_all_viewers():
    return await viewer_repo.get_all_viewers()

@router.get("/api/viewers/{twitch_id}", response_model=ViewerResponse)
async def get_viewer(twitch_id: str):
    viewer = await viewer_repo.get_viewer(twitch_id)
    if not viewer:
        raise HTTPException(status_code=404, detail="Viewer non trouvé")
    return viewer

@router.post("/api/viewers/{twitch_id}/nickname")
async def update_nickname(twitch_id: str, data: dict):
    nickname = data.get("nickname")
    if not nickname:
        raise HTTPException(status_code=400, detail="Nickname requis")
    await viewer_repo.update_viewer_profile(twitch_id, nickname=nickname)
    return {"status": "success", "nickname": nickname}

@router.post("/api/viewers/{twitch_id}/roast")
async def update_roast_level(twitch_id: str, data: dict):
    level = data.get("level")
    await viewer_repo.update_viewer_profile(twitch_id, roast_level=level)
    return {"status": "success", "roast_level": level}
