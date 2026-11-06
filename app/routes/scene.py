"""
Scènes OBS : chaque scène est une source navigateur (/overlay/<nom>, 1920x1080 transparent)
qui regroupe des widgets (overlays + labels) placés depuis /admin/scene. On peut en créer plusieurs
(ex. /overlay/brb, /overlay/justchatting) ; /overlay/scene est la scène d'origine.

Chaque widget est une page d'overlay existante affichée dans un cadre transparent de 1920x1080,
décalé et mis à l'échelle pour que sa « zone native » (là où elle s'affiche seule dans OBS)
tombe à l'endroit choisi. Les overlays individuels (/overlay/...) continuent de fonctionner tels quels.
"""
import asyncio
import glob
import ipaddress
import json
import logging
import os
import random
import re
import shutil
import socket
import unicodedata
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

import aiohttp

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.config import settings
from app.core.security import require_admin
from app.routes.overlays import trigger_overlay_event
from app.services import wheel_service

logger = logging.getLogger("masthbot.scene")
router = APIRouter(tags=["scene"])
templates = Jinja2Templates(directory="app/templates")

NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}

# {NODE} est remplacé côté navigateur par http://<hôte de la page>:3005 (serveur Node).
# nx/ny/nw/nh : zone occupée par le widget quand il est affiché seul dans une source 1920x1080.
# x/y : position par défaut dans la scène (par défaut = zone native). full : widget plein écran.
FULL = dict(nx=0, ny=0, nw=1920, nh=1080, full=True)


def _w(key, label, group, url, nx, ny, nw, nh, x=None, y=None, full=False, z=10, enabled=False, scale=1.0):
    x = nx if x is None else x
    y = ny if y is None else y
    # dx/dy/dscale : réglage « d'origine » (celui d'un widget jamais déplacé, et du bouton « Position d'origine »)
    return dict(key=key, label=label, group=group, url=url, nx=nx, ny=ny, nw=nw, nh=nh,
                x=x, y=y, full=full, z=z, enabled=enabled, dx=x, dy=y, dscale=scale,
                fw=1920, fh=1080, embed="ok", note="")


# Les écrans de titre se placent à 100 % : leur taille (140 %) est réglée dans la page Titres
TITLE = dict(**FULL, z=42)


STATIC_WIDGETS = [
    # Écrans de titre (page « Titres ») : groupe à part, en haut de la liste des widgets
    _w("titre_auto",   "Titre · Automatique (début / pause / fin selon la scène OBS)", "Titres", "/overlay/titre/auto", **TITLE),
    _w("titre_start",  "Titre · Début de live (avec décompte)", "Titres", "/overlay/titre/start", **TITLE),
    _w("titre_brk",    "Titre · Pause",                         "Titres", "/overlay/titre/brk",   **TITLE),
    _w("titre_end",    "Titre · Fin de live",                   "Titres", "/overlay/titre/end",   **TITLE),
    # Lecteur séparé en 3 widgets : une même page, filtrée par ?only= (voir /shoutout dans server.js)
    _w("so",           "Shoutout (clip d'un streamer)", "Écran", "{NODE}/shoutout?only=so",     480, 190, 960, 700, z=5),
    _w("replay",       "Replay (clip de ta chaîne)",    "Écran", "{NODE}/shoutout?only=replay", 480, 190, 960, 700, z=5),
    _w("tiktok",       "TikTok",                        "Écran", "{NODE}/shoutout?only=tiktok", 1414, 108, 486, 864, z=5),
    _w("alertes",      "Alertes des commandes (images / sons)", "Écran", "{NODE}/alerts",          **FULL, z=6),
    _w("anniversaire", "Anniversaire",              "Écran", "/overlay/anniversaire",  **FULL, z=20),
    _w("emotes",       "Mur d'emotes",              "Écran", "/overlay/emotes",        **FULL, z=3),
    _w("clips",        "Clips du mois (vote)",      "Écran", "/overlay/clips",         **FULL, z=7),
    _w("poll",         "Sondage du bot",            "Écran", "/overlay/poll",          435, 30, 1050, 240),
    _w("twitch_poll",  "Sondage Twitch",            "Écran", "/overlay/twitch_poll",   30, 890, 800, 160),
    _w("trophies",     "Trophées",                  "Écran", "/overlay/trophies",      40, 40, 360, 100),
    _w("time",         "Chronomètre & minuteur (!timer, !chrono)", "Écran", "/overlay/time",          0, 0, 1920, 105),
    _w("wheels",       "Roues",            "Roues", "/overlay/wheels",        660, 240, 614, 651, z=15),
    _w("credits",      "Générique de fin",          "Écran", "/overlay/credits",       **FULL, z=30),
    _w("brb",          "BRB / pause",               "Écran", "{NODE}/brb",             **FULL, z=40),
    _w("events",       "Animations d'alertes (follow, sub, raid, screamer)", "Écran", "/overlay/events", **FULL, z=45),
    _w("felix",        "Fel-X (IA)",                "Écran", "/overlay/felix",         830, 450, 260, 180),
    _w("lbl_followers", "Label · Followers",        "Labels", "/overlay/followers",    0, 0, 200, 50,  x=20, y=20),
    _w("lbl_viewers",   "Label · Viewers",          "Labels", "/overlay/viewers",      0, 0, 110, 50,  x=20, y=100),
    _w("lbl_subs",      "Label · Subs",             "Labels", "/overlay/subs",         0, 0, 140, 50,  x=20, y=180),
    _w("lbl_heure",     "Label · Heure",            "Labels", "/overlay/heure",        0, 516, 220, 50, x=20, y=260),
    _w("lbl_follow",    "Label · Dernier follow",   "Labels", "/overlay/label/follow",  0, 518, 460, 50, x=20, y=380),
    _w("lbl_sub",       "Label · Dernier sub",      "Labels", "/overlay/label/sub",     0, 518, 460, 50, x=20, y=470),
    _w("lbl_subgift",   "Label · Dernier subgift",  "Labels", "/overlay/label/subgift", 0, 518, 460, 50, x=20, y=560),
    _w("lbl_bits",      "Label · Derniers bits",    "Labels", "/overlay/label/bits",    0, 518, 460, 50, x=20, y=650),
    _w("lbl_raid",      "Label · Dernier raid",     "Labels", "/overlay/label/raid",    0, 518, 460, 50, x=20, y=740),
]
STATIC_KEYS = {w["key"] for w in STATIC_WIDGETS}

