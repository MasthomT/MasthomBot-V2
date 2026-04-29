import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["overlays"])
templates = Jinja2Templates(directory="app/templates")

# ==========================================
# 1. MOTEUR D'ÉVÉNEMENTS INTERNE (PORT 8000)
# ==========================================
overlay_clients = []

async def event_generator(request: Request):
    queue = asyncio.Queue()
    overlay_clients.append(queue)
    try:
        while True:
            if await request.is_disconnected():
                break
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        if queue in overlay_clients:
            overlay_clients.remove(queue)

@router.get("/overlay_events")
async def sse_endpoint(request: Request):
    """La source que l'overlay OBS va écouter pour recevoir les alertes"""
    return StreamingResponse(event_generator(request), media_type="text/event-stream")

async def trigger_overlay_event(payload: dict):
    """La fonction appelée par rewards.py pour envoyer l'alerte !"""
    for queue in overlay_clients:
        await queue.put(payload)


# ==========================================
# 2. ROUTES DES PAGES OBS (TES PAGES)
# ==========================================
@router.get("/overlay/emotes", response_class=HTMLResponse)
async def get_emote_wall(request: Request):
    """Affiche le mur d'emotes pour OBS"""
    return templates.TemplateResponse(request=request, name="overlays/emote_wall.html")

@router.get("/overlay/time", response_class=HTMLResponse)
async def get_time_overlay(request: Request):
    """Affiche le timer/chrono pour OBS"""
    return templates.TemplateResponse(request=request, name="overlays/time_overlay.html")

@router.get("/overlay/credits", response_class=HTMLResponse)
async def get_credits_overlay(request: Request):
    """Affiche l'overlay du générique de fin pour OBS"""
    return templates.TemplateResponse(request=request, name="overlays/credits.html")

@router.get("/overlay/poll", response_class=HTMLResponse)
async def get_poll_overlay(request: Request):
    """Affiche le widget automatique des sondages pour OBS"""
    return templates.TemplateResponse(request=request, name="overlays/poll_overlay.html")

@router.get("/overlay/trophies", response_class=HTMLResponse)
async def get_trophies_overlay(request: Request):
    """Affiche les popups d'alertes de trophées pour OBS"""
    return templates.TemplateResponse(request=request, name="overlays/trophy_overlay.html")
