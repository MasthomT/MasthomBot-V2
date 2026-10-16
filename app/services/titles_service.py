"""
Écrans de titre (début de live, pause, fin) avec décompte optionnel, gérés depuis /admin/titres.

Remplace les pages locales « overlay_scenes.html?scene=start|brk|end » : un écran = un titre, un sous-titre,
une image facultative, un fond, un effet d'ambiance et un décompte. Affichés par /overlay/titre/<écran>
(et disponibles comme widgets dans la Scène OBS).
"""
import json
import logging
import re
import time
from datetime import datetime, timedelta

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.titles")

SCREENS = {"start": "Début de live", "brk": "Pause", "end": "Fin de live"}
EFFECTS = {"none": "Aucun", "bats": "Chauves-souris", "confetti": "Confettis / bonbons", "snow": "Neige",
           "hearts": "Cœurs", "ghost": "Fantôme qui passe"}
ANIMS = {"perspective": "Apparition en profondeur (comme avant)", "zoom": "Zoom", "fade": "Fondu", "bounce": "Rebond",
         "slide-up": "Glisse du bas", "none": "Aucune"}
LINE_ANIMS = {"": "Comme le reste", **ANIMS}
BACKDROPS = {"none": "Transparent", "dim": "Voile sombre", "color": "Couleur unie"}
LOOKS = {"original": "Original (bleu acier, police Kanit)", "theme": "Thème du bot (couleurs et police des widgets)"}
FORMATS = {"main": "Grand titre (rempli, animé)", "sub": "Sous-titre (contour)", "message": "Message (petit, espacé)", "plain": "Texte simple"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
IMAGES_DIR = "static/commands/images"
MAX_LINES = 12

_FONT_RE = re.compile(r"^[A-Za-z0-9 ]{0,40}$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

# Reprend la décoration de l'ancienne page overlay_scenes.html (sous-titre contour + grand titre + message + décompte)
DEFAULT_LINES = {
    "start": [("LE LIVE VA", "sub"), ("COMMENCER", "main"), ("Installez-vous confortablement", "message")],
    "brk":   [("JE SUIS", "sub"), ("EN PAUSE", "main"), ("Je reviens très vite", "message")],
    "end":   [("LE STREAM EST", "sub"), ("TERMINÉ", "main"), ("Merci et à la prochaine !", "message")],
}
DEFAULT_COUNTDOWN = {
    "start": {"enabled": True, "label": "", "end_text": "ON COMMENCE !"},
    "brk": {"enabled": False, "label": "Retour dans", "end_text": "On revient !"},
    "end": {"enabled": False, "label": "", "end_text": ""},
}


def default_config(slug: str) -> dict:
    cd = DEFAULT_COUNTDOWN[slug]
    return {
        "look": "original",
        "lines": [{"text": t, "format": f, "size": 0, "color": "", "x": None, "y": None, "anim": "", "delay": 0}
                  for t, f in DEFAULT_LINES[slug]],
        "uppercase": True, "gap": 14, "glow": True, "ridge": True, "stagger": 0,
        "base_color": "#4682b4", "outline": "#f0f8ff", "hue_rotate": True, "hue_speed": 40,
        "font": "", "accent": "", "halloween_decor": False, "halloween_look": True, "hw_font": "Kanit", "hw_font_text": "Kanit",
        "frame": True, "frame_color": "#ff7a18",
        "zoom": 1.4,
        "x": 50, "y": 50, "w": 90,
        "image": "", "image_w": 18, "image_x": 50, "image_y": 14,
        "backdrop": "none", "backdrop_color": "#000000", "backdrop_opacity": 0.55,
        "effect": "none", "anim_in": "perspective", "anim_dur": 1.5,
        # x / y = None : le décompte suit les lignes ; sinon position libre (en % de l'écran, centre)
        "countdown": {"enabled": cd["enabled"], "mode": "minutes", "minutes": 5, "time": "20:00", "auto": True,
                      "label": cd["label"], "end_text": cd["end_text"], "size": 72, "x": None, "y": None, "delay": 0},
    }


def _num(v, lo, hi, name, cast=float):
    try:
        x = cast(v)
    except (TypeError, ValueError):
        raise ValueError(f"« {name} » doit être un nombre")
    if not lo <= x <= hi:
        raise ValueError(f"« {name} » doit être entre {lo} et {hi}")
    return x


def _line_anim(v):
    v = v or ""
    if v not in LINE_ANIMS:
        raise ValueError("animation de ligne inconnue")
    return v


def _opt_pos(v, name):
    """Position libre facultative : None (placement automatique) ou un pourcentage de l'écran."""
    if v is None or v == "":
        return None
    return _num(v, -30, 130, name)


def _lines_from(raw: dict, base: dict) -> list:
    lines = raw.get("lines")
    if lines is None:
        # ancien format (titre + sous-titre) : converti en lignes
        old = []
        if raw.get("title"):
            old.append({"text": raw["title"], "format": "main"})
        if raw.get("subtitle"):
            old.append({"text": raw["subtitle"], "format": "message"})
        lines = old or base["lines"]
    if not isinstance(lines, list):
        raise ValueError("lignes invalides")
    if len(lines) > MAX_LINES:
        raise ValueError(f"{MAX_LINES} lignes maximum")
    out = []
    for ln in lines:
        if not isinstance(ln, dict):
            raise ValueError("ligne invalide")
        fmt = ln.get("format", "plain")
        if fmt not in FORMATS:
            raise ValueError("format de ligne inconnu")
        col = str(ln.get("color") or "").strip()
        if col and not _COLOR_RE.match(col):
            raise ValueError("couleur de ligne invalide (#rrggbb)")
        out.append({"text": str(ln.get("text", ""))[:200], "format": fmt,
                    "size": int(_num(ln.get("size", 0) or 0, 0, 400, "taille de ligne", int)), "color": col,
                    "x": _opt_pos(ln.get("x"), "position X de la ligne"), "y": _opt_pos(ln.get("y"), "position Y de la ligne"),
                    "anim": _line_anim(ln.get("anim", "")),
                    "delay": _num(ln.get("delay", 0) or 0, 0, 60, "délai de la ligne")})
    return out


def clean_config(slug: str, raw: dict, images: set) -> dict:
    base = default_config(slug)
    if not isinstance(raw, dict):
        raise ValueError("configuration invalide")
    cd_raw = raw.get("countdown") or {}
    cdb = base["countdown"]

    def color(v, name, allow_empty=False):
        s = str(v or "").strip()
        if not s and allow_empty:
            return ""
        if not _COLOR_RE.match(s):
            raise ValueError(f"« {name} » doit être une couleur #rrggbb")
        return s

    font = str(raw.get("font", "")).strip()
    if not _FONT_RE.match(font):
        raise ValueError("nom de police invalide")
    hw_font = str(raw.get("hw_font", "Kanit")).strip()
    hw_font_text = str(raw.get("hw_font_text", "Kanit")).strip()
    if not _FONT_RE.match(hw_font) or not _FONT_RE.match(hw_font_text):
        raise ValueError("nom de police Halloween invalide")
    image = raw.get("image") or ""
    if image and image not in images:
        raise ValueError("image introuvable")
    for key, allowed, label in (("effect", EFFECTS, "effet"), ("anim_in", ANIMS, "animation"),
                                ("backdrop", BACKDROPS, "fond"), ("look", LOOKS, "style")):
        if raw.get(key, base[key]) not in allowed:
            raise ValueError(f"{label} inconnu")
    mode = cd_raw.get("mode", cdb["mode"])
    if mode not in ("minutes", "time"):
        raise ValueError("mode de décompte inconnu")
    t = str(cd_raw.get("time", cdb["time"]))
    if not _TIME_RE.match(t):
        raise ValueError("l'heure du décompte doit être au format HH:MM")

    return {
        "look": raw.get("look", "original"),
        "lines": _lines_from(raw, base),
        "uppercase": bool(raw.get("uppercase", True)),
        "gap": _num(raw.get("gap", 14), 0, 200, "espacement des lignes", int),
        "glow": bool(raw.get("glow", True)),
        "ridge": bool(raw.get("ridge", True)),
        "stagger": _num(raw.get("stagger", 0), 0, 5, "décalage entre les lignes"),
        "base_color": color(raw.get("base_color", "#4682b4"), "couleur de base"),
        "outline": color(raw.get("outline", "#f0f8ff"), "couleur du contour"),
        "hue_rotate": bool(raw.get("hue_rotate", True)),
        "hue_speed": _num(raw.get("hue_speed", 40), 5, 300, "vitesse du changement de couleur"),
        "font": font,
        "accent": color(raw.get("accent", ""), "couleur d'accent", allow_empty=True),
        "halloween_decor": bool(raw.get("halloween_decor", raw.get("decor", False))),
        "halloween_look": bool(raw.get("halloween_look", True)),
        "hw_font": hw_font,
        "hw_font_text": hw_font_text,
        "frame": bool(raw.get("frame", True)),
        "frame_color": color(raw.get("frame_color", "#ff7a18"), "couleur du cadre"),
        "x": _num(raw.get("x", 50), 0, 100, "position X"),
        "y": _num(raw.get("y", 50), 0, 100, "position Y"),
        "zoom": _num(raw.get("zoom", 1.4), 0.5, 3, "zoom du titre"),
        "w": _num(raw.get("w", 90), 20, 100, "largeur"),
        "image": image,
        "image_w": _num(raw.get("image_w", 18), 3, 80, "largeur de l'image"),
        "image_x": _num(raw.get("image_x", raw.get("x", 50)), -30, 130, "position X de l'image"),
        "image_y": _num(raw.get("image_y", 14), -30, 130, "position Y de l'image"),
        "backdrop": raw.get("backdrop", "none"),
        "backdrop_color": color(raw.get("backdrop_color", "#000000"), "couleur du fond"),
        "backdrop_opacity": _num(raw.get("backdrop_opacity", 0.55), 0, 1, "opacité du fond"),
        "effect": raw.get("effect", "none"),
        "anim_in": raw.get("anim_in", "perspective"),
        "anim_dur": _num(raw.get("anim_dur", 1.5), 0.1, 4, "durée de l'animation"),
        "countdown": {
            "enabled": bool(cd_raw.get("enabled", cdb["enabled"])),
            "mode": mode,
            "minutes": _num(cd_raw.get("minutes", cdb["minutes"]), 0.1, 600, "durée du décompte"),
            "time": t,
            "auto": bool(cd_raw.get("auto", True)),
            "label": str(cd_raw.get("label", cdb["label"]))[:100],
            "end_text": str(cd_raw.get("end_text", cdb["end_text"]))[:100],
            "size": _num(cd_raw.get("size", cdb["size"]), 20, 500, "taille du décompte", int),
            "x": _opt_pos(cd_raw.get("x"), "position X du décompte"),
            "y": _opt_pos(cd_raw.get("y"), "position Y du décompte"),
            "delay": _num(cd_raw.get("delay", 0) or 0, 0, 60, "délai du décompte"),
        },
    }


# ── Stockage ─────────────────────────────────────────────────────────────────

_ready = False


async def _ensure():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS title_screens (slug TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}', "
                         "target_ts DOUBLE PRECISION)")
    _ready = True


def image_files() -> list[str]:
    import os
    if not os.path.isdir(IMAGES_DIR):
        return []
    return sorted(f for f in os.listdir(IMAGES_DIR) if os.path.splitext(f)[1].lower() in IMAGE_EXTS)


async def get_config(slug: str) -> dict:
    if slug not in SCREENS:
        raise KeyError(slug)
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT data FROM title_screens WHERE slug = $1", (slug,))
        row = await c.fetchone()
    try:
        saved = json.loads(row["data"]) if row else {}
    except Exception:
        saved = {}
    try:
        # on tolère un fichier image supprimé depuis (l'image sera juste absente)
        return clean_config(slug, saved, set(image_files()) | {saved.get("image", "")})
    except ValueError:
        return default_config(slug)


# ── Écran automatique : un seul widget qui affiche start / brk / end selon la scène OBS en cours ──
AUTO_DEFAULT_RULES = [
    {"match": "beg", "screen": "start"}, {"match": "start", "screen": "start"}, {"match": "demarr", "screen": "start"},
    {"match": "break", "screen": "brk"}, {"match": "brb", "screen": "brk"}, {"match": "pause", "screen": "brk"},
    {"match": "end", "screen": "end"}, {"match": "fin", "screen": "end"},
]


def clean_rules(raw) -> list[dict]:
    if not isinstance(raw, list):
        raise ValueError("règles invalides")
    out = []
    for r in raw[:30]:
        if not isinstance(r, dict):
            continue
        match = str(r.get("match", "")).strip()[:60]
        screen = r.get("screen")
        if not match:
            continue
        if screen not in SCREENS:
            raise ValueError("écran inconnu dans une règle")
        out.append({"match": match, "screen": screen})
    return out


async def get_rules() -> list[dict]:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT data FROM title_screens WHERE slug = '_auto'")
        row = await c.fetchone()
    if not row:
        return [dict(r) for r in AUTO_DEFAULT_RULES]
    try:
        return clean_rules(json.loads(row["data"]).get("rules", []))
    except Exception:
        return [dict(r) for r in AUTO_DEFAULT_RULES]


async def save_rules(rules: list[dict]):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO title_screens (slug, data) VALUES ('_auto', $1) "
            "ON CONFLICT (slug) DO UPDATE SET data = EXCLUDED.data", (json.dumps({"rules": rules}, ensure_ascii=False),))