_table_ready = False


async def _ensure_table():
    global _table_ready
    if _table_ready:
        return
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                slug       TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("ALTER TABLE scenes ADD COLUMN IF NOT EXISTS frame BOOLEAN NOT NULL DEFAULT FALSE")
        await db.execute("ALTER TABLE scenes ADD COLUMN IF NOT EXISTS frame_color TEXT NOT NULL DEFAULT '#ff7a18'")
        await db.execute("ALTER TABLE scenes ADD COLUMN IF NOT EXISTS tint BOOLEAN NOT NULL DEFAULT FALSE")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scene_widgets (
                scene_slug TEXT NOT NULL DEFAULT 'scene',
                widget_key TEXT NOT NULL,
                enabled    BOOLEAN NOT NULL DEFAULT FALSE,
                x          INTEGER NOT NULL DEFAULT 0,
                y          INTEGER NOT NULL DEFAULT 0,
                scale      DOUBLE PRECISION NOT NULL DEFAULT 1,
                z          INTEGER NOT NULL DEFAULT 10,
                PRIMARY KEY (scene_slug, widget_key)
            )
        """)
        # Migration de l'ancienne table (une seule scène, clé = widget) vers « une disposition par scène »
        c = await db.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = 'scene_widgets' AND column_name = 'scene_slug'")
        if not await c.fetchone():
            await db.execute("ALTER TABLE scene_widgets ADD COLUMN scene_slug TEXT NOT NULL DEFAULT 'scene'")
            await db.execute("ALTER TABLE scene_widgets DROP CONSTRAINT IF EXISTS scene_widgets_pkey")
            await db.execute("ALTER TABLE scene_widgets ADD PRIMARY KEY (scene_slug, widget_key)")
        await db.execute(
            "INSERT INTO scenes (slug, name) VALUES ('scene', 'Scène principale') ON CONFLICT (slug) DO NOTHING")
        # Migrations ponctuelles (une seule fois chacune)
        await db.execute("CREATE TABLE IF NOT EXISTS scene_migrations (name TEXT PRIMARY KEY)")
        c = await db.execute("SELECT 1 FROM scene_migrations WHERE name = 'wheels_measured_box'")
        if not await c.fetchone():
            # La zone de la roue est maintenant mesurée (614×651 à partir de 660,240) au lieu de 440×440 à
            # partir de 740,320 : on décale la position enregistrée pour que la roue reste EXACTEMENT où elle était.
            await db.execute("""UPDATE scene_widgets
                                SET x = x - ROUND(80 * scale), y = y - ROUND(80 * scale)
                                WHERE widget_key = 'wheels'""")
            await db.execute("INSERT INTO scene_migrations (name) VALUES ('wheels_measured_box')")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scene_obs_sources (
                source_key TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                url        TEXT NOT NULL DEFAULT '',
                width      INTEGER NOT NULL DEFAULT 1920,
                height     INTEGER NOT NULL DEFAULT 1080,
                embed      TEXT NOT NULL DEFAULT 'ok',
                note       TEXT NOT NULL DEFAULT ''
            )
        """)
        await db.execute("ALTER TABLE scene_obs_sources ADD COLUMN IF NOT EXISTS builtin_key TEXT NOT NULL DEFAULT ''")
    _table_ready = True


