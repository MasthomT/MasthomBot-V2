"""API d'administration de la protection des modérateurs (voir app/services/mod_guard_service.py)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_admin
from app.services import mod_guard_service as G

router = APIRouter(tags=["mod_guard"], dependencies=[Depends(require_admin)])


@router.get("/admin/api/modguard")
async def modguard_get():
    return {"config": await G.get_config(), "roster": await G.get_roster(), "log": await G.get_log()}


class ConfigPayload(BaseModel):
    config: dict


@router.put("/admin/api/modguard/config")
async def modguard_save(payload: ConfigPayload):
    return {"config": await G.save_config(payload.config)}


@router.post("/admin/api/modguard/check")
async def modguard_check():
    return await G.reconcile("vérification manuelle")


class ProtectPayload(BaseModel):
    protected: bool


@router.post("/admin/api/modguard/{twitch_id}/protect")
async def modguard_protect(twitch_id: str, payload: ProtectPayload):
    await G.set_protected(twitch_id, payload.protected)
    return {"ok": True}


@router.post("/admin/api/modguard/{twitch_id}/demote")
async def modguard_demote(twitch_id: str):
    return await G.demote(twitch_id)


@router.delete("/admin/api/modguard/{twitch_id}")
async def modguard_forget(twitch_id: str):
    await G.forget(twitch_id)
    return {"ok": True}
