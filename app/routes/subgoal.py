"""
app/routes/subgoal.py — Page admin "SubGoal" (objectif de subs à paliers, ex: Subtember) +
overlay OBS associé.

Routes admin (protégées) :
  GET  /admin/subgoal                 -> page de gestion (config + CRUD des paliers)
  GET  /admin/api/subgoal/config      -> {since, end_date, linked_wheel_id}
  POST /admin/api/subgoal/config      -> met à jour la période de comptage et la roue liée (optionnelle)
  GET  /admin/api/subgoal/tiers       -> liste des paliers
  POST /admin/api/subgoal/tiers       -> création d'un palier
  PUT  /admin/api/subgoal/tiers/{id}  -> édition
  DELETE /admin/api/subgoal/tiers/{id} -> suppression

Routes publiques (overlay OBS, pas d'auth) :
  GET /overlay/subgoal   -> page affichée dans OBS
  GET /api/v1/subgoal    -> données consommées par l'overlay (paliers + compteurs live)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.security import require_admin
from app.services import subgoal_service
from app.routes.overlays import NO_CACHE
from app.routes.api import get_compteur_defi

logger = logging.getLogger("masthbot.subgoal_routes")
router = APIRouter(tags=["subgoal"])
templates = Jinja2Templates(directory="app/templates")


class TierPayload(BaseModel):
    threshold: int
    label: str


class ConfigPayload(BaseModel):
    since: str
    end_date: str | None = None
    linked_wheel_id: int | None = None


# ── Admin ────────────────────────────────────────────────────────────────────

@router.get("/admin/subgoal", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_subgoal_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/subgoal.html")


@router.get("/admin/api/subgoal/config", dependencies=[Depends(require_admin)])
async def get_subgoal_config():
    return await subgoal_service.get_config()


@router.post("/admin/api/subgoal/config", dependencies=[Depends(require_admin)])
async def save_subgoal_config(payload: ConfigPayload):
    await subgoal_service.set_config(payload.since, payload.end_date, payload.linked_wheel_id)
    return {"status": "ok"}


@router.get("/admin/api/subgoal/tiers", dependencies=[Depends(require_admin)])
async def list_subgoal_tiers():
    return {"tiers": await subgoal_service.get_all_tiers()}


@router.post("/admin/api/subgoal/tiers", dependencies=[Depends(require_admin)])
async def create_subgoal_tier(payload: TierPayload):
    if payload.threshold < 1 or not payload.label.strip():
        raise HTTPException(status_code=400, detail="Palier invalide : nombre de subs et défi requis.")
    tier_id = await subgoal_service.create_tier(payload.threshold, payload.label)
    return {"status": "ok", "id": tier_id}


@router.put("/admin/api/subgoal/tiers/{tier_id}", dependencies=[Depends(require_admin)])
async def edit_subgoal_tier(tier_id: int, payload: TierPayload):
    if payload.threshold < 1 or not payload.label.strip():
        raise HTTPException(status_code=400, detail="Palier invalide : nombre de subs et défi requis.")
    await subgoal_service.update_tier(tier_id, payload.threshold, payload.label)
    return {"status": "ok"}


@router.delete("/admin/api/subgoal/tiers/{tier_id}", dependencies=[Depends(require_admin)])
async def remove_subgoal_tier(tier_id: int):
    await subgoal_service.delete_tier(tier_id)
    return {"status": "ok"}


# ── Overlay (public, pour OBS) ──────────────────────────────────────────────

@router.get("/overlay/subgoal", response_class=HTMLResponse)
async def subgoal_overlay_page(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/subgoal_overlay.html", headers=NO_CACHE)


@router.get("/api/v1/subgoal")
async def get_subgoal_public():
    config = await subgoal_service.get_config()
    counters = await get_compteur_defi(since=config["since"])
    tiers = await subgoal_service.get_all_tiers()
    return {**counters, "tiers": tiers, "end_date": config["end_date"]}
