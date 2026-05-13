import sqlite3
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("masthbot.vips")
router = APIRouter(prefix="/admin", tags=["vips"])
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "/home/thomas/masthom/BOT_V2/bot_database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 1. ROUTE POUR AFFICHER LA PAGE WEB
@router.get("/vips", response_class=HTMLResponse)
async def admin_vips_page(request: Request):
    conn = get_db()
    try:
        vips = conn.execute("""
            SELECT twitch_id, username, is_vip, vip_expiry 
            FROM viewers 
            WHERE is_vip = 1 
            ORDER BY username ASC
        """).fetchall()
        
        return templates.TemplateResponse(
            request=request, 
            name="admin/admin_vips.html", 
            context={"request": request, "vips": vips}
        )
    finally:
        conn.close()

# 2. ROUTE POUR AJOUTER UN VIP (MODIFIÉE POUR LE CALENDRIER)
@router.post("/vips/add")
async def add_vip(
    username: str = Form(...), 
    duration_days: int = Form(...), 
    exact_date: str = Form(None)  # Le nouveau champ caché qui contient la date du calendrier
):
    conn = get_db()
    try:
        clean_username = username.lower().strip().replace("@", "")
        expiry = None
        
        # LOGIQUE 1 : Si on a choisi "Date Exacte" (Valeur du selecteur = -1)
        if duration_days == -1 and exact_date:
            try:
                # Le HTML envoie une date au format ISO (ex: 2026-05-10T15:30)
                expiry = datetime.fromisoformat(exact_date).isoformat()
            except ValueError:
                pass # Sécurité anti-crash si le navigateur a envoyé une date bizarre
        
        # LOGIQUE 2 : Si on a choisi un nombre de jours classique (1, 7, 30)
        elif duration_days > 0:
            expiry = (datetime.now() + timedelta(days=duration_days)).isoformat()
        
        # LOGIQUE 3 : Si on a choisi 0, "expiry" reste "None" (donc Permanent)
        
        # Enregistrement en base de données
        res = conn.execute("""
            UPDATE viewers 
            SET is_vip = 1, vip_expiry = ? 
            WHERE LOWER(username) = ?
        """, (expiry, clean_username))
        
        # Sécurité : Si l'utilisateur n'existe pas
        if res.rowcount == 0:
            return RedirectResponse(url="/admin/vips?error=not_found", status_code=303)
            
        conn.commit()
        logger.info(f"💎 Nouveau VIP ajouté : {clean_username} (Expire le: {expiry if expiry else 'Jamais'})")
        return RedirectResponse(url="/admin/vips?success=added", status_code=303)
    finally:
        conn.close()

# 3. ROUTE POUR SUPPRIMER UN VIP MANUELLEMENT
@router.post("/vips/revoke/{twitch_id}")
async def revoke_vip(twitch_id: str):
    conn = get_db()
    try:
        conn.execute("UPDATE viewers SET is_vip = 0, vip_expiry = NULL WHERE twitch_id = ?", (twitch_id,))
        conn.commit()
        logger.info(f"🗑️ Grade VIP retiré pour l'ID {twitch_id}")
        return RedirectResponse(url="/admin/vips?success=revoked", status_code=303)
    finally:
        conn.close()
