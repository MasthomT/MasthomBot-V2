import logging
import os
import shutil
import asyncio
import aiohttp
import httpx # Ajouté pour la requête Twitch
import obsws_python as obs
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.services.shoutout_service import shoutout_service
from app.services.twitch_service import twitch_bot
from app.services.obs_service import obs_service
from app.routes.overlays import trigger_overlay_event

logging.getLogger("obsws_python").setLevel(logging.CRITICAL)

logger = logging.getLogger("masthbot.deck")
router = APIRouter(tags=["deck"])
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = "/home/thomas/masthom/BOT_V2/app/static/uploads"

class DeckAction(BaseModel):
    action: str
    param: str | None = None

# ========================================================
# 📱 AFFICHAGE DES PAGES HTML
# ========================================================
@router.get("/deck", response_class=HTMLResponse)
async def deck_home(request: Request):
    return templates.TemplateResponse(request=request, name="deck.html")

@router.get("/deck/2", response_class=HTMLResponse)
async def deck_page2(request: Request):
    return templates.TemplateResponse(request=request, name="deck_page2.html")

@router.get("/deck/3", response_class=HTMLResponse)
async def deck_page3(request: Request):
    return templates.TemplateResponse(request=request, name="deck_page3.html")

# 🎵 LA ROUTE MAGIQUE POUR AUTORISER OBS À LIRE LES SONS
@router.get("/static/uploads/{file_name}")
async def serve_upload(file_name: str):
    """Sert les fichiers audio/image pour l'Overlay OBS"""
    upload_dir_real = os.path.realpath(UPLOAD_DIR)
    file_path = os.path.realpath(os.path.join(upload_dir_real, file_name))
    if not file_path.startswith(upload_dir_real + os.sep):
        return HTMLResponse(status_code=404)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse(status_code=404)

# ========================================================
# ⚙️ GESTION DES ACTIONS OBS & TWITCH
# ========================================================

# --- FONCTION TWITCH POUR FÉLIX ---
async def toggle_felix_twitch():
    global felix_est_la
    felix_est_la = not felix_est_la 
    
    b_id = getattr(twitch_bot, 'broadcaster_id', None)
    token = getattr(twitch_bot, 'master_token', None)
    client_id = os.getenv("TWITCH_CLIENT_ID", getattr(twitch_bot._http, 'client_id', ''))

    if not b_id or not token:
        logger.error("❌ Impossible de modifier Féli'Cam : Identifiants Twitch manquants.")
        return False

    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}"
    }
    
    payload = {
        "is_enabled": felix_est_la
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={b_id}&id={FELICAM_REWARD_ID}",
                headers=headers,
                json=payload
            )
            
            if resp.status_code == 200:
                etat = "ACTIVÉE" if felix_est_la else "DÉSACTIVÉE"
                logger.info(f"🐱 Féli'Cam {etat} avec succès sur Twitch.")
                return True
            else:
                logger.error(f"❌ Erreur Twitch ({resp.status_code}) lors de la modification de Féli'Cam: {resp.text}")
                # En cas d'erreur de Twitch (ex: mauvais ID, pas les droits), on annule le changement local
                felix_est_la = not felix_est_la 
                return False
                
    except Exception as e:
        logger.error(f"❌ Erreur de connexion Twitch pour Félix : {e}")
        felix_est_la = not felix_est_la 
        return False


