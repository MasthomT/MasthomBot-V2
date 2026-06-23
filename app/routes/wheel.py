"""
app/routes/wheel.py — Roues de la fortune configurables (admin + overlay OBS).

Routes admin (protégées) :
  GET    /admin/wheels                  -> page de gestion (CRUD + bouton "Lancer")
  GET    /admin/api/wheels              -> liste des roues
  POST   /admin/api/wheels              -> création
  PUT    /admin/api/wheels/{id}         -> édition
  DELETE /admin/api/wheels/{id}         -> suppression
  POST   /admin/api/wheels/{id}/spin    -> tire un gagnant et déclenche l'overlay

Routes publiques (overlay OBS, pas d'auth — comme les autres /overlay/*) :
  GET /overlay/wheel/{id}    -> page affichée dans OBS pour CETTE roue précise
  GET /api/v1/wheels/{id}    -> données de la roue (pour que l'overlay les charge)
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import require_admin
from app.services import wheel_service
from app.services.twitch_service import twitch_bot
from app.routes.overlays import trigger_overlay_event

# Doit correspondre au temps d'animation de la roue côté overlay (wheel_overlay.html,
# transition CSS de 5.5s + petite marge) pour que le message arrive pile quand elle s'arrête.
SPIN_ANIMATION_SECONDS = 5.8

logger = logging.getLogger("masthbot.wheel_routes")
router = APIRouter(tags=["wheel"])
templates = Jinja2Templates(directory="app/templates")


class WheelItemPayload(BaseModel):
    label: str
    color: str = "#6366f1"
    weight: float = 1


class WheelPayload(BaseModel):
    name: str
    items: list[WheelItemPayload]


# ── Admin ────────────────────────────────────────────────────────────────────

@router.get("/admin/wheels", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_wheels_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/wheel_manager.html")


@router.get("/admin/api/wheels", dependencies=[Depends(require_admin)])
async def list_wheels():
    return {"wheels": await wheel_service.get_all_wheels()}


@router.post("/admin/api/wheels", dependencies=[Depends(require_admin)])
async def create_wheel(payload: WheelPayload):
    if not payload.items or len(payload.items) < 2:
        raise HTTPException(status_code=400, detail="Il faut au moins 2 segments sur la roue.")
    wheel_id = await wheel_service.create_wheel(payload.name, [i.model_dump() for i in payload.items])
    return {"status": "ok", "id": wheel_id}


@router.put("/admin/api/wheels/{wheel_id}", dependencies=[Depends(require_admin)])
async def edit_wheel(wheel_id: int, payload: WheelPayload):
    if not payload.items or len(payload.items) < 2:
        raise HTTPException(status_code=400, detail="Il faut au moins 2 segments sur la roue.")
    await wheel_service.update_wheel(wheel_id, payload.name, [i.model_dump() for i in payload.items])
    return {"status": "ok"}


@router.delete("/admin/api/wheels/{wheel_id}", dependencies=[Depends(require_admin)])
async def remove_wheel(wheel_id: int):
    await wheel_service.delete_wheel(wheel_id)
    return {"status": "ok"}


@router.post("/admin/api/wheels/{wheel_id}/spin", dependencies=[Depends(require_admin)])
async def spin_wheel(wheel_id: int):
    wheel = await wheel_service.get_wheel(wheel_id)
    if not wheel:
        raise HTTPException(status_code=404, detail="Roue introuvable.")
    if len(wheel["items"]) < 2:
        raise HTTPException(status_code=400, detail="Il faut au moins 2 segments sur la roue.")

    winner_index = wheel_service.pick_winner(wheel["items"])
    winner = wheel["items"][winner_index]
    await trigger_overlay_event({
        "type": "spin_wheel",
        "wheel_id": wheel_id,
        "winner_index": winner_index,
    })
    asyncio.create_task(_announce_winner_in_chat(winner["label"]))
    return {"status": "ok", "winner_index": winner_index, "winner": winner}


async def _announce_winner_in_chat(label: str) -> None:
    """Envoyé en tâche de fond, décalé pour arriver pile quand la roue s'arrête visuellement."""
    try:
        await asyncio.sleep(SPIN_ANIMATION_SECONDS)
        channel_name = settings.TWITCH_CHANNEL.replace("#", "").lower()
        channel = twitch_bot.get_channel(channel_name)
        if channel:
            await channel.send(f"🎡 Le résultat est : {label}")
    except Exception as e:
        logger.error(f"❌ [WHEEL] Échec annonce résultat dans le chat : {e}")


# ── Overlay (public, pour OBS) ──────────────────────────────────────────────

@router.get("/overlay/wheel/{wheel_id}", response_class=HTMLResponse)
async def wheel_overlay_page(request: Request, wheel_id: int):
    return templates.TemplateResponse(
        request=request, name="overlays/wheel_overlay.html", context={"wheel_id": wheel_id}
    )


@router.get("/api/v1/wheels/{wheel_id}")
async def get_wheel_public(wheel_id: int):
    wheel = await wheel_service.get_wheel(wheel_id)
    if not wheel:
        return JSONResponse(status_code=404, content={"error": "Roue introuvable."})
    return wheel
