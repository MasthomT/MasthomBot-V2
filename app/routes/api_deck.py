import sqlite3
import logging
import os
import shutil
import asyncio
import aiohttp
import obsws_python as obs
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.services.shoutout_service import shoutout_service
from app.services.twitch_service import twitch_bot
from app.services.obs_service import obs_service
from app.routes.overlays import trigger_overlay_event 

logging.getLogger("obsws_python").setLevel(logging.WARNING)

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
@router.get("/api/deck/status")
async def deck_status():
    def fetch_obs_status():
        try:
            cl = obs.ReqClient(host=obs_service.host, port=obs_service.port, password=obs_service.password)
            scene_name = cl.get_current_program_scene().current_program_scene_name
            is_muted = cl.get_input_mute("Micro").input_muted
            
            cam_visible = True
            for item in cl.get_scene_item_list(scene_name).scene_items:
                if item['sourceName'] == "WEBCAM":
                    cam_visible = item['sceneItemEnabled']
                    break
                    
            return {"scene": scene_name, "mic_muted": is_muted, "cam_visible": cam_visible}
        except Exception:
            return {"scene": "main", "mic_muted": False, "cam_visible": True}

    obs_status = await asyncio.to_thread(fetch_obs_status)
    twitch_status = {"brb_active": False, "emote_only": False, "follower_only": False, "slow_mode": False}
    return {"twitch": twitch_status, "obs": obs_status}

@router.post("/api/deck/action")
async def deck_action(data: DeckAction):
    logger.info(f"📱 [DECK] Clic reçu : {data.action} ({data.param})")
    
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
            logger.error(f"❌ Erreur Contrôle OBS Python : {e}")
        return {"status": "success"}

    b_id = getattr(twitch_bot, 'broadcaster_id', None)
    token = getattr(twitch_bot, 'master_token', None)
    client_id = os.getenv("TWITCH_CLIENT_ID", getattr(twitch_bot._http, 'client_id', ''))

    if b_id and token and data.action in ["clear", "chat_mode", "ad", "marker"]:
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            try:
                if data.action == "clear":
                    await session.delete(f"https://api.twitch.tv/helix/moderation/chat?broadcaster_id={b_id}&moderator_id={b_id}", headers=headers)
                elif data.action == "chat_mode":
                    url = f"https://api.twitch.tv/helix/chat/settings?broadcaster_id={b_id}&moderator_id={b_id}"
                    if data.param == "emote": await session.patch(url, headers=headers, json={"emote_mode": True})
                    elif data.param == "follower": await session.patch(url, headers=headers, json={"follower_mode": True})
                    elif data.param == "slow": await session.patch(url, headers=headers, json={"slow_mode": True})
                    elif data.param == "normal": await session.patch(url, headers=headers, json={"emote_mode": False, "follower_mode": False, "slow_mode": False})
                elif data.action == "ad":
                    await session.post("https://api.twitch.tv/helix/channels/commercial", headers=headers, json={"broadcaster_id": str(b_id), "length": int(data.param or 180)})
                elif data.action == "marker":
                    await session.post("https://api.twitch.tv/helix/streams/markers", headers=headers, json={"user_id": str(b_id)})
            except Exception as e:
                logger.error(f"❌ Erreur API Twitch (Deck) : {e}")
        return {"status": "success"}

    if data.action == "shoutout" and data.param:
        shoutout_service.trigger_shoutout(target=data.param)
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