async def save_config(slug: str, cfg: dict):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO title_screens (slug, data) VALUES ($1, $2) "
            "ON CONFLICT (slug) DO UPDATE SET data = EXCLUDED.data", (slug, json.dumps(cfg, ensure_ascii=False)))


async def set_target(slug: str, ts: float | None):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO title_screens (slug, target_ts) VALUES ($1, $2) "
            "ON CONFLICT (slug) DO UPDATE SET target_ts = EXCLUDED.target_ts", (slug, ts))


async def get_target(slug: str) -> float | None:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT target_ts FROM title_screens WHERE slug = $1", (slug,))
        row = await c.fetchone()
    return float(row["target_ts"]) if row and row["target_ts"] is not None else None


async def countdown_state(slug: str, cfg: dict) -> dict:
    """{'target': epoch|None, 'now': epoch}. 'time' : prochaine occurrence de HH:MM ; 'minutes' : cible lancée depuis l'admin."""
    now = time.time()
    cd = cfg["countdown"]
    target = None
    if cd["enabled"]:
        if cd["mode"] == "time":
            h, m = map(int, cd["time"].split(":"))
            today = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
            # l'heure du jour reste « la cible » une heure après son passage (le temps d'afficher le message de fin)
            if datetime.now() > today + timedelta(hours=1):
                today += timedelta(days=1)
            target = today.timestamp()
        else:
            t = await get_target(slug)
            if t is not None and now < t + 3600:
                target = t
    return {"target": target, "now": now}
