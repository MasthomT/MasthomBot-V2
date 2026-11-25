"""« La Bombe » : overlay /overlay/bombe et son état (voir app/services/bomb_service.py)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.security import require_admin
from app.services import bomb_service as B

NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}
templates = Jinja2Templates(directory="app/templates")

public = APIRouter(tags=["bomb"])
admin = APIRouter(tags=["bomb"], dependencies=[Depends(require_admin)])


@public.get("/overlay/bombe", response_class=HTMLResponse)
async def bomb_overlay(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/bomb_overlay.html", headers=NO_CACHE)


@public.get("/api/bomb/state")
async def bomb_state():
    return JSONResponse(B.state(), headers=NO_CACHE)


@admin.post("/admin/api/bomb/test")
async def bomb_test(payload: dict | None = None):
    """Pose une bombe de test (timeout simulé) ; avec {"cut": "rouge"} coupe un fil à la place de la cible."""
    payload = payload or {}
    if payload.get("cut"):
        s = B._state
        ok = s.get("active") and await B.on_chat(s["target_login"], s["target_name"], "!coupe " + payload["cut"])
        return {"ok": bool(ok), "state": B.state()}
    return {"ok": True, "message": await B.start(payload.get("sender") or "Test", test=True)}
