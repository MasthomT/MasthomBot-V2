"""Boîte d'alertes (follow, sub, subgift, bits, raid) et screamer : overlay /overlay/events + admin /admin/alerts."""
import logging
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.security import require_admin
from app.services import alerts_service as A

logger = logging.getLogger("masthbot.alerts_admin")
public_router = APIRouter(tags=["alerts_overlay"])
admin_router = APIRouter(tags=["alerts_admin"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")

MAX_UPLOAD = 25 * 1024 * 1024
NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}

SAMPLES = {
    "follow": dict(user="PseudoTest"),
    "sub": dict(user="PseudoTest", months=3),
    "subgift": dict(user="PseudoTest", count=5),
    "bits": dict(user="PseudoTest", bits=500),
    "raid": dict(user="PseudoTest", viewers=42),
    "hype_start": dict(user="PseudoTest", level=1, total=500, goal=1800),
    "hype_end": dict(user="PseudoTest", level=4, total=15800),
    "hype_record": dict(user="PseudoTest", level=6, total=24500),
    "goal_start": dict(user="", description="Objectif de followers", type="followers", current=0, target=100),
    "goal_end": dict(user="", description="Objectif de followers", type="followers", current=100, target=100),
}


@public_router.get("/overlay/events", response_class=HTMLResponse)
async def overlay_events(request: Request):
    return templates.TemplateResponse(request=request, name="overlays/events_overlay.html", headers=NO_CACHE)


class AlertsPayload(BaseModel):
    variants: list
    screamer: dict


class TestPayload(BaseModel):
    variant: dict
    user: str | None = None          # pseudo de test (pour essayer un pseudo très long)


def _libs():
    return set(A.media_files(A.IMAGES_DIR, A.IMAGE_EXTS)), set(A.media_files(A.SOUNDS_DIR, A.SOUND_EXTS))


async def _widget_status() -> list[dict]:
    """Pour chaque scène : le widget « Animations d'alertes » y est-il affiché ?"""
    from app.routes import scene as scene_routes
    out = []
    for s in (await scene_routes.admin_scenes_list())["scenes"]:
        ws = {w["key"]: w for w in await scene_routes._all_widgets(s["slug"])}
        out.append({"slug": s["slug"], "name": s["name"], "enabled": bool(ws["events"]["enabled"])})
    return out


class EnablePayload(BaseModel):
    scenes: list[str]


@admin_router.post("/admin/api/alerts/enable-widget")
async def admin_alerts_enable_widget(payload: EnablePayload):
    """Coche le widget « Animations d'alertes » (plein écran, par-dessus tout) dans les scènes demandées."""
    from app.routes import scene as scene_routes
    known = {s["slug"] for s in (await scene_routes.admin_scenes_list())["scenes"]}
    done = []
    for slug in payload.scenes:
        if slug not in known:
            continue
        await scene_routes.admin_scene_save(
            scene_routes.ScenePayload(widgets=[scene_routes.WidgetState(key="events", enabled=True, x=0, y=0, scale=1.0, z=45)]),
            scene=slug)
        done.append(slug)
    return {"status": "ok", "scenes": done}


@admin_router.get("/admin/alerts", response_class=HTMLResponse)
async def admin_alerts_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/alerts_manager.html",
                                      context={"embed": request.query_params.get("embed") == "1"})


@admin_router.get("/admin/api/alerts")
async def admin_alerts_get():
    cfg = await A.get_config()
    images, sounds = _libs()
    return {
        "variants": cfg["variants"],
        "screamer": cfg["screamer"],
        "kinds": [{"key": k, "label": A.KIND_LABELS[k], "vars": A.KIND_VARS[k],
                   "amount": A.AMOUNT_LABEL.get(k), "group": A.KIND_GROUPS[k]} for k in A.KINDS],
        "effects": A.EFFECTS, "anim_in": A.ANIM_IN, "anim_out": A.ANIM_OUT,
        "images": sorted(images), "sounds": sorted(sounds),
        "media_info": {f: A.inspect_media(f) for f in sorted(images)},
        "widget": await _widget_status(),
        "samples": SAMPLES,
        "template_variant": {k: A.new_variant(k) for k in A.KINDS},
    }