async def _all_widgets(scene: str = "scene") -> list[dict]:
    """Registre des widgets fusionné avec ce qui est enregistré en base pour cette scène."""
    await _ensure_table()
    widgets = [dict(w) for w in STATIC_WIDGETS]

    async with get_db_connection() as db:
        c = await db.execute("SELECT widget_key, enabled, x, y, scale, z FROM scene_widgets WHERE scene_slug = $1", (scene,))
        saved = {r["widget_key"]: dict(r) for r in await c.fetchall()}
        c = await db.execute("SELECT source_key, name, url, width, height, embed, note, builtin_key FROM scene_obs_sources ORDER BY name")
        obs_rows = [dict(r) for r in await c.fetchall()]

    by_key = {w["key"]: w for w in widgets}
    extra = 0
    for r in obs_rows:
        target = by_key.get(r["builtin_key"]) if r["builtin_key"] else None
        if target is not None:
            # Même overlay qu'un widget existant : pas de doublon, il prend la taille réelle de la source OBS
            exact = _normalize_url(r["url"]) == target["url"]
            if exact and (r["width"], r["height"]) != (1920, 1080):
                target["nx"], target["ny"], target["nw"], target["nh"] = 0, 0, r["width"], r["height"]
                target["fw"], target["fh"] = r["width"], r["height"]
                target["note"] = f"Taille reprise d'OBS : {r['width']}×{r['height']} (source « {r['name']} »)."
            continue
        w = _w(r["source_key"], r["name"], "Autres overlays", r["url"], 0, 0, r["width"], r["height"],
               x=20 + (extra % 6) * 40, y=100 + (extra % 6) * 40, z=12)
        w["fw"], w["fh"] = r["width"], r["height"]
        w["embed"], w["note"] = "ok", r["note"]
        widgets.append(w)
        extra += 1

    legacy = saved.get("lecteur")
    for w in widgets:
        s = saved.get(w["key"])
        if not s and legacy and w["key"] in ("so", "replay", "tiktok"):
            s = dict(legacy, x=w["x"], y=w["y"], scale=1.0)  # reprend seulement « activé » et l'ordre
        w["saved"] = bool(s)
        w["enabled"] = bool(s["enabled"]) if s else w["enabled"]
        w["x"] = int(s["x"]) if s else w["x"]
        w["y"] = int(s["y"]) if s else w["y"]
        w["scale"] = float(s["scale"]) if s else w["dscale"]
        w["z"] = int(s["z"]) if s else w["z"]
    return widgets


class WidgetState(BaseModel):
    key: str
    enabled: bool = False
    x: int = 0
    y: int = 0
    scale: float = 1.0
    z: int = 10


class ScenePayload(BaseModel):
    widgets: list[WidgetState]


# ── Admin ────────────────────────────────────────────────────────────────────

@router.get("/admin/scene", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_scene_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/scene_manager.html",
                                      context={"embed": request.query_params.get("embed") == "1"})


# ── Scènes (une disposition de widgets par scène) ───────────────────────────

class SceneName(BaseModel):
    name: str
    copy_from: str | None = None


def _url_slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def _reserved_slugs(request: Request) -> set:
    """Premiers segments déjà pris sous /overlay/ par les autres overlays du bot."""
    reserved = set()
    for r in request.app.routes:
        path = getattr(r, "path", "") or ""
        if path.startswith("/overlay/"):
            seg = path.split("/")[2]
            if seg and "{" not in seg:
                reserved.add(seg.lower())
    return reserved


async def _scene_or_404(slug: str | None) -> dict:
    await _ensure_table()
    async with get_db_connection() as db:
        if slug:
            c = await db.execute("SELECT slug, name FROM scenes WHERE slug = $1", (slug.lower(),))
        else:
            c = await db.execute("SELECT slug, name FROM scenes ORDER BY created_at, slug LIMIT 1")
        row = await c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scène introuvable.")
    return dict(row)


@router.get("/admin/api/scenes", dependencies=[Depends(require_admin)])
async def admin_scenes_list():
    await _ensure_table()
    async with get_db_connection() as db:
        c = await db.execute("SELECT slug, name, frame, frame_color, tint FROM scenes ORDER BY created_at, slug")
        rows = [dict(r) for r in await c.fetchall()]
    scenes = []
    for r in rows:
        active = sum(1 for w in await _all_widgets(r["slug"]) if w["enabled"])
        scenes.append(dict(r, path=f"/overlay/{r['slug']}", active=active))
    return {"scenes": scenes}


@router.post("/admin/api/scenes", dependencies=[Depends(require_admin)])
async def admin_scenes_create(payload: SceneName, request: Request):
    await _ensure_table()
    name = payload.name.strip()
    slug = _url_slug(name)
    if not name or not slug:
        raise HTTPException(status_code=400, detail="Donne un nom (lettres ou chiffres).")
    if slug in _reserved_slugs(request):
        raise HTTPException(status_code=400, detail=f"« {slug} » est déjà utilisé par un autre overlay du bot, choisis un autre nom.")
    async with get_db_connection() as db:
        c = await db.execute("SELECT 1 FROM scenes WHERE slug = $1", (slug,))
        if await c.fetchone():
            raise HTTPException(status_code=400, detail=f"Une scène « {slug} » existe déjà.")
        await db.execute("INSERT INTO scenes (slug, name) VALUES ($1, $2)", (slug, name))
        if payload.copy_from:
            await db.execute(
                """INSERT INTO scene_widgets (scene_slug, widget_key, enabled, x, y, scale, z)
                   SELECT $1, widget_key, enabled, x, y, scale, z FROM scene_widgets WHERE scene_slug = $2""",
                (slug, payload.copy_from.lower()),
            )
            src_bg = _bg_path(payload.copy_from.lower())
            if src_bg:
                shutil.copyfile(src_bg, os.path.join(BG_DIR, f"bg_{slug}" + os.path.splitext(src_bg)[1]))
    return {"status": "ok", "slug": slug, "name": name, "path": f"/overlay/{slug}"}


