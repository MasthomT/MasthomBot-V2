"""Écrans de titre : overlay /overlay/titre/<écran> + admin /admin/titres (voir app/services/titles_service.py)."""
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.security import require_admin
from app.services import titles_service as T

public_router = APIRouter(tags=["titles_overlay"])
admin_router = APIRouter(tags=["titles_admin"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")
NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


def _screen(slug: str) -> str:
    if slug not in T.SCREENS:
        raise HTTPException(status_code=404, detail="Écran de titre inconnu (start, brk ou end).")
    return slug


@public_router.get("/overlay/titre/{slug}", response_class=HTMLResponse)
async def overlay_title(request: Request, slug: str):
    if slug != "auto":                       # « auto » = choisit l'écran selon la scène OBS en cours
        _screen(slug)
    return templates.TemplateResponse(request=request, name="overlays/title_overlay.html", headers=NO_CACHE)


@public_router.get("/api/titres/auto/scene")
async def api_title_scene():
    """Scène OBS en cours, lue par le serveur Node (obs-websocket) : fonctionne même après un F9 / rechargement des sources."""
    import aiohttp
    from app.core.config import settings
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
            async with session.get(f"{settings.OVERLAY_NODE_URL}/api/obs-scene") as resp:
                j = await resp.json()
        return {"scene": str(j.get("scene") or ""), "connected": bool(j.get("connected"))}
    except Exception:
        return {"scene": "", "connected": False}


@public_router.get("/api/titres/auto/rules")
async def api_title_rules():
    return {"rules": await T.get_rules()}


@public_router.get("/api/titres/{slug}")
async def api_title(slug: str):
    _screen(slug)
    cfg = await T.get_config(slug)
    return {"config": cfg, "countdown": await T.countdown_state(slug, cfg)}


# ── Admin ────────────────────────────────────────────────────────────────────

class ScreenPayload(BaseModel):
    config: dict


@admin_router.get("/admin/titres", response_class=HTMLResponse)
async def admin_titles_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/titles_manager.html",
                                      context={"embed": request.query_params.get("embed") == "1"})


@admin_router.get("/admin/api/titres")
async def admin_titles_get():
    screens = {}
    for slug, label in T.SCREENS.items():
        cfg = await T.get_config(slug)
        screens[slug] = {"label": label, "config": cfg, "countdown": await T.countdown_state(slug, cfg)}
    return {"screens": screens, "effects": T.EFFECTS, "anims": T.ANIMS, "backdrops": T.BACKDROPS,
            "looks": T.LOOKS, "formats": T.FORMATS, "line_anims": T.LINE_ANIMS, "auto_rules": await T.get_rules(), "scene_offsets": await _scene_offsets(),
            "images": T.image_files(), "defaults": {s: T.default_config(s) for s in T.SCREENS}}


class RulesPayload(BaseModel):
    rules: list[dict]


@admin_router.put("/admin/api/titres-auto/rules")
async def admin_titles_rules(payload: RulesPayload):
    try:
        rules = T.clean_rules(payload.rules)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await T.save_rules(rules)
    return {"status": "ok", "rules": rules}


@admin_router.put("/admin/api/titres/{slug}")
async def admin_titles_save(slug: str, payload: ScreenPayload):
    _screen(slug)
    try:
        cfg = T.clean_config(slug, payload.config, set(T.image_files()))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await T.save_config(slug, cfg)
    return {"status": "ok", "config": cfg}


async def _scene_offsets() -> list[dict]:
    """Widgets Titre activés dans une scène avec un décalage / zoom : l'aperçu de la page Titres n'en tient pas compte."""
    from app.core.database import get_db_connection
    async with get_db_connection() as db:
        c = await db.execute("SELECT scene_slug, widget_key, x, y, scale FROM scene_widgets "
                             "WHERE widget_key LIKE 'titre\\_%' AND enabled AND (x <> 0 OR y <> 0 OR scale <> 1) ORDER BY 1, 2")
        return [dict(r) for r in await c.fetchall()]


@admin_router.post("/admin/api/titres-auto/reset-scene-offsets")
async def admin_titles_reset_offsets():
    from app.core.database import get_db_connection
    async with get_db_connection() as db:
        await db.execute("UPDATE scene_widgets SET x = 0, y = 0, scale = 1 WHERE widget_key LIKE 'titre\\_%'")
    return {"status": "ok", "offsets": await _scene_offsets()}


@admin_router.post("/admin/api/titres/{slug}/start")
async def admin_titles_start(slug: str):
    """Lance le décompte (mode « durée ») maintenant, pour toutes les pages qui affichent cet écran."""
    _screen(slug)
    cfg = await T.get_config(slug)
    await T.set_target(slug, time.time() + float(cfg["countdown"]["minutes"]) * 60)
    return {"status": "ok", "countdown": await T.countdown_state(slug, cfg)}


@admin_router.post("/admin/api/titres/{slug}/stop")
async def admin_titles_stop(slug: str):
    _screen(slug)
    await T.set_target(slug, None)
    return {"status": "ok"}