@router.get("/api/deck/status")
async def deck_status():
    def fetch_obs_status():
        try:
            cl = obs.ReqClient(host=obs_service.host, port=obs_service.port, password=obs_service.password, timeout=1)
            scene_name = cl.get_current_program_scene().current_program_scene_name
            is_muted = cl.get_input_mute("Micro").input_muted

            cam_visible = True
            for item in cl.get_scene_item_list(scene_name).scene_items:
                if item['sourceName'] == "WEBCAM":
                    cam_visible = item['sceneItemEnabled']
                    break

            # 🎥 STATUT FÉLICAM OBS
            felicam_visible = False
            try:
                for item in cl.get_scene_item_list("SI - ALERTES").scene_items:
                    if item['sourceName'] == "FELI'CAM":
                        felicam_visible = item['sceneItemEnabled']
                        break
            except Exception:
                pass

            return {"scene": scene_name, "mic_muted": is_muted, "cam_visible": cam_visible, "felicam_visible": felicam_visible}
        except Exception:
            return {"scene": "main", "mic_muted": False, "cam_visible": True, "felicam_visible": False}

    obs_status = await asyncio.to_thread(fetch_obs_status)
    twitch_status = {"brb_active": False, "emote_only": False, "follower_only": False, "slow_mode": False}

    # 🐱 STATUT PRÉSENCE FÉLIX (Fichier texte)
    felix_present = False
    state_file = "/home/thomas/masthom/BOT_V2/felix_state.txt"
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                felix_present = (f.read().strip() == "1")
        except Exception:
            pass

    return {
        "twitch": twitch_status,
        "obs": obs_status,
        "felix_present": felix_present # LES DEUX SONT ENVOYÉS AU DECK !
    }

@router.post("/api/deck/action")
async def deck_action(data: DeckAction):
    logger.info(f"📱 [DECK] Clic reçu : {data.action} ({data.param})")

    # --- 1. ACTION PRÉSENCE FÉLIX (Pour l'Overlay Patte) ---
    if data.action == "toggle_felix":
        state_file = "/home/thomas/masthom/BOT_V2/felix_state.txt"
        actuel = False
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    actuel = (f.read().strip() == "1")
            except Exception:
                pass
        
        nouvel_etat = not actuel
        with open(state_file, "w") as f:
            f.write("1" if nouvel_etat else "0")
        return {"status": "success"}

    # --- 2. ACTION FÉLICAM OBS (Pour afficher la caméra) ---
    if data.action == "toggle_felicam_obs":
        def execute_felicam():
            cl = obs.ReqClient(host=obs_service.host, port=obs_service.port, password=obs_service.password)
            scene = "SI - ALERTES"
            source = "FELI'CAM"
            
            items = cl.get_scene_item_list(scene).scene_items
            item_id = None
            is_visible = False
            for item in items:
                if item['sourceName'] == source:
                    item_id = item['sceneItemId']
                    is_visible = item['sceneItemEnabled']
                    break
            
            if item_id is not None:
                if not is_visible:
                    try: cl.set_source_filter_enabled(scene, "FELICAM_IN", True)
                    except: pass
                    cl.set_scene_item_enabled(scene, item_id, True)
                else:
                    cl.set_scene_item_enabled(scene, item_id, False)
                    try: cl.set_source_filter_enabled(scene, "FELICAM_OUT", True)
                    except: pass

        try:
            await asyncio.to_thread(execute_felicam)
        except Exception as e:
            logger.error(f"❌ Erreur Toggle FeliCam : {e}")
        return {"status": "success"}

    # --- RESTE DES ACTIONS OBS CLASSIQUES ---
    if data.action.startswith("obs_") or data.action.startswith("mode_"):
        def execute_obs():
            cl = obs.ReqClient(host=obs_service.host, port=obs_service.port, password=obs_service.password)
            if data.action in ["obs_change_scene", "mode_chatting_filters", "mode_gaming_filters"]:
                cl.set_current_program_scene(data.param)
            elif data.action == "obs_hotkey":
                cl.trigger_hotkey_by_key_sequence(data.param)
            elif data.action == "obs_toggle_mute":
                cl.toggle_input_mute(data.param or "Micro")
            elif data.action == "obs_toggle_source":
                scene_name = cl.get_current_program_scene().current_program_scene_name
                for item in cl.get_scene_item_list(scene_name).scene_items:
                    if item['sourceName'] == (data.param or "WEBCAM"):
                        cl.set_scene_item_enabled(scene_name, item['sceneItemId'], not item['sceneItemEnabled'])
                        break
        try:
            await asyncio.to_thread(execute_obs)
        except Exception as e:
            pass
        return {"status": "success"}

    # --- ACTIONS TWITCH ---
    b_id = getattr(twitch_bot, 'broadcaster_id', None)
    token = getattr(twitch_bot, 'master_token', None)
    client_id = os.getenv("TWITCH_CLIENT_ID", getattr(twitch_bot._http, 'client_id', ''))

    if b_id and token and data.action in ["clear", "chat_mode", "ad", "marker"]:
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            try:
                if data.action == "clear": await session.delete(f"https://api.twitch.tv/helix/moderation/chat?broadcaster_id={b_id}&moderator_id={b_id}", headers=headers)
            except Exception: pass
        return {"status": "success"}

    return {"status": "success"}