@router.put("/admin/api/scenes/{slug}", dependencies=[Depends(require_admin)])
async def admin_scenes_rename(slug: str, payload: SceneName, request: Request):
    scene = await _scene_or_404(slug)
    name = payload.name.strip()
    new_slug = _url_slug(name)
    if not name or not new_slug:
        raise HTTPException(status_code=400, detail="Donne un nom (lettres ou chiffres).")
    async with get_db_connection() as db:
        if new_slug != scene["slug"]:
            if new_slug in _reserved_slugs(request):
                raise HTTPException(status_code=400, detail=f"« {new_slug} » est déjà utilisé par un autre overlay du bot.")
            c = await db.execute("SELECT 1 FROM scenes WHERE slug = $1", (new_slug,))
            if await c.fetchone():
                raise HTTPException(status_code=400, detail=f"Une scène « {new_slug} » existe déjà.")
            await db.execute("UPDATE scenes SET slug = $1, name = $2 WHERE slug = $3", (new_slug, name, scene["slug"]))
            await db.execute("UPDATE scene_widgets SET scene_slug = $1 WHERE scene_slug = $2", (new_slug, scene["slug"]))
            old_bg = _bg_path(scene["slug"])
            if old_bg:
                os.replace(old_bg, os.path.join(BG_DIR, f"bg_{new_slug}" + os.path.splitext(old_bg)[1]))
        else:
            await db.execute("UPDATE scenes SET name = $1 WHERE slug = $2", (name, scene["slug"]))
    return {"status": "ok", "slug": new_slug, "name": name, "path": f"/overlay/{new_slug}"}


class TintPayload(BaseModel):
    tint: bool = False


@router.put("/admin/api/scenes/{slug}/tint", dependencies=[Depends(require_admin)])
async def admin_scene_tint(slug: str, payload: TintPayload):
    """Teinte transparente du thème (couleur réglée dans /admin/labels) : active ou non pour cette scène."""
    scene = await _scene_or_404(slug)
    async with get_db_connection() as db:
        await db.execute("UPDATE scenes SET tint = $1 WHERE slug = $2", (payload.tint, scene["slug"]))
    return {"status": "ok", "tint": payload.tint}


class FramePayload(BaseModel):
    frame: bool = False
    frame_color: str = "#ff7a18"


@router.put("/admin/api/scenes/{slug}/frame", dependencies=[Depends(require_admin)])
async def admin_scene_frame(slug: str, payload: FramePayload):
    scene = await _scene_or_404(slug)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", payload.frame_color):
        raise HTTPException(status_code=400, detail="Couleur invalide.")
    async with get_db_connection() as db:
        await db.execute("UPDATE scenes SET frame = $1, frame_color = $2 WHERE slug = $3",
                         (payload.frame, payload.frame_color, scene["slug"]))
    return {"status": "ok", "frame": payload.frame, "frame_color": payload.frame_color}


@router.delete("/admin/api/scenes/{slug}", dependencies=[Depends(require_admin)])
async def admin_scenes_delete(slug: str):
    scene = await _scene_or_404(slug)
    async with get_db_connection() as db:
        c = await db.execute("SELECT COUNT(*) AS n FROM scenes")
        if int((await c.fetchone())["n"]) <= 1:
            raise HTTPException(status_code=400, detail="Il faut garder au moins une scène.")
        await db.execute("DELETE FROM scene_widgets WHERE scene_slug = $1", (scene["slug"],))
        await db.execute("DELETE FROM scenes WHERE slug = $1", (scene["slug"],))
    _clear_bg(scene["slug"])
    return {"status": "ok"}


class CopyPayload(BaseModel):
    targets: list[str]
    keys: list[str] | None = None        # None = tous les widgets
    background: bool = False


class ImportPayload(BaseModel):
    name: str
    widgets: list[dict]


async def _effective_rows(slug: str, keys: list[str] | None) -> list[dict]:
    rows = []
    for w in await _all_widgets(slug):
        if keys is None or w["key"] in keys:
            rows.append({"key": w["key"], "enabled": bool(w["enabled"]), "x": int(w["x"]), "y": int(w["y"]),
                         "scale": float(w["scale"]), "z": int(w["z"])})
    return rows


