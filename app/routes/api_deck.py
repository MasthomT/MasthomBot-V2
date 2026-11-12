import logging
import os
import shutil
import asyncio
import time
import aiohttp
import httpx # Ajouté pour la requête Twitch
from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from app.core.security import require_admin
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.services.shoutout_service import shoutout_service
from app.services.twitch_service import twitch_bot
from app.services.obs_service import obs_service
from app.routes.overlays import trigger_overlay_event


logger = logging.getLogger("masthbot.deck")
router = APIRouter(tags=["deck"])
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = "/home/thomas/masthom/BOT_V2/app/static/uploads"

# Cache 10s pour le statut chat Twitch (pollé toutes les 2s par le deck)
_chat_cache: dict = {"data": {"emote_only": False, "follower_only": False, "slow_mode": False}, "ts": 0.0}
_CHAT_CACHE_TTL = 10.0

_chat_status_cache: dict = {"at": 0.0, "value": None}


async def _cached_chat_status(b_id: str, token: str, client_id: str) -> dict:
    """Statut du chat (emote/follow/slow) gardé 10 s : /api/deck/status est interrogée chaque seconde."""
    now = time.time()
    if _chat_status_cache["value"] is None or now - _chat_status_cache["at"] > 10:
        _chat_status_cache["value"] = await _get_twitch_chat_status(b_id, token, client_id)
        _chat_status_cache["at"] = now
    return dict(_chat_status_cache["value"])


async def _get_twitch_chat_status(b_id: str, token: str, client_id: str) -> dict:
    now = time.monotonic()
    if now - _chat_cache["ts"] < _CHAT_CACHE_TTL:
        return _chat_cache["data"]
    try:
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"https://api.twitch.tv/helix/chat/settings?broadcaster_id={b_id}&moderator_id={b_id}",
                headers=headers, timeout=aiohttp.ClientTimeout(total=3)
            ) as resp:
                if resp.status == 200:
                    d = (await resp.json()).get("data", [{}])[0]
                    result = {
                        "emote_only":   d.get("emote_mode", False),
                        "follower_only": d.get("follower_mode", False),
                        "slow_mode":    d.get("slow_mode", False),
                    }
                    _chat_cache["data"] = result
                    _chat_cache["ts"] = now
                    return result
    except Exception:
        pass
    return _chat_cache["data"]

class DeckAction(BaseModel):
    action: str
    param: str | None = None

# ========================================================
# 📱 AFFICHAGE DES PAGES HTML
# ========================================================
@router.get("/deck", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def deck_home(request: Request):
    return templates.TemplateResponse(request=request, name="deck.html")

@router.get("/deck/2", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def deck_page2(request: Request):
    return templates.TemplateResponse(request=request, name="deck_page2.html")

@router.get("/deck/3", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
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
    # État OBS lu par server.js (connexion permanente) : plus de connexion OBS neuve à chaque appel
    # (cette route est interrogée chaque seconde par l'overlay Félix et le Stream Deck).
    obs_status = await asyncio.to_thread(obs_service.get_status)
    obs_status.pop("connected", None)

    b_id = getattr(twitch_bot, 'broadcaster_id', None)
    token = getattr(twitch_bot, 'master_token', None)
    client_id = os.getenv("TWITCH_CLIENT_ID", getattr(twitch_bot._http, 'client_id', ''))
    if b_id and token:
        chat_st = await _cached_chat_status(b_id, token, client_id)
    else:
        chat_st = {"emote_only": False, "follower_only": False, "slow_mode": False}
    twitch_status = {"brb_active": False, **chat_st}

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

@router.post("/api/deck/action", dependencies=[Depends(require_admin)])
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
        await asyncio.to_thread(obs_service.run_action, "felicam_toggle")
        return {"status": "success"}

    # --- RESTE DES ACTIONS OBS CLASSIQUES (exécutées par server.js) ---
    if data.action.startswith("obs_") or data.action.startswith("mode_"):
        if data.action in ["obs_change_scene", "mode_chatting_filters", "mode_gaming_filters"]:
            await asyncio.to_thread(obs_service.run_action, "scene_switch", scene=data.param)
        elif data.action == "obs_hotkey":
            await asyncio.to_thread(obs_service.run_action, "hotkey_sequence", text=data.param)
        elif data.action == "obs_toggle_mute":
            await asyncio.to_thread(obs_service.run_action, "toggle_mute", source=data.param or "Micro")
        elif data.action == "obs_toggle_source":
            await asyncio.to_thread(obs_service.run_action, "source_toggle_current", source=data.param or "WEBCAM")
        return {"status": "success"}

    # --- ACTIONS TWITCH ---
    b_id = getattr(twitch_bot, 'broadcaster_id', None)
    token = getattr(twitch_bot, 'master_token', None)
    client_id = os.getenv("TWITCH_CLIENT_ID", getattr(twitch_bot._http, 'client_id', ''))

    if b_id and token and data.action in ["clear", "chat_mode", "ad", "marker"]:
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        try:
            async with aiohttp.ClientSession() as session:
                if data.action == "clear":
                    await session.delete(
                        f"https://api.twitch.tv/helix/moderation/chat?broadcaster_id={b_id}&moderator_id={b_id}",
                        headers=headers
                    )

                elif data.action == "chat_mode":
                    _MODES = {
                        "emote":    {"emote_mode": True},
                        "follower": {"follower_mode": True, "follower_mode_duration": 0},
                        "slow":     {"slow_mode": True, "slow_mode_wait_time": 30},
                        "normal":   {"emote_mode": False, "follower_mode": False,
                                     "slow_mode": False, "subscriber_mode": False},
                    }
                    body = _MODES.get(data.param or "")
                    if body:
                        resp = await session.patch(
                            f"https://api.twitch.tv/helix/chat/settings?broadcaster_id={b_id}&moderator_id={b_id}",
                            headers=headers, json=body
                        )
                        logger.info(f"💬 [DECK] chat_mode={data.param} → HTTP {resp.status}")
                        _chat_cache["ts"] = 0.0  # force refresh au prochain poll

                elif data.action == "ad":
                    duration = int(data.param or "60")
                    resp = await session.post(
                        "https://api.twitch.tv/helix/channels/commercial",
                        headers=headers,
                        json={"broadcaster_id": b_id, "length": duration}
                    )
                    logger.info(f"📺 [DECK] pub {duration}s → HTTP {resp.status}")

                elif data.action == "marker":
                    resp = await session.post(
                        "https://api.twitch.tv/helix/streams/markers",
                        headers=headers,
                        json={"user_id": b_id, "description": "FelixDeck"}
                    )
                    logger.info(f"📍 [DECK] marker → HTTP {resp.status}")

        except Exception as e:
            logger.error(f"❌ [DECK] action Twitch '{data.action}' : {e}")

        return {"status": "success"}

    return {"status": "success"}

@router.post("/api/instant-replay", dependencies=[Depends(require_admin)])
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

@router.post("/api/deck/edit_button", dependencies=[Depends(require_admin)])
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

@router.post("/api/trigger-effect", dependencies=[Depends(require_admin)])
async def trigger_effect(payload: dict):
    try:
        await trigger_overlay_event({"type": "play_sound", "details": payload})
    except Exception as e:
        logger.error(f"Erreur Overlay (Play) : {e}")
    return {"status": "success"}

@router.post("/api/stop-effect", dependencies=[Depends(require_admin)])
async def stop_effect(payload: dict):
    try:
        await trigger_overlay_event({"type": "stop_sound", "details": payload})
    except Exception as e:
        logger.error(f"Erreur Overlay (Stop) : {e}")
    return {"status": "success"}
