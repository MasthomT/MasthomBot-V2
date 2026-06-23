import os
import aiohttp
from datetime import datetime
from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# --- IMPORT CORE POSTGRESQL ---
from app.core.database import get_db_connection

load_dotenv()

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")

EXCLUSION_LIST = "('masthom_', 'felixthebigblackcat', 'vestale7', 'streamelements', 'wizebot', 'nightbot')"

# ==========================================
# 1. PORTAIL D'ACCUEIL & AUTHENTIFICATION
# ==========================================
@router.get("/", response_class=HTMLResponse)
@router.get("/index", response_class=HTMLResponse)
async def home_page(request: Request):
    if request.cookies.get("viewer_id"):
        return RedirectResponse(url="/profile")
    return templates.TemplateResponse(request=request, name="public/index.html")

@router.get("/login")
async def login(request: Request):
    client_id = os.getenv("TWITCH_CLIENT_ID")
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/callback"
    url = f"https://id.twitch.tv/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=user:read:follows"
    return RedirectResponse(url)

@router.get("/auth/callback")
async def auth_callback(request: Request, code: str = None):
    if not code:
        return HTMLResponse("Erreur : Autorisation refusée par Twitch.", status_code=400)

    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/auth/callback"

    async with aiohttp.ClientSession() as session:
        token_resp = await session.post("https://id.twitch.tv/oauth2/token", data={
            "client_id": client_id, "client_secret": client_secret, "code": code,
            "grant_type": "authorization_code", "redirect_uri": redirect_uri
        })
        if token_resp.status != 200: return HTMLResponse("Erreur Auth Twitch.", status_code=400)
        token_data = await token_resp.json()
        
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token_data['access_token']}"}
        user_resp = await session.get("https://api.twitch.tv/helix/users", headers=headers)
        user_data = await user_resp.json()
        if not user_data.get("data"): return HTMLResponse("Impossible de lire votre profil.", status_code=400)
            
        user = user_data["data"][0]

        async with get_db_connection() as conn:
            cursor = await conn.execute("SELECT * FROM viewers WHERE twitch_id = $1", (user["id"],))
            row = await cursor.fetchone()
            if not row:
                await conn.execute("INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES ($1, $2, 0, 0, 0)", (user["id"], user["display_name"]))
            else:
                await conn.execute("UPDATE viewers SET username = $1 WHERE twitch_id = $2", (user["display_name"], user["id"]))

        response = RedirectResponse(url="/profile")
        response.set_cookie("viewer_id", user["id"], max_age=2592000, httponly=True)
        response.set_cookie("viewer_name", user["display_name"], max_age=2592000)
        response.set_cookie("viewer_avatar", user["profile_image_url"], max_age=2592000)
        return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("viewer_id")
    response.delete_cookie("viewer_name")
    response.delete_cookie("viewer_avatar")
    return response

# ==========================================
# 2. PAGES DU VIEWER (PROFIL & FÉLIX)
# ==========================================
@router.get("/classement", response_class=HTMLResponse)
async def leaderboard_page(request: Request):
    return templates.TemplateResponse(request=request, name="public/leaderboard.html", context={
        "is_logged_in": bool(request.cookies.get("viewer_id")),
    })

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    viewer_id = request.cookies.get("viewer_id")
    if not viewer_id: return RedirectResponse(url="/")
    
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM viewers WHERE twitch_id = $1", (viewer_id,))
        row = await cursor.fetchone()
        if not row:
            return RedirectResponse(url="/logout")
            
        viewer = dict(row)
        
        # Calculs XP et Niveau
        xp = viewer.get("points", 0)
        level = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
        next_xp = int(100 * ((level + 1) ** 2.2))
        curr_base = int(100 * (level ** 2.2)) if level > 1 else 0
        progress = min(100, max(0, ((xp - curr_base) / (next_xp - curr_base)) * 100)) if next_xp > curr_base else 100
            
        wt = viewer.get("watchtime", 0)
        watchtime_str = f"{wt // 3600}h {(wt % 3600) // 60}m"
        
        cursor_rank = await conn.execute("SELECT COUNT(*) FROM viewers WHERE points > $1", (xp,))
        rank_row = await cursor_rank.fetchone()
        rank = (rank_row[0] if rank_row else 0) + 1
        
        # Historique personnalisé et formaté
        cursor_logs = await conn.execute("SELECT * FROM viewer_exp_log WHERE twitch_id = $1 ORDER BY timestamp DESC LIMIT 15", (viewer_id,))
        raw_logs = await cursor_logs.fetchall()
        history = []
        for h in raw_logs:
            log = dict(h)
            evt = log.get("event_type", "").lower()
            icon, color = "✨", "#ffffff"
            if "présence" in evt or "watchtime" in evt: icon, color = "🎬", "#00ffcc"
            elif "message" in evt or "chat" in evt: icon, color = "💬", "#60a5fa"
            elif "sub" in evt or "abonnement" in evt: icon, color = "⭐", "#fbbf24"
            elif "raid" in evt: icon, color = "⚔️", "#f87171"
            elif "follow" in evt: icon, color = "❤️", "#f472b6"
            elif "bits" in evt or "cheer" in evt: icon, color = "💎", "#c084fc"
            
            ts = log.get("timestamp", "")
            d_str, t_str = ts.split(" ")[0] if " " in ts else ts, ts.split(" ")[1][:5] if " " in ts else ""
                
            history.append({"label": log["event_type"], "amount": log["amount"], "date": d_str, "time": t_str, "icon": icon, "color": color})
        
    return templates.TemplateResponse(request=request, name="public/profile.html", context={
        "viewer": viewer, "level": level, "next_xp": next_xp,
        "progress": progress, "watchtime_str": watchtime_str, "rank": rank,
        "history": history, "avatar": request.cookies.get("viewer_avatar", "")
    })