@router.post("/admin/api/scenes/{slug}/copy", dependencies=[Depends(require_admin)])
async def admin_scenes_copy(slug: str, payload: CopyPayload):
    """Copie l'état (activé, position, échelle, ordre) de tout ou partie des widgets vers d'autres scènes."""
    src = await _scene_or_404(slug)
    targets = []
    for t in payload.targets:
        if t == src["slug"]:
            continue
        targets.append((await _scene_or_404(t))["slug"])
    if not targets:
        raise HTTPException(status_code=400, detail="Choisis au moins une autre scène.")
    rows = await _effective_rows(src["slug"], payload.keys)
    if not rows:
        raise HTTPException(status_code=400, detail="Aucun widget à copier.")
    async with get_db_connection() as db:
        for t in targets:
            for r in rows:
                await db.execute(
                    """INSERT INTO scene_widgets (scene_slug, widget_key, enabled, x, y, scale, z)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (scene_slug, widget_key) DO UPDATE
                       SET enabled = EXCLUDED.enabled, x = EXCLUDED.x, y = EXCLUDED.y,
                           scale = EXCLUDED.scale, z = EXCLUDED.z""",
                    (t, r["key"], r["enabled"], r["x"], r["y"], r["scale"], r["z"]),
                )
    if payload.background:
        bg = _bg_path(src["slug"])
        if bg:
            for t in targets:
                _clear_bg(t)
                shutil.copyfile(bg, os.path.join(BG_DIR, f"bg_{t}" + os.path.splitext(bg)[1]))
    return {"status": "ok", "widgets": len(rows), "scenes": targets}


@router.get("/admin/api/scenes/{slug}/export", dependencies=[Depends(require_admin)])
async def admin_scenes_export(slug: str):
    sc = await _scene_or_404(slug)
    return {"format": "masthbot-scene", "version": 1, "name": sc["name"], "widgets": await _effective_rows(sc["slug"], None)}


@router.post("/admin/api/scenes/import", dependencies=[Depends(require_admin)])
async def admin_scenes_import(payload: ImportPayload, request: Request):
    """Crée une nouvelle scène à partir d'un fichier exporté (les widgets inconnus sont ignorés)."""
    await _ensure_table()
    name = payload.name.strip()
    slug = _url_slug(name)
    if not name or not slug:
        raise HTTPException(status_code=400, detail="Donne un nom à la scène importée.")
    if slug in _reserved_slugs(request):
        raise HTTPException(status_code=400, detail=f"« {slug} » est déjà utilisé par un autre overlay du bot.")
    known = {w["key"] for w in await _all_widgets("scene")}
    async with get_db_connection() as db:
        c = await db.execute("SELECT 1 FROM scenes WHERE slug = $1", (slug,))
        if await c.fetchone():
            raise HTTPException(status_code=400, detail=f"Une scène « {slug} » existe déjà : change le nom.")
        await db.execute("INSERT INTO scenes (slug, name) VALUES ($1, $2)", (slug, name))
        count = 0
        for w in payload.widgets:
            try:
                key = str(w["key"])
                if key not in known:
                    continue
                scale = min(max(float(w.get("scale", 1)), 0.05), 5.0)
                await db.execute(
                    """INSERT INTO scene_widgets (scene_slug, widget_key, enabled, x, y, scale, z)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    (slug, key, bool(w.get("enabled")), int(w.get("x", 0)), int(w.get("y", 0)), scale, int(w.get("z", 10))),
                )
                count += 1
            except (KeyError, TypeError, ValueError):
                continue
    return {"status": "ok", "slug": slug, "name": name, "path": f"/overlay/{slug}", "widgets": count}


@router.get("/admin/api/scene", dependencies=[Depends(require_admin)])
async def admin_scene_get(scene: str | None = None):
    sc = await _scene_or_404(scene)
    return {"scene": sc, "widgets": await _all_widgets(sc["slug"])}


@router.put("/admin/api/scene", dependencies=[Depends(require_admin)])
async def admin_scene_save(payload: ScenePayload, scene: str | None = None):
    sc = await _scene_or_404(scene)
    known = {w["key"] for w in await _all_widgets(sc["slug"])}
    for w in payload.widgets:
        if w.key not in known:
            raise HTTPException(status_code=400, detail=f"Widget inconnu : {w.key}")
    async with get_db_connection() as db:
        for w in payload.widgets:
            scale = min(max(w.scale, 0.05), 5.0)
            await db.execute(
                """INSERT INTO scene_widgets (scene_slug, widget_key, enabled, x, y, scale, z)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (scene_slug, widget_key) DO UPDATE
                   SET enabled = EXCLUDED.enabled, x = EXCLUDED.x, y = EXCLUDED.y,
                       scale = EXCLUDED.scale, z = EXCLUDED.z""",
                (sc["slug"], w.key, w.enabled, w.x, w.y, scale, w.z),
            )
    return {"status": "ok", "count": len(payload.widgets)}


# ── Import des sources navigateur d'OBS (via scripts/obs_web_sources.js, lecture seule) ──

def _normalize_url(url: str) -> str:
    """http://192.168.1.110:3005/shoutout -> {NODE}/shoutout ; http://hôte:8000/overlay/x -> /overlay/x"""
    try:
        u = urlparse(url.strip())
    except Exception:
        return url
    if u.scheme not in ("http", "https"):
        return url
    path = u.path.rstrip("/") or "/"
    return ("{NODE}" + path) if u.port == 3005 else path


def _our_hosts(request_host: str = "") -> set:
    """Adresses sous lesquelles les overlays du bot sont joignables (cette machine)."""
    hosts = {"localhost", "127.0.0.1", "::1", (request_host or "").lower()}
    try:
        hosts.add(socket.gethostname().lower())
        for info in socket.getaddrinfo(socket.gethostname(), None):
            hosts.add(info[4][0])
    except Exception:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))  # aucune donnée envoyée : sert à trouver l'IP locale
        hosts.add(probe.getsockname()[0])
        probe.close()
    except Exception:
        pass
    try:
        hosts.add((urlparse(settings.OVERLAY_NODE_URL).hostname or "").lower())
    except Exception:
        pass
    hosts.discard("")
    return hosts


