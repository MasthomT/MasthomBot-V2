"""Overlay « Récompenses de points de chaîne » (/overlay/recompenses) et ses réglages (page Récompenses › Overlay).
Voir app/services/reward_overlay_service.py."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.security import require_admin
from app.services import reward_overlay_service as R

NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}
templates = Jinja2Templates(directory="app/templates")

public = APIRouter(tags=["reward-overlay"])
admin = APIRouter(tags=["reward-overlay"], dependencies=[Depends(require_admin)])


@public.get("/overlay/recompenses", response_class=HTMLResponse)
async def reward_overlay_page(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/reward_overlay.html", headers=NO_CACHE)


@public.get("/api/reward-overlay/events")
async def reward_overlay_events(after: int = 0):
    return JSONResponse(R.events_after(after), headers=NO_CACHE)


@admin.get("/admin/api/reward-overlay")
async def reward_overlay_settings():
    from app.services.automation_service import media_files
    return {"visuals": await R.list_visuals(), "media": media_files()}


@admin.put("/admin/api/reward-overlay")
async def reward_overlay_save(payload: dict):
    try:
        return {"visual": await R.save_visual(payload or {})}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@admin.delete("/admin/api/reward-overlay")
async def reward_overlay_delete(title: str):
    await R.delete_visual(title)
    return {"status": "ok"}


@admin.post("/admin/api/reward-overlay/test")
async def reward_overlay_test(payload: dict):
    """Affiche le réglage EN COURS (pas forcément enregistré) sur l'overlay, comme si un viewer avait pris la récompense."""
    try:
        v = R.clean(dict(payload or {}, enabled=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    R.push(v, "Test", test=True)
    return {"ok": True}


@admin.get("/admin/api/reward-overlay/screenshot")
async def reward_overlay_screenshot():
    """Capture de la scène OBS en cours, en fond de la zone de placement."""
    from app.services.obs_service import obs_service
    img = await asyncio.to_thread(obs_service.take_screenshot)
    return {"image": img}
