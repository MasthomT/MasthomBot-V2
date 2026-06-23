import time
import asyncio
import logging
import os
import shutil
import aiohttp

from fastapi import APIRouter, Depends, HTTPException, Request, Form, File, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.premium_service import premium_service
from app.repositories import viewer_repo
from app.routes.overlays import trigger_overlay_event
from app.services.obs_service import obs_service
from app.core.security import require_admin
logger = logging.getLogger("masthbot.premium_routes")
router = APIRouter(tags=["premium"])

# 👉 C'EST CETTE LIGNE QUI MANQUAIT OU ÉTAIT MAL PLACÉE :
templates = Jinja2Templates(directory="app/templates")

_premium_cooldowns = {}

# ==========================================
# 🛠️ ROUTES POUR TON MINI PC (ADMIN)
# ==========================================

async def send_to_external_overlay(action_type: str, action_value: str, username: str):
    """Envoie l'ordre au format exact attendu par l'overlay Node.js."""
    url = "http://192.168.1.32:3005/alerts"
    
    # L'overlay JS utilise le type 'image' pour les vidéos (.mp4)
    overlay_type = "image" if action_type == "video" else action_type

    # L'overlay JS s'attend à trouver le fichier dans d.details.filename
    payload = {
        "type": overlay_type,
        "details": {
            "filename": action_value,
            "username": username
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload)
    except Exception as e:
        logger.error(f"❌ Erreur de communication avec l'overlay 3005 : {e}")

@router.get("/api/admin/premium/actions", dependencies=[Depends(require_admin)])
async def get_all_actions():
    """Renvoie TOUTES les actions pour ton interface mini PC."""
    actions = await premium_service.get_all_actions()
    return {"status": "success", "data": actions}

@router.post("/api/admin/premium/toggle", dependencies=[Depends(require_admin)])
async def toggle_action(payload: dict):
    """Active ou désactive un bouton depuis ton mini PC."""
    action_id = payload.get("id")
    is_active = payload.get("is_active")
    
    if action_id is None or is_active is None:
        raise HTTPException(status_code=400, detail="Données incomplètes")
        
    success = await premium_service.toggle_action_status(action_id, is_active)
    if success:
        return {"status": "success", "message": "Statut mis à jour !"}
    raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour.")

@router.get("/admin/premium", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_premium_page(request: Request):
    """Affiche la page web d'administration sur le mini PC."""
    return templates.TemplateResponse(
        request=request,
        name="admin/premium_dashboard.html",
        context={"request": request}
    )

# 📂 Définis les chemins de tes dossiers (adapte-les si besoin)
SOUNDS_DIR = "static/commands/sounds" 
VIDEOS_DIR = "static/commands/images"

@router.get("/api/admin/premium/files/{action_type}", dependencies=[Depends(require_admin)])
async def get_existing_files(action_type: str):
    """Renvoie la liste des fichiers existants sur le serveur (sans l'extension)."""
    target_dir = SOUNDS_DIR if action_type == "sound" else VIDEOS_DIR
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    files = []
    for f in os.listdir(target_dir):
        if os.path.isfile(os.path.join(target_dir, f)):
            files.append(os.path.splitext(f)[0])
            
    return {"status": "success", "data": sorted(files)}


@router.post("/api/admin/premium/add", dependencies=[Depends(require_admin)])
async def admin_add_action(
    name: str = Form(...),
    action_type: str = Form(...),
    action_value: str = Form(""), # Devenu optionnel (vide si on upload un fichier)
    file: UploadFile = File(None) # Le fameux fichier venant de ton PC !
):
    """Reçoit le formulaire, sauvegarde le fichier si fourni, et crée le bouton."""
    final_value = action_value
    
    # 1. GESTION DE L'UPLOAD : Si tu as glissé un fichier depuis ton PC
    if file and file.filename:
        target_dir = SOUNDS_DIR if action_type == "sound" else VIDEOS_DIR
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        safe_filename = file.filename.replace(" ", "_")
        file_path = os.path.join(target_dir, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        final_value = os.path.splitext(safe_filename)[0]

    if not final_value:
        return JSONResponse(status_code=400, content={"detail": "Veuillez choisir un fichier ou taper une source."})

    # 2. Icône automatique
    icon = "fa-bolt"
    if action_type == "sound": icon = "fa-music"
    elif action_type == "video": icon = "fa-film"
    elif action_type == "obs_source": icon = "fa-video"

    # 3. Enregistrement
    success = await premium_service.add_action(name, icon, action_type, final_value)
    if success:
        return {"status": "success", "message": f"Bouton ajouté avec succès !"}
    return JSONResponse(status_code=500, content={"detail": "Erreur serveur."})

@router.post("/api/admin/premium/trigger", dependencies=[Depends(require_admin)])
async def admin_force_trigger(payload: dict):
    """Déclenchement direct depuis le mini PC (Pas de vérification, pas de cooldown)."""
    action_type = payload.get("action_type")
    action_value = payload.get("action_value")

    try:
        if action_type == "sound":
            # 👉 Envoi vers l'alerte sur le port 3005
            await send_to_external_overlay("sound", f"{action_value}.mp3", "Le Boss")
            
        elif action_type == "video":
            # 👉 Envoi vers l'alerte sur le port 3005
            await send_to_external_overlay("video", f"{action_value}.mp4", "Le Boss")
            
        elif action_type == "obs_source":
            # 👉 L'action native OBS ne bouge pas
            await obs_service.set_source_visibility(scene_name="SI - ZONE_VIP", source_name=action_value, visible=True)
            async def turn_off_later():
                await asyncio.sleep(5)
                await obs_service.set_source_visibility(scene_name="SI - ZONE_VIP", source_name=action_value, visible=False)
            asyncio.create_task(turn_off_later())

        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

# ==========================================
# 🎮 ROUTES POUR LES VIEWERS (SITE WEB)
# ==========================================

@router.get("/api/premium/actions/active")
async def get_active_actions():
    """Renvoie UNIQUEMENT les actions actives pour la page des VIPs."""
    actions = await premium_service.get_active_actions()
    return {"status": "success", "data": actions}

@router.post("/api/premium/action/trigger")
async def trigger_premium_action(payload: dict):
    """Le déclencheur Hybride pour les VIEWERS (Sons, Vidéos, OBS)."""
    twitch_id = payload.get("twitch_id")
    action_type = payload.get("action_type")   
    action_value = payload.get("action_value") 

    if not twitch_id or not action_type or not action_value:
        return JSONResponse(status_code=400, content={"detail": "Données incomplètes."})

    # --- 1. VIGILE : Vérification des droits ---
    viewer = await viewer_repo.get_viewer(twitch_id)
    if not viewer: 
        return JSONResponse(status_code=404, content={"detail": "Utilisateur non trouvé."})
    
    viewer = dict(viewer)
    is_premium = viewer.get("is_sub", 0) == 1 or viewer.get("is_vip", 0) == 1 or viewer.get("is_mod", 0) == 1
    is_boss = viewer.get("username", "").lower() == "masthom_"
    
    if not is_premium and not is_boss: 
        return JSONResponse(status_code=403, content={"detail": "🔒 Réservé Premium !"})

    # --- 2. ANTI-SPAM : Cooldown (sauf pour le boss) ---
    now = time.time()
    last_used = _premium_cooldowns.get(twitch_id, 0)
    cooldown_time = 30 
    
    if not is_boss and (now - last_used < cooldown_time):
        return JSONResponse(status_code=429, content={"detail": f"⏳ Recharge... ({int(cooldown_time - (now - last_used))}s)"})
    
    _premium_cooldowns[twitch_id] = now

    # --- 3. EXÉCUTION HYBRIDE ---
    try:
        if action_type == "sound":
            # 👉 Envoi vers l'alerte sur le port 3005 avec le nom du VIEWER
            await send_to_external_overlay("sound", f"{action_value}.mp3", viewer.get("username", "Un VIP"))
            return {"status": "success", "message": "🎵 Son activé !"}

        elif action_type == "video":
            # 👉 Envoi vers l'alerte sur le port 3005 avec le nom du VIEWER
            await send_to_external_overlay("video", f"{action_value}.mp4", viewer.get("username", "Un VIP"))
            return {"status": "success", "message": "🎬 Vidéo lancée !"}

        elif action_type == "obs_source":
            # 👉 Action native OBS
            await obs_service.set_source_visibility(scene_name="SI - ZONE_VIP", source_name=action_value, visible=True)
            async def turn_off_later():
                await asyncio.sleep(5)
                await obs_service.set_source_visibility(scene_name="SI - ZONE_VIP", source_name=action_value, visible=False)
            asyncio.create_task(turn_off_later())

            return {"status": "success", "message": "🎥 Effet activé !"}

        else:
            return JSONResponse(status_code=400, content={"detail": "Type d'action inconnu."})

    except Exception as e:
        logger.error(f"Erreur Action Hybride : {e}")
        return JSONResponse(status_code=500, content={"detail": "Erreur d'exécution."})
