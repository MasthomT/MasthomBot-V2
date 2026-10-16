"""Page /admin/automatisations : déclencheurs → messages du bot dans le t'chat (voir app/services/automation_service.py)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.security import require_admin
from app.services import automation_service as A

router = APIRouter(tags=["automations"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")


@router.get("/admin/automatisations", response_class=HTMLResponse)
async def automations_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/automations.html")


@router.get("/admin/api/automations")
async def automations_get():
    return {"triggers": A.catalog(), "rules": await A.list_rules(), "log": await A.get_log()}


class CreatePayload(BaseModel):
    trigger: str
    name: str = ""


@router.post("/admin/api/automations")
async def automations_create(payload: CreatePayload):
    try:
        return {"rule": await A.create_rule(payload.trigger, payload.name)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class RulePayload(BaseModel):
    rule: dict


@router.post("/admin/api/automations/test")
async def automations_test(payload: RulePayload):
    """Envoie vraiment le message dans le t'chat avec des valeurs d'exemple."""
    try:
        return await A.test_rule(payload.rule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/admin/api/automations/{rule_id}")
async def automations_save(rule_id: int, payload: RulePayload):
    if not await A.get_rule(rule_id):
        raise HTTPException(status_code=404, detail="Automatisation introuvable.")
    try:
        return {"rule": await A.save_rule(rule_id, payload.rule)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/api/automations/{rule_id}/duplicate")
async def automations_duplicate(rule_id: int):
    rule = await A.duplicate_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Automatisation introuvable.")
    return {"rule": rule}


@router.delete("/admin/api/automations/{rule_id}")
async def automations_delete(rule_id: int):
    await A.delete_rule(rule_id)
    return {"ok": True}