@router.get("/felix", response_class=HTMLResponse)
async def felix_page(request: Request):
    viewer_id = request.cookies.get("viewer_id")
    if not viewer_id: return RedirectResponse(url="/")
        
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM viewers WHERE twitch_id = $1", (viewer_id,))
        row = await cursor.fetchone()
        if not row: return RedirectResponse(url="/logout")
        
    return templates.TemplateResponse(request=request, name="public/felix.html", context={"viewer": dict(row)})

@router.post("/felix/save")
async def felix_save(request: Request):
    viewer_id = request.cookies.get("viewer_id")
    if not viewer_id: return RedirectResponse(url="/")
        
    form = await request.form()
    async with get_db_connection() as conn:
        await conn.execute("""
            UPDATE viewers SET 
                nickname = $1, nickname_for_bot = $2, birthday = $3, sleep_pattern = $4, 
                vibe = $5, roast_level = $6, favorite_game = $7, favorite_food = $8, free_message = $9
            WHERE twitch_id = $10
        """, (
            form.get("nickname"), form.get("felix_nickname"), form.get("birthday"), 
            form.get("sleep_pattern"), form.get("vibe"), int(form.get("roast_level") or 5), 
            form.get("favorite_game"), form.get("favorite_food"), form.get("free_message"), viewer_id
        ))
    return RedirectResponse(url="/felix?saved=1", status_code=303)

@router.get("/infos", response_class=HTMLResponse)
@router.get("/infos.html", response_class=HTMLResponse)
async def public_infos_page(request: Request):
    """Affiche la page publique des informations avec Jinja2."""
    async with get_db_connection() as conn:
        cursor = await conn.execute("SELECT * FROM channel_info WHERE id = 1")
        row = await cursor.fetchone()
        info_data = dict(row) if row else {}

    return templates.TemplateResponse(
        request=request,
        name="public/infos.html",
        context={"request": request, "info": info_data}
    )

