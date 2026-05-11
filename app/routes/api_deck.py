import sqlite3
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

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"
UPLOAD_DIR = "/home/masthom/BOT_V2/app/static/uploads"

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

@router.get("/overlay_deck", response_class=HTMLResponse)
async def deck_overlay_page(request: Request):
    return templates.TemplateResponse(request=request, name="overlay_deck.html")

# 🎵 LA ROUTE MAGIQUE POUR AUTORISER OBS À LIRE LES SONS
@router.get("/static/uploads/{file_name}")
async def serve_upload(file_name: str):
    """Sert les fichiers audio/image pour l'Overlay OBS"""
    file_path = os.path.join(UPLOAD_DIR, file_name)
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
    state_file = "/home/masthom/BOT_V2/felix_state.txt"
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
        state_file = "/home/masthom/BOT_V2/felix_state.txt"
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
    shoutout_service.trigger_replay()
    return {"status": "success"}

# ========================================================
# 🎵 GESTION DE LA PAGE 3 (SONS & IMAGES)
# ========================================================
@router.get("/api/deck/buttons")
async def deck_buttons():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS deck_buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, type TEXT, mode TEXT, file TEXT)")
        
        # 🧠 Mise à jour automatique de la base de données pour le Volume
        try:
            conn.execute("SELECT volume FROM deck_buttons LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE deck_buttons ADD COLUMN volume INTEGER DEFAULT 100")
            conn.commit()

        if conn.execute("SELECT COUNT(*) FROM deck_buttons").fetchone()[0] == 0:
            for _ in range(12): 
                conn.execute("INSERT INTO deck_buttons (label, type, mode, file, volume) VALUES ('Vide', 'none', 'click', '', 100)")
            conn.commit()
            
        return [dict(b) for b in conn.execute("SELECT * FROM deck_buttons").fetchall()]
    finally:
        conn.close()

@router.post("/api/deck/edit_button")
async def edit_deck_button(
    request: Request, 
    id: int = Form(...), 
    label: str = Form(...), 
    type: str = Form(...), 
    mode: str = Form("click"), 
    volume: int = Form(100), # 🎚️ Nouveau paramètre reçu du formulaire
    file: UploadFile = File(None)
):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 5000")
    
    try:
        filename = None
        if file and file.filename:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            safe_name = file.filename.replace(" ", "_").replace("'", "")
            file_path = os.path.join(UPLOAD_DIR, safe_name)
            with open(file_path, "wb") as buffer: 
                shutil.copyfileobj(file.file, buffer)
            filename = f"/static/uploads/{safe_name}"
        else:
            old_data = conn.execute("SELECT file FROM deck_buttons WHERE id=?", (id,)).fetchone()
            if old_data:
                filename = old_data[0]

        if type == "none":
            filename = ""
            label = "Vide"

        # 💾 On sauvegarde le volume avec le reste
        conn.execute("UPDATE deck_buttons SET label=?, type=?, mode=?, file=?, volume=? WHERE id=?", 
                     (label, type, mode, filename, volume, id))
        conn.commit()
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde bouton : {e}")
    finally:
        conn.close()
        
    return RedirectResponse(url="/deck/3", status_code=303)

@router.post("/api/trigger-effect")
async def trigger_effect(payload: dict):
    try: 
        await trigger_overlay_event({"type": "play_sound", "details": payload})
    except Exception as e:
        logger.error(f"Erreur Overlay : {e}")
    return {"status": "success"}

@router.post("/api/stop-effect")
async def stop_effect(payload: dict):
    try: 
        await trigger_overlay_event({"type": "stop_sound", "details": payload})
    except Exception as e:
        logger.error(f"Erreur Overlay : {e}")
    return {"status": "success"}
