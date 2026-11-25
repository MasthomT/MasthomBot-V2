"""Overlay « Récompenses de points de chaîne » (/overlay/recompenses) et ses réglages (page Récompenses › Actions).
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
    from app.services.automation_service import media_files, STEP_TYPES
    return {"visuals": await R.list_visuals(), "media": media_files(), "step_types": STEP_TYPES, "log": R.recent()}


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
    """Fait le réglage EN COURS (pas forcément enregistré) comme si « Test » avait pris la récompense (timeout simulé)."""
    try:
        v = R.clean(dict(payload or {}, enabled=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    R.fire(v, {"user": "Test", "reward": v["title"], "input": "Test", "cost": 0}, test=True)
    if v["chat_mode"] == "random" and len(v["messages"]) > 1:
        v = dict(v, messages=v["messages"][:1])          # pour le compte rendu : un seul message part
    done = [x for x, on in (("image / vidéo", v["media"]), ("son", v["sound"]), (f"{len(v['messages'])} message(s)", v["messages"]),
                            (f"{len(v['steps'])} étape(s) OBS / Twitch", v["steps"])) if on]
    note = " L'image / vidéo n'apparaît que si le widget est dans la scène OBS affichée." if v["media"] else ""
    return {"ok": True, "message": "Test lancé : " + ", ".join(done) + "." + note}


@admin.get("/admin/api/reward-overlay/screenshot")
async def reward_overlay_screenshot():
    """Capture de la scène OBS en cours, en fond de la zone de placement."""
    from app.services.obs_service import obs_service
    img = await asyncio.to_thread(obs_service.take_screenshot)
    return {"image": img}
