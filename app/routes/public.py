import os
import sqlite3
import aiohttp
from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================
# 1. PORTAIL D'ACCUEIL & AUTHENTIFICATION
# ==========================================
@router.get("/", response_class=HTMLResponse)
@router.get("/index", response_class=HTMLResponse)
async def home_page(request: Request):
    if request.cookies.get("viewer_id"):
        return RedirectResponse(url="/profile")
    return templates.TemplateResponse("public/index.html", {"request": request})

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

        conn = get_db()
        row = conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (user["id"],)).fetchone()
        if not row:
            conn.execute("INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES (?, ?, 0, 0, 0)", (user["id"], user["display_name"]))
        else:
            conn.execute("UPDATE viewers SET username = ? WHERE twitch_id = ?", (user["display_name"], user["id"]))
        conn.commit()
        conn.close()

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
@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    viewer_id = request.cookies.get("viewer_id")
    if not viewer_id: return RedirectResponse(url="/")
    
    conn = get_db()
    row = conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (viewer_id,)).fetchone()
    if not row:
        conn.close()
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
    rank = conn.execute("SELECT COUNT(*) FROM viewers WHERE points > ?", (xp,)).fetchone()[0] + 1
    
    # Historique personnalisé et formaté
    raw_logs = conn.execute("SELECT * FROM viewer_exp_log WHERE twitch_id = ? ORDER BY timestamp DESC LIMIT 15", (viewer_id,)).fetchall()
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
        
    conn.close()
    
    return templates.TemplateResponse("public/profile.html", {
        "request": request, "viewer": viewer, "level": level, "next_xp": next_xp,
        "progress": progress, "watchtime_str": watchtime_str, "rank": rank,
        "history": history, "avatar": request.cookies.get("viewer_avatar", "")
    })

@router.get("/felix", response_class=HTMLResponse)
async def felix_page(request: Request):
    viewer_id = request.cookies.get("viewer_id")
    if not viewer_id: return RedirectResponse(url="/")
        
    conn = get_db()
    row = conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (viewer_id,)).fetchone()
    conn.close()
    if not row: return RedirectResponse(url="/logout")
        
    return templates.TemplateResponse("public/felix.html", {"request": request, "viewer": dict(row)})

@router.post("/felix/save")
async def felix_save(request: Request):
    viewer_id = request.cookies.get("viewer_id")
    if not viewer_id: return RedirectResponse(url="/")
        
    form = await request.form()
    conn = get_db()
    conn.execute("""
        UPDATE viewers SET 
            nickname = ?, nickname_for_bot = ?, birthday = ?, sleep_pattern = ?, 
            vibe = ?, roast_level = ?, favorite_game = ?, favorite_food = ?, free_message = ?
        WHERE twitch_id = ?
    """, (
        form.get("nickname"), form.get("felix_nickname"), form.get("birthday"), 
        form.get("sleep_pattern"), form.get("vibe"), int(form.get("roast_level") or 5), 
        form.get("favorite_game"), form.get("favorite_food"), form.get("free_message"), viewer_id
    ))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/felix?saved=1", status_code=303)
