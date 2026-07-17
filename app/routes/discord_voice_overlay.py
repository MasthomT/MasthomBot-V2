"""
app/routes/discord_voice_overlay.py — Route de l'overlay "salon vocal Discord" maison.

Servi sur le port dédié 8001 (media_app, cf. app/main.py) et non sur le 8000 : c'est un
WebSocket permanent comme les autres overlays temps réel, et OBS limite déjà les connexions
à ~6 par origine sur le port 8000 (cf. commentaire dans main.py à propos du proxy TikTok et
des labels) — l'ajouter là-bas aurait recréé exactement le problème de connexions saturées
qui causait les échecs de fetch observés sur les overlays labels/felix.
"""
import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.discord_voice_overlay_service import discord_voice_overlay_service

logger = logging.getLogger("masthbot.discord_voice_overlay_route")
router = APIRouter(tags=["discord_voice_overlay"])
templates = Jinja2Templates(directory="app/templates")

NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


@router.get("/overlay/discord_voice", response_class=HTMLResponse)
async def get_discord_voice_overlay(request: Request):
    return templates.TemplateResponse(
        request=request, name="overlays/discord_voice_overlay.html", headers=NO_CACHE
    )


@router.websocket("/ws/discord_voice")
async def discord_voice_ws(websocket: WebSocket):
    await websocket.accept()
    await discord_voice_overlay_service.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"⚠️ [WS discord_voice] Erreur inattendue : {e}")
    finally:
        discord_voice_overlay_service.unregister(websocket)
