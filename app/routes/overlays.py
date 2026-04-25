from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["overlays"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/overlay/emotes", response_class=HTMLResponse)
async def get_emote_wall(request: Request):
    """Affiche le mur d'emotes pour OBS"""
    return templates.TemplateResponse(
        request=request, 
        name="overlays/emote_wall.html"
    )

@router.get("/overlay/time", response_class=HTMLResponse)
async def get_time_overlay(request: Request):
    """Affiche le timer/chrono pour OBS"""
    return templates.TemplateResponse(
        request=request, 
        name="overlays/time_overlay.html"
    )

@router.get("/overlay/credits", response_class=HTMLResponse)
async def get_credits_overlay(request: Request):
    """Affiche l'overlay du générique de fin pour OBS"""
    return templates.TemplateResponse(
        request=request,
        name="overlays/credits.html"
    )

@router.get("/overlay/poll", response_class=HTMLResponse)
async def get_poll_overlay(request: Request):
    """Affiche le widget automatique des sondages pour OBS"""
    return templates.TemplateResponse(
        request=request,
        name="overlays/poll_overlay.html"
    )
