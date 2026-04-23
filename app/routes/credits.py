from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.services.credits_service import credits_service
import json

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
    """L'API que l'overlay appelle pour savoir qui afficher."""
    return {
        "stats": credits_service.get_stats(),
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
    return {"status": "success"}

@router.post("/api/credits/test")
async def inject_test_data():
    """Génère des faux noms pour tester l'overlay."""
    credits_service.log_event("subscribers", "Vestale7", "Tier 1")
    credits_service.log_event("subscribers", "LAntreDeSilver", "Tier 3")
    credits_service.log_event("raiders", "Siphano", "150 viewers")
    credits_service.log_event("bits", "MonkeyMaxou", "500 Bits")
    credits_service.log_event("followers", "Nouvel_Ami", "Bienvenue !")
    credits_service.log_event("chatters", "Masthom")
    return {"status": "test_injected"}
