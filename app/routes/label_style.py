"""Style des labels OBS : thème global + réglages propres à chaque label (police, dégradés, icône, animation).
API publique lue par les pages + admin /admin/labels."""
import json
import logging
import re
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
    "halloween": {"preset": "halloween", "font": "Special Elite", "weight": "400", "size": "", "spacing": "1",
                  "color": "#ffa24d", "glow": "#ff5a00", "icon_color": "#b266ff", "icon_set": "halloween",
                  "w_accent": "#ff7a18", "w_accent2": "#7b2cbf", "w_font": "Special Elite",
                  "until": "2026-10-31"},
    # The Legend of Zelda : Ocarina of Time (or d'Hyrule, vert Kokiri, bleu de Navi) — thème permanent, sans date de fin
    "zelda": {"preset": "zelda", "font": "Charlemagne Std", "weight": "400", "size": "", "spacing": "1",
              "color": "#f7ecc4", "glow": "#d4a017", "icon_color": "#f2c94c", "icon_set": "zelda",
              "w_accent": "#f2c94c", "w_accent2": "#2f9e44", "w_font": "Cinzel", "until": ""},
}

# Suggestions (n'importe quelle police Google Fonts peut être saisie à la main)
FONTS = ["", "Montserrat", "Poppins", "Roboto", "Inter", "Oswald", "Bebas Neue", "Orbitron", "Audiowide",
         "Press Start 2P", "Righteous", "Bangers", "Fredoka", "Pacifico", "Lobster", "Permanent Marker", "Caveat",
         "Special Elite", "Creepster", "Nosifer", "Eater", "Butcherman", "Metal Mania", "Jolly Lodger",
         "Mystery Quest", "Rubik Wet Paint", "Frijole", "Pirata One", "Cinzel", "Cinzel Decorative", "MedievalSharp",
         "Uncial Antiqua", "Almendra", "Charlemagne Std"]

LABEL_KEYS = ["followers", "viewers", "subs", "heure", "follow", "sub", "subgift", "bits", "raid"]

# Réglages propres à un label (vide = on reprend le thème global, puis le réglage d'origine de la page).
LABEL_FIELDS = {
    "font": "font", "weight": "weight", "size": "number", "spacing": "number", "uppercase": "flag",
    "text_mode": ("", "solid", "gradient"), "color": "color",
    "grad1": "color", "grad2": "color", "grad3": "color", "grad_angle": "angle",
    "glow": "color",
    "icon": "icon", "icon_text": "emoji", "icon_hidden": "flag",
    "icon_mode": ("", "solid", "gradient"), "icon_color": "color",
    "icon_grad1": "color", "icon_grad2": "color", "icon_grad_angle": "angle",
    "icon_anim": ("", "none", "pulse", "spin", "bounce", "shake"),
}
_FONT_RE = re.compile(r"^[A-Za-z0-9 ]{0,40}$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$")
_ICON_RE = re.compile(r"^fa-(solid|regular|brands) fa-[a-z0-9-]{1,40}$")


def _clean_value(kind, value) -> str:
    """Valeur nettoyée ou ValueError. Une chaîne vide est toujours acceptée (= pas de réglage)."""
    v = "" if value is None else str(value).strip()
    if v == "":
        return ""
    if isinstance(kind, tuple):
        if v not in kind:
            raise ValueError("valeur inconnue")
    elif kind == "font":
        if not _FONT_RE.match(v):
            raise ValueError("nom de police invalide")
    elif kind == "weight":
        if v not in ("100", "200", "300", "400", "500", "600", "700", "800", "900"):
            raise ValueError("graisse invalide")
    elif kind == "number":
        float(v)
    elif kind == "angle":
        if not 0 <= int(float(v)) <= 360:
            raise ValueError("angle invalide")
        v = str(int(float(v)))
    elif kind == "color":
        if not _COLOR_RE.match(v):
            raise ValueError("couleur invalide (#rrggbb)")
    elif kind == "icon":
        if not _ICON_RE.match(v):
            raise ValueError("icône invalide")
    elif kind == "emoji":
        if len(v) > 8:
            raise ValueError("8 caractères maximum")
    elif kind == "flag":
        v = "1" if v in ("1", "true", "True") else ""
    return v


def clean_labels(raw) -> dict:
    """Réglages par label : on ne garde que les clés et champs connus, avec leurs valeurs validées."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for key in LABEL_KEYS:
        src = raw.get(key)
        if not isinstance(src, dict):
            continue
        item = {}
        for field, kind in LABEL_FIELDS.items():
            try:
                v = _clean_value(kind, src.get(field))
            except (ValueError, TypeError):
                raise ValueError(f"{key} › {field} : valeur invalide")
            if v != "":
                item[field] = v
        if item:
            out[key] = item
    return out

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
    try:
        style["labels"] = clean_labels(data.get("labels"))
    except ValueError:
        style["labels"] = {}

    # Thème temporaire : passé la date limite, retour automatique au style classique (et on l'enregistre)
    if style["until"]:
        try:
            expired = date.today() > date.fromisoformat(style["until"])
        except ValueError:
            expired = False
        if expired:
            logger.info(f"🎃 [STYLE] Thème « {style['preset']} » expiré le {style['until']} : retour au style classique.")
            # Seul le thème global expire : les réglages propres à chaque label sont conservés.
            style = {**BLANK, "labels": style["labels"]}
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
    labels: dict = {}


@public_router.get("/api/labels/style")
async def api_label_style():
    return await get_style()


@admin_router.get("/admin/labels", response_class=HTMLResponse)
async def admin_labels_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/labels_style.html",
                                      context={"embed": request.query_params.get("embed") == "1"})


@admin_router.get("/admin/api/labels/style")
async def admin_label_style_get():
    return {"style": await get_style(), "presets": PRESETS, "fonts": FONTS, "label_keys": LABEL_KEYS}


@admin_router.put("/admin/api/labels/style")
async def admin_label_style_save(payload: StylePayload):
    data = payload.model_dump()
    for key in ("font", "w_font"):
        if not _FONT_RE.match(data[key].strip()):
            raise HTTPException(status_code=400, detail="Nom de police invalide (lettres, chiffres, espaces).")
        data[key] = data[key].strip()
    try:
        data["labels"] = clean_labels(data.get("labels"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    if data["icon_set"] not in ("default", "halloween", "zelda"):
        raise HTTPException(status_code=400, detail="Jeu d'icônes inconnu.")
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("UPDATE label_style SET data = $1 WHERE id = 1", (json.dumps(data, ensure_ascii=False),))
    return {"status": "ok"}
