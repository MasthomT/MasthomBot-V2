import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.services import credits_service
from app.core.database import get_db_connection

from app.services.credits_service import credits_service
import json

from app.services.twitch_service import twitch_bot

logger = logging.getLogger("masthbot.credits")
router = APIRouter(tags=["credits"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/admin/credits_manager", response_class=HTMLResponse)
async def admin_credits_page(request: Request):
    """Affiche le gestionnaire de générique sur le Pi."""
    # ✅ FIX : On nomme explicitement les paramètres pour FastAPI
    return templates.TemplateResponse(
        request=request,
        name="admin/credits_manager.html", 
        context={"request": request, "config": credits_service.config}
    )

@router.get("/overlay/credits", response_class=HTMLResponse)
async def overlay_credits_page(request: Request):
    """L'overlay pour OBS."""
    # ✅ FIX : Pareil ici pour l'overlay
    return templates.TemplateResponse(
        request=request,
        name="overlays/credits.html", 
        context={"request": request}
    )

@router.get("/api/credits/data")
async def get_credits_data():
    """Récupère tout le monde présent (Chat Twitch + Base de données)."""
    
    # 1. Sécurité : On s'assure que les valeurs ne sont pas None
    master_token = str(twitch_bot.master_token or "")
    client_id = str(getattr(twitch_bot._http, 'client_id', '') or "")
    
    if not master_token or not client_id:
        logger.error("❌ [CREDITS API] Token ou ClientID manquant !")
        return {"stats": credits_service.get_stats(), "config": credits_service.config}

    # 2. Récupération des chatters via Twitch
    url = f"https://api.twitch.tv/helix/chat/chatters?broadcaster_id={twitch_bot.broadcaster_id}&moderator_id={twitch_bot.broadcaster_id}&first=1000"
    headers = {"Authorization": f"Bearer {master_token}", "Client-ID": client_id}
    
    session = await twitch_bot.get_web_session()
    all_usernames = []
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                chatters = data.get("data", [])
                all_usernames = [c['user_name'].lower() for c in chatters]
    except Exception as e:
        logger.error(f"❌ [CREDITS API] Erreur appel Twitch : {e}")

    # 3. Récupération des stats depuis la DB pour ceux qui sont connectés
    db_data = {}
    if all_usernames:
        async with get_db_connection() as conn:
            # On utilise ANY pour récupérer les infos en 1 seule requête SQL
            rows = await conn.execute("SELECT username, watchtime FROM viewers WHERE LOWER(username) = ANY($1)", (all_usernames,))
            db_rows = await rows.fetchall()
            db_data = {r['username'].lower(): r['watchtime'] for r in db_rows}

    # 4. Construction de la liste des 'viewers' (tous les connectés)
    viewers_list = []
    for username in all_usernames:
        # On récupère les données brutes de la base pour cet utilisateur
        user_data = db_data.get(username, {})
        
        # SÉCURITÉ : On vérifie que user_data est bien un dictionnaire
        # Si c'est un int (bug potentiel), on réinitialise à un dictionnaire vide
        if not isinstance(user_data, dict):
            user_data = {}

        viewers_list.append({
            "name": username,
            "watchtime": user_data.get('watchtime', 0),
            "messages": user_data.get('messages', 0),
            "label": ""
        })

    # 5. Fusion avec les catégories spéciales du service (subs, vips, etc.)
    final_stats = credits_service.get_stats().copy()
    final_stats['viewers'] = viewers_list

    return {
        "stats": final_stats,
        "config": credits_service.config
    }

@router.post("/api/credits/config")
async def save_credits_config(request: Request):
    """Sauvegarde les réglages (titre, durée, ordre)."""
    new_config = await request.json()
    credits_service.config.update(new_config)
    return {"status": "success"}

@router.post("/api/credits/reset")
async def reset_credits():
    """Bouton de vidage manuel."""
    credits_service.reset_session()
    return {"status": "success"}

@router.post("/api/credits/test")
async def inject_test_data():
    """Génère des faux noms très complets pour tester l'overlay et le Studio."""
    
    # 1. Catégories à Labels (Subs, Gifts, Bits, Raids, Followers)
    credits_service.log_event("subscribers", "Vestale7", "Tier 1")
    credits_service.log_event("subscribers", "LAntreDeSilver", "Tier 3")
    credits_service.log_event("gifters", "LeGrosMecene", "5 Gifts")
    credits_service.log_event("bits", "MonkeyMaxou", "500 Bits")
    credits_service.log_event("raiders", "Siphano", "150 viewers")
    credits_service.log_event("followers", "Nouvel_Ami", "Bienvenue !")
    
    # 2. Catégories à Messages (Modos, VIPs, Chatters)
    # On appelle log_event plusieurs fois pour simuler plusieurs messages
    credits_service.log_event("moderators", "SuperModo")
    credits_service.log_event("moderators", "SuperModo") # Fait passer à 2 msg
    credits_service.log_event("vips", "StarDuLive")
    credits_service.log_event("chatters", "Masthom")
    credits_service.log_event("chatters", "Masthom")
    credits_service.log_event("chatters", "Masthom") # Fait passer à 3 msg

    # 3. Catégorie Temps (Viewers / Lurkers)
    # add_watchtime(nom, minutes)
    credits_service.add_watchtime("Lurker_Fidele", 125)  # Donnera 2h05m
    credits_service.add_watchtime("Petit_Curieux", 45)   # Donnera 45m
    
    return {"status": "test_injected"}