# Pages à nous qu'on ne propose pas comme widget : la scène elle-même et le bus de sons du Deck (invisible)
_NEVER_WIDGETS = ("/overlay/scene", "/overlay_deck")


def _match_builtin(url: str) -> str | None:
    """Clé du widget existant qui affiche déjà cette page (ou '' si page à nous sans équivalent)."""
    norm = _normalize_url(url)
    for w in STATIC_WIDGETS:
        if w["url"] == norm:
            return w["key"]
    if re.fullmatch(r"/overlay/wheels?(/\d+)?", norm):
        return "wheels"
    if norm == "{NODE}/shoutout":  # lecteur complet = remplacé par Shoutout / Replay / TikTok
        return "so"
    return None


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_") or "source"


def _find_node() -> str | None:
    found = shutil.which("node")
    if found:
        return found
    candidates = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/node")))
    return candidates[-1] if candidates else ("/usr/bin/node" if os.path.exists("/usr/bin/node") else None)


async def _check_embed(url: str) -> tuple[str, str]:
    """('ok' | 'local' | 'blocked' | 'unknown', note) : la page peut-elle s'afficher dans un cadre de la scène ?"""
    low = url.lower()
    if not low.startswith(("http://", "https://")):
        return "local", "Fichier local : ne peut pas s'afficher dans la scène, garde-la comme source OBS. Ce cadre sert de repère."
    host = urlparse(url).hostname or ""
    try:
        if host in ("localhost",) or ipaddress.ip_address(host).is_private:
            return "ok", ""
    except ValueError:
        pass
    try:
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as resp:
                xfo = resp.headers.get("X-Frame-Options", "")
                csp = resp.headers.get("Content-Security-Policy", "")
                if xfo or re.search(r"frame-ancestors\s+[^;]*('none'|'self')", csp):
                    return "blocked", "Ce site refuse d'être affiché dans un cadre : garde-le comme source OBS. Ce cadre sert de repère."
        return "ok", ""
    except Exception:
        return "unknown", "Impossible de vérifier si ce site accepte d'être affiché dans la scène."


@router.post("/admin/api/scene/import_obs", dependencies=[Depends(require_admin)])
async def admin_scene_import_obs(request: Request):
    await _ensure_table()
    node = _find_node()
    script = os.path.join("scripts", "obs_web_sources.js")
    if not node or not os.path.exists(script):
        raise HTTPException(status_code=500, detail="Node.js ou scripts/obs_web_sources.js introuvable.")
    proc = await asyncio.create_subprocess_exec(
        node, script, "--json",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=40)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504, detail="OBS ne répond pas (délai dépassé).")
    if proc.returncode != 0:
        msg = (err.decode(errors="ignore").strip().splitlines() or ["Erreur inconnue"])[0]
        raise HTTPException(status_code=502, detail=msg)
    try:
        sources = json.loads(out.decode())
    except Exception:
        raise HTTPException(status_code=502, detail="Réponse illisible du script OBS.")

    ours = _our_hosts(request.url.hostname or "")
    async with get_db_connection() as db:
        c = await db.execute("SELECT slug FROM scenes")
        scene_paths = {f"/overlay/{r['slug']}" for r in await c.fetchall()}
    used, rows, seen_urls = set(), [], set()
    foreign = []
    for src in sources:
        url = (src.get("url") or "").strip()
        parsed = urlparse(url)
        is_ours = (parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in ours
                   and parsed.port in (8000, 3005, 8001))
        norm = _normalize_url(url)
        if not is_ours:
            foreign.append(src["name"])
            continue
        if norm.endswith(_NEVER_WIDGETS) or norm in scene_paths or norm in seen_urls:
            continue
        seen_urls.add(norm)
        key = base = "obs_" + _slug(src["name"])
        n = 2
        while key in used:
            key, n = f"{base}_{n}", n + 1
        used.add(key)
        builtin = _match_builtin(url)
        rows.append((key, src["name"], url, int(src.get("width") or 1920), int(src.get("height") or 1080),
                     "ok", "", builtin or ""))

    async with get_db_connection() as db:
        c = await db.execute("SELECT source_key FROM scene_obs_sources")
        existing = {r["source_key"] for r in await c.fetchall()}
        for r in rows:
            await db.execute(
                """INSERT INTO scene_obs_sources (source_key, name, url, width, height, embed, note, builtin_key)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (source_key) DO UPDATE
                   SET name = EXCLUDED.name, url = EXCLUDED.url, width = EXCLUDED.width,
                       height = EXCLUDED.height, embed = EXCLUDED.embed, note = EXCLUDED.note,
                       builtin_key = EXCLUDED.builtin_key""",
                r,
            )
        for gone in existing - used:
            await db.execute("DELETE FROM scene_obs_sources WHERE source_key = $1", (gone,))
            await db.execute("DELETE FROM scene_widgets WHERE widget_key = $1", (gone,))
    matched = sum(1 for r in rows if r[7])
    return {"status": "ok", "count": len(rows), "matched": matched, "added": len(rows) - matched,
            "ignored": len(foreign), "ignored_names": foreign, "removed": len(existing - used)}


