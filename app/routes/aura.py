"""Aura : couleur du cadre choisie par les viewers (récompense de points de chaîne). Voir app/services/aura_service.py."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import require_admin
from app.services import aura_service as A

public_router = APIRouter(tags=["aura"])
admin_router = APIRouter(tags=["aura_admin"], dependencies=[Depends(require_admin)])


@public_router.get("/api/aura")
async def api_aura():
    """Lue par les overlays toutes les 2 s : color = None → ils gardent leur couleur normale."""
    s = await A.get_state()
    cfg = await A.get_config()
    # color : choix d'un viewer (ou None) ; base : couleur normale unique réglée dans la page Aura
    return {"color": s["color"], "base": cfg["base_color"], "until": s["until"]}


@admin_router.get("/admin/api/aura")
async def admin_aura_get():
    return {"config": await A.get_config(), "state": await A.get_state()}


class ConfigPayload(BaseModel):
    config: dict


@admin_router.put("/admin/api/aura/config")
async def admin_aura_save(payload: ConfigPayload):
    current = await A.get_config()
    try:
        cfg = A.clean_config(payload.config, current)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await A.save_config(cfg)
    pushed = await A.push_config() if cfg["reward_id"] else None
    return {"status": "ok", "config": cfg, "twitch": pushed}


@admin_router.post("/admin/api/aura/create")
async def admin_aura_create():
    return await A.create_reward()


class EnablePayload(BaseModel):
    enabled: bool


@admin_router.post("/admin/api/aura/reward_enabled")
async def admin_aura_enable(payload: EnablePayload):
    return await A.set_reward_enabled(payload.enabled)


class ApplyPayload(BaseModel):
    text: str


@admin_router.post("/admin/api/aura/apply")
async def admin_aura_apply(payload: ApplyPayload):
    """Test depuis l'admin : même analyse que pour un viewer."""
    parsed = A.parse_color(payload.text)
    if not parsed:
        return {"ok": False, "message": "Couleur non comprise (nom en français / anglais, ou code #rrggbb)."}
    cfg = await A.get_config()
    await A.set_color(parsed[0], "admin", parsed[1], float(cfg["duration_min"]))
    return {"ok": True, "message": f"Aura en {parsed[1]} ({parsed[0]}).", "state": await A.get_state()}


@admin_router.post("/admin/api/aura/reset")
async def admin_aura_reset():
    await A.reset()
    return {"ok": True, "message": "Aura remise à sa couleur normale."}