@admin_router.put("/admin/api/alerts")
async def admin_alerts_save(payload: AlertsPayload):
    images, sounds = _libs()
    try:
        variants = A.clean_variants(payload.variants, images, sounds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    s, d = payload.screamer or {}, A.DEFAULT_SCREAMER
    image, sound = (s.get("image") or ""), (s.get("sound") or "")
    if image and image not in images or sound and sound not in sounds:
        raise HTTPException(status_code=400, detail="Fichier introuvable pour le screamer.")
    try:
        screamer = {
            "enabled": bool(s.get("enabled", d["enabled"])), "image": image, "sound": sound,
            "volume": A._num(s.get("volume", d["volume"]), 0, 1, "screamer › volume"),
            "duration": A._num(s.get("duration", d["duration"]), 0.5, 6, "screamer › durée"),
            "flash": bool(s.get("flash", d["flash"])), "shake": bool(s.get("shake", d["shake"])),
            "chance": A._num(s.get("chance", d["chance"]), 0, 100, "screamer › hasard"),
            "reward_title": str(s.get("reward_title", d["reward_title"])).strip()[:45],
            "cooldown": A._num(s.get("cooldown", d["cooldown"]), 0, 3600, "screamer › délai"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await A.save_config(variants, screamer)
    return {"status": "ok", "variants": variants}


@admin_router.post("/admin/api/alerts/test")
async def admin_alerts_test(payload: TestPayload):
    """Joue à l'écran la variante en cours d'édition (même non enregistrée)."""
    images, sounds = _libs()
    try:
        v = A.clean_variant(payload.variant, images, sounds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sample = dict(SAMPLES[v["kind"]])
    user = (payload.user or "").strip()[:40]
    if user:
        sample["user"] = user
    await A.fire_alert(v["kind"], force=True, variant=v, **sample)

    warnings = []
    if v["media"]["file"]:
        info = A.inspect_media(v["media"]["file"])
        if info.get("message"):
            warnings.append(info["message"])
    widget = await _widget_status()
    if not any(w["enabled"] for w in widget):
        warnings.append("Le widget « Animations d'alertes » n'est affiché dans aucune scène : rien n'apparaîtra dans OBS tant que tu ne l'actives pas.")
    return {"status": "ok", "message": "Alerte de test envoyée à l'écran.", "warnings": warnings}


@admin_router.post("/admin/api/alerts/test_chat")
async def admin_alerts_test_chat(payload: TestPayload):
    """Envoie le message du t'chat de la variante (préfixé [TEST]) avec les valeurs d'exemple."""
    images, sounds = _libs()
    try:
        v = A.clean_variant(payload.variant, images, sounds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sample = dict(SAMPLES[v["kind"]])
    vars_ = {k: sample.get(k, "") for k in A.ALL_VARS}
    text = A.render_chat(v, vars_, prefix="[TEST] ")
    if not text:
        raise HTTPException(status_code=400, detail="Le message du t'chat est vide.")
    if not await A.send_chat(text):
        raise HTTPException(status_code=503, detail="Le bot n'est pas connecté au t'chat pour l'instant.")
    return {"status": "ok", "message": "Message envoyé dans le t'chat : " + text}


@admin_router.post("/admin/api/alerts/test_screamer")
async def admin_screamer_test():
    await A.fire_screamer(source="test admin", force=True)
    return {"status": "ok", "message": "Screamer envoyé à l'écran !"}


@admin_router.post("/admin/api/alerts/upload")
async def admin_alerts_upload(type: str, file: UploadFile = File(...)):
    if type not in ("media", "sound"):
        raise HTTPException(status_code=400, detail="Type de fichier inconnu.")
    folder, exts = (A.IMAGES_DIR, A.IMAGE_EXTS) if type == "media" else (A.SOUNDS_DIR, A.SOUND_EXTS)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in exts:
        raise HTTPException(status_code=400, detail="Format non supporté : " + ", ".join(sorted(exts)))
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="Fichier trop lourd (25 Mo max).")
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", os.path.splitext(file.filename or "fichier")[0]).strip("_")[:40] or "fichier"
    name = f"{base}{ext}"
    os.makedirs(folder, exist_ok=True)
    if os.path.exists(os.path.join(folder, name)):
        name = f"{base}_{uuid.uuid4().hex[:6]}{ext}"
    with open(os.path.join(folder, name), "wb") as f:
        f.write(data)
    result = {"status": "ok", "name": name}
    if type == "media":
        result["info"] = A.inspect_media(name)
    return result