# ── Test d'un widget (envoie un faux événement à l'overlay, visible tout de suite dans OBS) ──

EMOTE_TEST_URLS = ["https://static-cdn.jtvnw.net/emoticons/v2/25/default/dark/3.0"] * 12  # Kappa
NO_TEST = {
    "clips": "Le vote de clips se lance avec la commande de vote (il a besoin de vrais clips).",
    "felix": "Fel-X est toujours affiché, rien à tester.",
}


async def _node_post(path: str, payload: dict) -> dict:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async with session.post(f"{settings.OVERLAY_NODE_URL}{path}", json=payload) as resp:
            try:
                return await resp.json()
            except Exception:
                return {"status": resp.status}


@router.post("/admin/api/scene/test/{key}", dependencies=[Depends(require_admin)])
async def admin_scene_test(key: str):
    if key == "events":
        from app.services import alerts_service
        await alerts_service.fire_alert("follow", "PseudoTest", force=True)
        return {"ok": True, "message": "Animation de follow envoyée (les autres se testent dans /admin/alerts)."}
    if key.startswith("titre_"):
        return {"ok": False, "message": "Rien à déclencher : l'écran de titre s'affiche tel quel (décompte : page Titres)."}
    if key in ("credits", "brb"):
        return {"ok": False, "message": "Pas de test ici : le générique et le BRB se lancent depuis leurs propres pages."}
    if key.startswith("obs_"):
        return {"ok": False, "message": "Source importée d'OBS : rien à déclencher, elle s'affiche telle quelle."}
    if key.startswith("lbl_"):
        return {"ok": False, "message": "Les labels sont toujours affichés (ils se mettent à jour tout seuls)."}
    if key in NO_TEST:
        return {"ok": False, "message": NO_TEST[key]}

    if key == "replay":
        res = await _node_post("/api/replay", {})
        if res.get("status") == "success":
            return {"ok": True, "message": f"Replay lancé : « {res.get('title', '?')} »"}
        return {"ok": False, "message": "Aucun clip trouvé pour le test."}

    if key == "so":
        channel = settings.TWITCH_CHANNEL.replace("#", "").lower()
        await _node_post("/api/shoutout", {"target": channel, "slug": ""})
        return {"ok": True, "message": f"Shoutout de test lancé (clip aléatoire de {channel}). Rien n'est écrit dans le chat."}

    if key == "tiktok":
        return {"ok": False, "message": "Pas de test TikTok : lance !play avec un lien TikTok."}

    if key == "alertes":
        folder = "static/commands/images"
        files = sorted(f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in {".gif", ".png", ".jpg", ".jpeg", ".webp"}) if os.path.isdir(folder) else []
        if not files:
            return {"ok": False, "message": "Aucune image dans les commandes pour faire le test."}
        pick = random.choice(files)
        await _node_post("/api/trigger", {"type": "image", "details": {"filename": pick}})
        return {"ok": True, "message": f"Image envoyée : {pick}"}

    if key == "emotes":
        await _node_post("/api/trigger", {"type": "emote_rain", "details": {"urls": EMOTE_TEST_URLS}})
        return {"ok": True, "message": "Pluie d'emotes envoyée."}

    if key == "time":
        await _node_post("/api/trigger", {"type": "time_event", "details": {"action": "start", "mode": "timer", "duration": 30, "label": "TEST"}})
        return {"ok": True, "message": "Minuteur de test (30 s) lancé."}

    if key == "anniversaire":
        await trigger_overlay_event({"type": "anniversaire", "username": "Test"})
        return {"ok": True, "message": "Animation d'anniversaire envoyée."}

    if key == "trophies":
        await trigger_overlay_event({"type": "trophy_unlock", "details": {
            "username": "Testeur_Fou", "trophy_name": "Test de la scène", "icon": "🏆", "tier": "Or"}})
        return {"ok": True, "message": "Trophée de test envoyé."}

    if key == "poll":
        await trigger_overlay_event({"type": "show_poll", "poll": {
            "active": True, "question": "Sondage de test : ça marche ?", "total_votes": 10,
            "options": {"1": "Oui", "2": "Non", "3": "Peut-être"}, "results": {"1": 6, "2": 3, "3": 1}}})
        return {"ok": True, "message": "Sondage de test affiché (20 s)."}

    if key == "twitch_poll":
        ends = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
        await trigger_overlay_event({"type": "show_twitch_poll", "payload": {
            "title": "Sondage Twitch de test", "ends_at": ends, "total_votes": 10, "is_prediction": False,
            "choices": [{"title": "Choix A", "votes": 6}, {"title": "Choix B", "votes": 4}]}})
        return {"ok": True, "message": "Sondage Twitch de test affiché."}

    if key == "wheels":
        wheels = [w for w in await wheel_service.get_all_wheels() if len(w["items"]) >= 2]
        if not wheels:
            return {"ok": False, "message": "Aucune roue avec au moins 2 segments."}
        wheel = random.choice(wheels)
        idx = wheel_service.pick_winner(wheel["items"])
        await trigger_overlay_event({"type": "spin_wheel", "wheel_id": wheel["id"], "winner_index": idx})
        return {"ok": True, "message": f"Roue « {wheel['name']} » lancée (résultat : {wheel['items'][idx]['label']}). Rien n'est annoncé dans le chat."}

    raise HTTPException(status_code=404, detail="Widget inconnu.")


