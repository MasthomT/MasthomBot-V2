"""Style commun des labels OBS (police, couleurs, icônes) : API publique lue par les pages + admin /admin/labels."""
import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.security import require_admin

logger = logging.getLogger("masthbot.label_style")
public_router = APIRouter(tags=["label_style"])
admin_router = APIRouter(tags=["label_style_admin"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")

# Champ vide = on garde le réglage d'origine de la page.
BLANK = {"preset": "classique", "font": "", "weight": "", "size": "", "spacing": "", "color": "", "glow": "",
         "icon_color": "", "icon_set": "default",
         # widgets de la scène (sondages, trophées, roues, lecteur, chrono, BRB…)
         "w_accent": "", "w_accent2": "", "w_font": "",
         # date (AAAA-MM-JJ, incluse) après laquelle le style revient tout seul au thème classique
         "until": ""}

PRESETS = {
    "classique": dict(BLANK),
    "halloween": {"preset": "halloween", "font": "Creepster", "weight": "400", "size": "", "spacing": "2",
                  "color": "#ffa24d", "glow": "#ff5a00", "icon_color": "#b266ff", "icon_set": "halloween",
                  "w_accent": "#ff7a18", "w_accent2": "#7b2cbf", "w_font": "Creepster",
                  "until": "2026-10-31"},
}

FONTS = ["", "Montserrat", "Creepster", "Nosifer", "Eater", "Butcherman", "Metal Mania", "Jolly Lodger",
         "Mystery Quest", "Special Elite", "Rubik Wet Paint", "Frijole", "Pirata One"]

_ready = False


async def _ensure():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS label_style (id INTEGER PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}')")
        await db.execute("INSERT INTO label_style (id, data) VALUES (1, $1) ON CONFLICT (id) DO NOTHING",
                         (json.dumps(BLANK),))
    _ready = True


async def get_style() -> dict:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT data FROM label_style WHERE id = 1")
        row = await c.fetchone()
    try:
        data = json.loads(row["data"]) if row else {}
    except Exception:
        data = {}
    style = {**BLANK, **{k: str(v) for k, v in data.items() if k in BLANK}}

    # Thème temporaire : passé la date limite, retour automatique au style classique (et on l'enregistre)
    if style["until"]:
        try:
            expired = date.today() > date.fromisoformat(style["until"])
        except ValueError:
            expired = False
        if expired:
            logger.info(f"🎃 [STYLE] Thème « {style['preset']} » expiré le {style['until']} : retour au style classique.")
            style = dict(BLANK)
            async with get_db_connection() as db:
                await db.execute("UPDATE label_style SET data = $1 WHERE id = 1", (json.dumps(style, ensure_ascii=False),))
    return style


class StylePayload(BaseModel):
    preset: str = "classique"
    font: str = ""
    weight: str = ""
    size: str = ""
    spacing: str = ""
    color: str = ""
    glow: str = ""
    icon_color: str = ""
    icon_set: str = "default"
    w_accent: str = ""
    w_accent2: str = ""
    w_font: str = ""
    until: str = ""


@public_router.get("/api/labels/style")
async def api_label_style():
    return await get_style()


@admin_router.get("/admin/labels", response_class=HTMLResponse)
async def admin_labels_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/labels_style.html")


@admin_router.get("/admin/api/labels/style")
async def admin_label_style_get():
    return {"style": await get_style(), "presets": PRESETS, "fonts": FONTS}


@admin_router.put("/admin/api/labels/style")
async def admin_label_style_save(payload: StylePayload):
    data = payload.model_dump()
    if data["font"] not in FONTS or data["w_font"] not in FONTS:
        raise HTTPException(status_code=400, detail="Police non proposée.")
    for key in ("size", "spacing"):
        v = data[key].strip()
        if v:
            try:
                float(v)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"« {key} » doit être un nombre.")
        data[key] = v
    for key in ("color", "glow", "icon_color", "w_accent", "w_accent2"):
        v = data[key].strip()
        if v and not (v.startswith("#") and len(v) in (4, 7)):
            raise HTTPException(status_code=400, detail=f"« {key} » doit être une couleur (#rrggbb).")
        data[key] = v
    if data["weight"] not in ("", "100", "200", "300", "400", "500", "600", "700", "800", "900"):
        raise HTTPException(status_code=400, detail="Graisse invalide.")
    data["until"] = data["until"].strip()
    if data["until"]:
        try:
            date.fromisoformat(data["until"])
        except ValueError:
            raise HTTPException(status_code=400, detail="La date de fin doit être au format AAAA-MM-JJ.")
    if data["icon_set"] not in ("default", "halloween"):
        raise HTTPException(status_code=400, detail="Jeu d'icônes inconnu.")
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("UPDATE label_style SET data = $1 WHERE id = 1", (json.dumps(data, ensure_ascii=False),))
    return {"status": "ok"}
