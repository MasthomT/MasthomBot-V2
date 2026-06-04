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

    # 3. Récupération des stats de la SESSION (Table journalière)
    session_data = {}
    async with get_db_connection() as conn:
        # On va chercher TOUS les viewers qui ont du temps de watchtime aujourd'hui (même s'ils ont quitté le stream)
        rows = await conn.execute("""
            SELECT LOWER(v.username) as lower_name, v.username as real_name, COALESCE(d.watchtime, 0) as daily_watchtime
            FROM viewers v
            JOIN viewer_daily_stats d ON v.twitch_id = d.twitch_id
            WHERE d.day = CURRENT_DATE AND d.watchtime > 0
        """)
        db_rows = await rows.fetchall()
        
        # On stocke leurs données dans le dictionnaire
        for r in db_rows:
            session_data[r['lower_name']] = {
                'real_name': r['real_name'],
                'watchtime': r['daily_watchtime']
            }

    # On rajoute les NOUVEAUX (présents dans l'API Twitch en direct mais pas encore sauvés en base car ils viennent d'arriver)
    for username in all_usernames:
        if username not in session_data:
            session_data[username] = {
                'real_name': username,
                'watchtime': 0
            }

    # 4. Construction de la liste des 'viewers' finale
    final_stats = credits_service.get_stats().copy()
    
    # Dictionnaire magique pour regrouper absolument tout le monde sans faire de doublons
    all_viewers_dict = {}

    # A. On ajoute ceux qu'on a trouvé via la Base de données ou l'API Twitch
    for lower_name, info in session_data.items():
        all_viewers_dict[lower_name] = {
            "name": info['real_name'],
            "watchtime": info['watchtime'] // 60  # Conversion en minutes
        }

    # B. L'EXIGENCE ABSOLUE : On force l'intégration de TOUTES les personnes présentes dans n'importe quelle catégorie !
    for cat_name, users_in_cat in final_stats.items():
        for u in users_in_cat:
            uname = u['name'].lower()
            wt = u.get('watchtime', 0)
            
            if uname not in all_viewers_dict:
                # Le viewer a parlé mais n'est pas dans la liste de base ? On l'ajoute de force !
                all_viewers_dict[uname] = {
                    "name": u['name'],
                    "watchtime": wt
                }
            else:
                # S'il y était déjà, on s'assure de garder son temps de visionnage le plus élevé
                if wt > all_viewers_dict[uname]['watchtime']:
                    all_viewers_dict[uname]['watchtime'] = wt

    # C. Filtrage des bots et création de la liste finale
    exclusion_list = ['masthom_', 'felixthebigblackcat', 'streamelements', 'wizebot', 'nightbot']
    viewers_list = []
    
    for lower_name, data in all_viewers_dict.items():
        if lower_name not in exclusion_list:
            viewers_list.append({
                "name": data['name'],
                "watchtime": data['watchtime']
            })

    # On trie du plus grand temps de visionnage au plus petit
    viewers_list.sort(key=lambda x: x['watchtime'], reverse=True)

    # On écrase l'ancienne liste par notre super-liste complète
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
    
    # ✅ LE COUP DE BALAI POUR LES VIEWERS
    try:
        async with get_db_connection() as conn:
            # On remet le temps de présence à 0 pour tous ceux enregistrés aujourd'hui
            await conn.execute("UPDATE viewer_daily_stats SET watchtime = 0 WHERE day = CURRENT_DATE")
    except Exception as e:
        logger.error(f"❌ Erreur lors du reset du watchtime : {e}")

    return {"status": "success"}

@router.post("/api/credits/test")
async def inject_test_data():
    """Génère des faux noms très complets pour tester l'overlay et le Studio."""
    
    # 1. Catégories à Labels (Subs, Gifts, Bits, Raids, Followers)
    credits_service.log_event("subscribers", "Vestale7", "1")
    credits_service.log_event("subscribers", "LAntreDeSilver", "15")
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