# ── Image de fond de l'éditeur (repère visuel, jamais affichée dans OBS) ──────

BG_DIR = "static/scene"
BG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
BG_MAX_BYTES = 15 * 1024 * 1024


def _bg_path(slug: str) -> str | None:
    names = [f"bg_{slug}"] + (["background"] if slug == "scene" else [])  # « background » = ancienne image
    for base in names:
        for ext in BG_EXTS:
            p = os.path.join(BG_DIR, base + ext)
            if os.path.exists(p):
                return p
    return None


def _clear_bg(slug: str):
    names = [f"bg_{slug}"] + (["background"] if slug == "scene" else [])
    for base in names:
        for ext in BG_EXTS:
            p = os.path.join(BG_DIR, base + ext)
            if os.path.exists(p):
                os.remove(p)


@router.get("/admin/api/scene/background", dependencies=[Depends(require_admin)])
async def admin_scene_bg_get(scene: str | None = None):
    sc = await _scene_or_404(scene)
    p = _bg_path(sc["slug"])
    if not p:
        raise HTTPException(status_code=404, detail="Aucune image de fond.")
    return FileResponse(p, headers={"Cache-Control": "private, max-age=3600"})


@router.post("/admin/api/scene/background", dependencies=[Depends(require_admin)])
async def admin_scene_bg_upload(scene: str | None = None, file: UploadFile = File(...)):
    sc = await _scene_or_404(scene)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in BG_EXTS:
        raise HTTPException(status_code=400, detail="Format non supporté (png, jpg, webp).")
    data = await file.read(BG_MAX_BYTES + 1)
    if len(data) > BG_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image trop lourde (15 Mo max).")
    os.makedirs(BG_DIR, exist_ok=True)
    _clear_bg(sc["slug"])
    with open(os.path.join(BG_DIR, f"bg_{sc['slug']}" + ext), "wb") as f:
        f.write(data)
    return {"status": "ok"}


@router.delete("/admin/api/scene/background", dependencies=[Depends(require_admin)])
async def admin_scene_bg_delete(scene: str | None = None):
    sc = await _scene_or_404(scene)
    _clear_bg(sc["slug"])
    return {"status": "ok"}


# ── Overlay OBS (public, comme les autres /overlay/*) ────────────────────────

@router.get("/api/scene/layout")
async def scene_layout(scene: str = "scene"):
    await _ensure_table()
    keys = ("key", "url", "nx", "ny", "nw", "nh", "fw", "fh", "x", "y", "scale", "z")
    widgets = [{k: w[k] for k in keys} for w in await _all_widgets(scene.lower())
               if w["enabled"] and w["embed"] not in ("local", "blocked")]
    async with get_db_connection() as db:
        c = await db.execute("SELECT frame, frame_color, tint FROM scenes WHERE slug = $1", (scene.lower(),))
        row = await c.fetchone()
    return {"widgets": sorted(widgets, key=lambda w: w["z"]),
            "frame": bool(row["frame"]) if row else False, "frame_color": row["frame_color"] if row else "#ff7a18",
            "tint": bool(row["tint"]) if row else False}


# Doit rester le DERNIER chemin /overlay/... déclaré : les overlays du bot (déclarés avant) l'emportent,
# ce nom libre ne sert que pour les scènes créées dans /admin/scene.
@router.get("/overlay/{slug}", response_class=HTMLResponse)
async def overlay_scene(request: Request, slug: str):
    await _scene_or_404(slug)
    return templates.TemplateResponse(request=request, name="overlays/scene_overlay.html", headers=NO_CACHE)