# ==========================================
# 3. ROUTES API POUR LE FRONTEND (fel-x.icu)
# ==========================================
@router.get("/viewer/{twitch_id}")
async def get_viewer_profile_api(twitch_id: str, username: str = None):
    async with get_db_connection() as conn:
        c = await conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,))
        row = await c.fetchone()
        display_name = username if username else f"Visiteur_{twitch_id[:4]}"

        if not row:
            await conn.execute("INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES (?, ?, 0, 0, 0)", (twitch_id, display_name))
            c = await conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,))
            row = await c.fetchone()
        else:
            if row['username'].startswith("Visiteur_") and username:
                await conn.execute("UPDATE viewers SET username = ? WHERE twitch_id = ?", (username, twitch_id))
                c = await conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,))
                row = await c.fetchone()

        viewer_data = dict(row)
        await conn.execute("UPDATE viewers SET last_seen = NOW(), last_web_login = NOW() WHERE twitch_id = ?", (twitch_id,))

        xp = viewer_data.get('points', 0)
        viewer_data['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1

        crank = await conn.execute(f"SELECT COUNT(*) FROM viewers WHERE points > ? AND LOWER(username) NOT IN {EXCLUSION_LIST}", (xp,))
        rank_val = await crank.fetchone()
        viewer_data['rank'] = (rank_val[0] if rank_val else 0) + 1

        ctrophies = await conn.execute("""
            SELECT t.label, t.icon, t.description, t.tier, vt.earned_at
            FROM viewer_trophies vt
            JOIN trophy_list t ON vt.trophy_id = t.id
            WHERE vt.twitch_id = ?
            ORDER BY vt.earned_at DESC
        """, (twitch_id,))
        trophies_raw = await ctrophies.fetchall()

        trophies_list = []
        tier_counts = {"Standard": 0, "Bronze": 0, "Argent": 0, "Or": 0, "Platine": 0, "Diamant": 0}

        for tr in trophies_raw:
            t_dict = dict(tr)
            if isinstance(t_dict.get('earned_at'), datetime):
                t_dict['earned_at'] = t_dict['earned_at'].isoformat()
            trophies_list.append(t_dict)
            tier_name = t_dict.get('tier', 'Standard')
            tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

        viewer_data['trophies'] = trophies_list
        viewer_data['tier_counts'] = tier_counts

        history_list = []
        cset = await conn.execute("SELECT exp_per_message, exp_per_watchtime FROM settings WHERE id=1")
        settings_row = await cset.fetchone()
        exp_msg = settings_row['exp_per_message'] if settings_row else 2
        exp_wt = settings_row['exp_per_watchtime'] if settings_row else 5

        ctoday = await conn.execute("SELECT messages, watchtime FROM viewer_daily_stats WHERE twitch_id = ? AND day = CURRENT_DATE", (twitch_id,))
        today_stats = await ctoday.fetchone()

        if today_stats:
            if today_stats['watchtime'] > 0:
                wt = today_stats['watchtime']
                wt_str = f"{wt // 3600}h {(wt % 3600) // 60}m" if wt >= 3600 else f"{wt // 60} min"
                history_list.append({
                    "event_type": "PRÉSENCE (LIVE)", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "date": "Aujourd'hui", "details": f"Session : {wt_str}", "amount": (wt // 60) * exp_wt,
                    "icon": "⏱️", "color": "#10b981"
                })
            if today_stats['messages'] > 0:
                history_list.append({
                    "event_type": "ACTIVITÉ CHAT", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "date": "Aujourd'hui", "details": f"{today_stats['messages']} messages envoyés", "amount": today_stats['messages'] * exp_msg,
                    "icon": "💬", "color": "#0ea5e9"
                })

        chist = await conn.execute("SELECT * FROM viewer_exp_log WHERE twitch_id = ? ORDER BY timestamp DESC LIMIT 15", (twitch_id,))
        raw_history = await chist.fetchall()
        for r in raw_history:
            log = dict(r)
            ev = log['event_type'].upper()
            icon, color = "✨", "#00f5c3"
            if any(x in ev for x in ["BIT", "CHEER"]): icon, color = "💎", "#ffb300"
            elif "RAID" in ev: icon, color = "⚔️", "#a855f7"
            elif "SUB" in ev: icon, color = "💜", "#9146ff"

            ts = log['timestamp']
            if isinstance(ts, datetime):
                ts = ts.strftime('%Y-%m-%d %H:%M:%S')
            elif not isinstance(ts, str):
                ts = str(ts)

            history_list.append({
                "event_type": ev, "amount": log['amount'], "details": log['details'] or "Action standard",
                "date": ts[:10].replace("-", "/"), "icon": icon, "color": color
            })

        viewer_data['history'] = history_list
        
        for k, v in viewer_data.items():
            if isinstance(v, datetime):
                viewer_data[k] = v.isoformat()
                
        return viewer_data

@router.get("/rewards/secret")
async def get_secret_rewards():
    """API publique pour charger la liste des trophées masqués de la table trophy_list"""
    async with get_db_connection() as conn:
        try:
            cursor = await conn.execute("SELECT * FROM trophy_list WHERE is_secret = 1")
            return [dict(t) for t in await cursor.fetchall()]
        except Exception as e:
            print(f"Erreur chargement trophées secrets: {e}")
            return []

@router.post("/viewer/update_context")
async def update_viewer_context_public(request: Request):
    from app.routes.api import update_viewer_context
    return await update_viewer_context(request)
