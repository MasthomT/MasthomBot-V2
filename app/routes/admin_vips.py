import sqlite3
import logging
import aiohttp
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings

logger = logging.getLogger("masthbot.vips")
router = APIRouter(prefix="/admin", tags=["vips_team"])
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_team_columns():
    conn = get_db()
    try:
        conn.execute("ALTER TABLE viewers ADD COLUMN is_mod INTEGER DEFAULT 0")
    except: pass
    try:
        conn.execute("ALTER TABLE viewers ADD COLUMN is_artist INTEGER DEFAULT 0")
    except: pass
    conn.commit()
    conn.close()

# ==========================================
# 📊 ROUTE PRINCIPALE
# ==========================================
@router.get("/vips", response_class=HTMLResponse)
async def admin_vips_page(request: Request):
    init_team_columns()
    conn = get_db()
    try:
        # On affiche tout le monde en lecture seule
        vips = conn.execute("SELECT twitch_id, username, is_vip, vip_expiry FROM viewers WHERE is_vip = 1 ORDER BY username ASC").fetchall()
        mods = conn.execute("SELECT twitch_id, username FROM viewers WHERE is_mod = 1 ORDER BY username ASC").fetchall()
        artists = conn.execute("SELECT twitch_id, username FROM viewers WHERE is_artist = 1 ORDER BY username ASC").fetchall()
        
        return templates.TemplateResponse(
            request=request, 
            name="admin/admin_vips.html", 
            context={"request": request, "vips": vips, "mods": mods, "artists": artists}
        )
    finally:
        conn.close()

# ==========================================
# 🔄 L'ASPIRATEUR AUTOMATIQUE (VIP + MODOS)
# ==========================================
@router.post("/vips/sync")
async def sync_vips_from_twitch():
    init_team_columns()
    conn = get_db()
    try:
        token = settings.TWITCH_OAUTH_TOKEN.replace("oauth:", "").strip()
        channel_name = settings.TWITCH_CHANNEL.replace("#", "").lower().strip()
        if not token: return RedirectResponse(url="/admin/vips?error=sync_failed", status_code=303)
            
        async with aiohttp.ClientSession() as session:
            # 1. Validation Twitch
            async with session.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {token}"}) as r:
                if r.status != 200: return RedirectResponse(url="/admin/vips?error=sync_failed", status_code=303)
                client_id = (await r.json())['client_id']
            
            headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
            async with session.get(f"https://api.twitch.tv/helix/users?login={channel_name}", headers=headers) as r:
                broadcaster_id = (await r.json())['data'][0]['id']
                
            # 2. Aspiration des VIPS
            vips = []
            cursor = ""
            while True:
                url = f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={broadcaster_id}&first=100"
                if cursor: url += f"&after={cursor}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    vips.extend(data.get("data", []))
                    cursor = data.get("pagination", {}).get("cursor")
                    if not cursor: break
                        
            # 3. Aspiration des MODÉRATEURS
            mods = []
            cursor = ""
            while True:
                url = f"https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={broadcaster_id}&first=100"
                if cursor: url += f"&after={cursor}"
                async with session.get(url, headers=headers) as r:
                    if r.status != 200: break
                    data = await r.json()
                    mods.extend(data.get("data", []))
                    cursor = data.get("pagination", {}).get("cursor")
                    if not cursor: break

            # 4. Enregistrement en base de données
            # On met tout le monde à 0 pour éviter les anciens rôles, puis on recoche
            conn.execute("UPDATE viewers SET is_vip = 0, is_mod = 0 WHERE is_vip = 1 OR is_mod = 1")
            
            count_vips = 0
            for v in vips:
                t_id = v['user_id']
                u_name = v['user_login']
                conn.execute("INSERT OR IGNORE INTO viewers (twitch_id, username) VALUES (?, ?)", (t_id, u_name))
                conn.execute("UPDATE viewers SET is_vip = 1 WHERE twitch_id = ?", (t_id,))
                count_vips += 1
            
            count_mods = 0
            for m in mods:
                t_id = m['user_id']
                u_name = m['user_login']
                conn.execute("INSERT OR IGNORE INTO viewers (twitch_id, username) VALUES (?, ?)", (t_id, u_name))
                conn.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = ?", (t_id,))
                count_mods += 1
                
            conn.commit()
            logger.info(f"🔄 [SYNCHRO] {count_vips} VIPs et {count_mods} Modérateurs aspirés depuis Twitch !")
            return RedirectResponse(url="/admin/vips?success=synced", status_code=303)
    except Exception as e:
        logger.error(f"❌ Erreur de synchro VIP/Mods : {e}")
        return RedirectResponse(url="/admin/vips?error=sync_failed", status_code=303)
    finally:
        conn.close()

# On garde juste l'attribution de VIP manuelle avec Date si jamais tu as besoin de faire des VIP Temporaires.
@router.post("/vips/add")
async def add_vip(username: str = Form(...), duration_days: int = Form(...), exact_date: str = Form(None)):
    conn = get_db()
    try:
        clean_username = username.lower().strip().replace("@", "")
        expiry = None
        viewer = conn.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = ?", (clean_username,)).fetchone()
        if not viewer:
            return RedirectResponse(url="/admin/vips?error=not_found", status_code=303)
        twitch_id = viewer["twitch_id"]
        
        if duration_days == -1:
            if not exact_date: return RedirectResponse(url="/admin/vips?error=missing_date", status_code=303)
            expiry = exact_date.replace("T", " ")
            if len(expiry) == 16: expiry += ":00"
        elif duration_days > 0:
            expiry = (datetime.now() + timedelta(days=duration_days)).isoformat()
        
        conn.execute("UPDATE viewers SET is_vip = 1, vip_expiry = ? WHERE twitch_id = ?", (expiry, twitch_id))
        conn.commit()
        return RedirectResponse(url="/admin/vips?success=added", status_code=303)
    finally:
        conn.close()

@router.post("/vips/revoke/{twitch_id}")
async def revoke_vip(twitch_id: str):
    conn = get_db()
    try:
        conn.execute("UPDATE viewers SET is_vip = 0, vip_expiry = NULL WHERE twitch_id = ?", (twitch_id,))
        conn.commit()
        return RedirectResponse(url="/admin/vips?success=revoked", status_code=303)
    finally:
        conn.close()
