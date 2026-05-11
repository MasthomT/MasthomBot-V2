import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("masthbot.overlays")
router = APIRouter(tags=["overlays"])
templates = Jinja2Templates(directory="app/templates")

# ==========================================
# 📡 1. MOTEURS DE DIFFUSION (SSE & WEBSOCKET)
# ==========================================

# Liste des clients connectés en SSE (Streaming)
sse_clients = []
# Liste des clients connectés en WebSocket (Pour l'Overlay Deck)
ws_clients = set()

async def event_generator(request: Request):
    """Générateur pour le système SSE (Server-Sent Events)"""
    queue = asyncio.Queue()
    sse_clients.append(queue)
    try:
        while True:
            if await request.is_disconnected():
                break
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        if queue in sse_clients:
            sse_clients.remove(queue)

@router.get("/overlay_events")
async def sse_endpoint(request: Request):
    """Route pour les anciens overlays utilisant SSE"""
    return StreamingResponse(event_generator(request), media_type="text/event-stream")

@router.websocket("/ws/overlay")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    
    # On utilise .debug() au lieu de .info() pour ne pas spammer la console standard
    logger.debug(f"✅ [WS] Nouveau client connecté. Total: {len(ws_clients)}")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_clients.remove(websocket)
        logger.debug(f"❌ [WS] Client déconnecté. Restants: {len(ws_clients)}")
    except Exception as e:
        if websocket in ws_clients:
            ws_clients.remove(websocket)
        # On garde les vraies erreurs en rouge pour pouvoir corriger les bugs
        logger.error(f"⚠️ [WS] Erreur inattendue : {e}")

async def trigger_overlay_event(payload: dict):
    """
    Fonction universelle pour envoyer une alerte (Son, Image, Trophée).
    Diffuse l'information à TOUS les clients connectés (SSE et WS).
    """
    # 1. Envoi aux clients SSE
    for queue in sse_clients:
        await queue.put(payload)
        
    # 2. Envoi aux clients WebSocket (Sons Deck, etc.)
    if ws_clients:
        # On crée une liste de tâches pour envoyer à tout le monde en même temps
        disconnected = []
        for client in ws_clients:
            try:
                await client.send_json(payload)
            except Exception:
                disconnected.append(client)
        
        # Nettoyage des clients qui ont crashé
        for client in disconnected:
            if client in ws_clients:
                ws_clients.remove(client)

# ==========================================
# 2. ROUTES DES PAGES HTML (OBS)
# ==========================================

@router.get("/overlay/emotes", response_class=HTMLResponse)
async def get_emote_wall(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/emote_wall.html")

@router.get("/overlay/time", response_class=HTMLResponse)
async def get_time_overlay(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/time_overlay.html")

@router.get("/overlay/credits", response_class=HTMLResponse)
async def get_credits_overlay(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/credits.html")

@router.get("/overlay/poll", response_class=HTMLResponse)
async def get_poll_overlay(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/poll_overlay.html")

@router.get("/overlay/trophies", response_class=HTMLResponse)
async def get_trophies_overlay(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/trophy_overlay.html")

@router.get("/overlay_deck", response_class=HTMLResponse)
async def get_deck_overlay(request: Request):
    """Route pour l'overlay dédié aux sons et images du Deck"""
    return templates.TemplateResponse(request=request, name="overlay_deck.html")

@router.get("/overlay/felix", response_class=HTMLResponse)
async def felix_overlay_page(request:Request):
    return templates.TemplateResponse(request=request, name="felix_overlay.html")

@router.get("/overlay/twitch_poll", response_class=HTMLResponse)
async def get_twitch_poll_overlay(request: Request):
    """
    Route corrigée pour pointer vers le fichier EXACT.
    Assure-toi que le fichier s'appelle bien twitch_poll_overlay.html 
    dans le dossier app/templates/overlays/
    """
    return templates.TemplateResponse(
        request=request, 
        name="overlays/twitch_poll_overlay.html" # Vérifie bien ce nom !
    )