@router.post("/api/instant-replay")
async def deck_replay():
    await shoutout_service.trigger_replay()
    return {"status": "success"}

# ========================================================
# 🎵 GESTION DE LA PAGE 3 (SONS & IMAGES)
# ========================================================
from app.core.database import get_db_connection

@router.get("/api/deck/buttons")
async def deck_buttons():
    try:
        async with get_db_connection() as conn:
            # 1. Création de la table (Syntaxe PostgreSQL : SERIAL PRIMARY KEY)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS deck_buttons (
                    id SERIAL PRIMARY KEY, 
                    label TEXT, 
                    type TEXT, 
                    mode TEXT, 
                    file TEXT,
                    volume INTEGER DEFAULT 100
                )
            """)

            # 🧠 2. Mise à jour automatique propre
            try:
                await conn.execute("ALTER TABLE deck_buttons ADD COLUMN IF NOT EXISTS volume INTEGER DEFAULT 100")
            except Exception as e:
                pass # Déjà géré par PostgreSQL

            # 3. Initialisation des 12 boutons vides si la table est vierge
            c_count = await conn.execute("SELECT COUNT(*) FROM deck_buttons")
            count_res = await c_count.fetchone()
            if count_res and count_res[0] == 0:
                for _ in range(12):
                    await conn.execute(
                        "INSERT INTO deck_buttons (label, type, mode, file, volume) VALUES ($1, $2, $3, $4, $5)", 
                        ('Vide', 'none', 'click', '', 100)
                    )

            # 4. Retour des boutons
            c_buttons = await conn.execute("SELECT * FROM deck_buttons ORDER BY id ASC")
            buttons = await c_buttons.fetchall()
            return [dict(b) for b in buttons]
            
    except Exception as e:
        logger.error(f"❌ Erreur chargement deck_buttons : {e}")
        return []

@router.post("/api/deck/edit_button")
async def edit_deck_button(
    request: Request,
    id: int = Form(...),
    label: str = Form(...),
    type: str = Form(...),
    mode: str = Form("click"),
    volume: int = Form(100),
    file: UploadFile = File(None)
):
    try:
        filename = None
        
        # Gestion du fichier uploadé
        if file and file.filename:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            safe_name = file.filename.replace(" ", "_").replace("'", "")
            file_path = os.path.join(UPLOAD_DIR, safe_name)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            filename = f"/static/uploads/{safe_name}"
        else:
            # Récupération de l'ancien fichier si rien n'est uploadé
            async with get_db_connection() as conn:
                c_old = await conn.execute("SELECT file FROM deck_buttons WHERE id=$1", (id,))
                old_data = await c_old.fetchone()
                if old_data:
                    filename = old_data['file']

        # Cas d'un bouton vidé
        if type == "none":
            filename = ""
            label = "Vide"

        # 💾 Sauvegarde globale avec PostgreSQL
        async with get_db_connection() as conn:
            await conn.execute("""
                UPDATE deck_buttons 
                SET label=$1, type=$2, mode=$3, file=$4, volume=$5 
                WHERE id=$6
            """, (label, type, mode, filename, volume, id))
            
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde bouton : {e}")

    return RedirectResponse(url="/deck/3", status_code=303)

@router.post("/api/trigger-effect")
async def trigger_effect(payload: dict):
    try:
        await trigger_overlay_event({"type": "play_sound", "details": payload})
    except Exception as e:
        logger.error(f"Erreur Overlay (Play) : {e}")
    return {"status": "success"}

@router.post("/api/stop-effect")
async def stop_effect(payload: dict):
    try:
        await trigger_overlay_event({"type": "stop_sound", "details": payload})
    except Exception as e:
        logger.error(f"Erreur Overlay (Stop) : {e}")
    return {"status": "success"}
