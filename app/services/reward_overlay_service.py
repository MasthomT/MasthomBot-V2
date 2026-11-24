"""Overlay « Récompenses de points de chaîne » : chaque récompense peut afficher une image / vidéo (et un son)
à l'endroit et à la taille choisis dans la page Récompenses (onglet Overlay).

- Réglages par récompense (repérée par son TITRE, comme les automatisations) : table `reward_visuals`.
- Quand un viewer prend la récompense (EventSub, via automation_service.on_eventsub), un événement est mis en file.
- L'overlay /overlay/recompenses vient chercher les nouveaux événements par petites requêtes (pas de connexion
  permanente : OBS sature vers 6 connexions par serveur, voir la mémoire du projet).
"""
import time

from app.core.database import get_db_connection

FIELDS = ("title", "media", "sound", "x", "y", "w", "h", "duration", "volume", "enabled")
_ready = False
_events: list[dict] = []          # file circulaire des derniers événements (id croissant)
_next_id = int(time.time() * 1000)


async def _ensure():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS reward_visuals (
            title_key TEXT PRIMARY KEY, title TEXT NOT NULL, media TEXT NOT NULL DEFAULT '', sound TEXT NOT NULL DEFAULT '',
            x INTEGER NOT NULL DEFAULT 660, y INTEGER NOT NULL DEFAULT 240, w INTEGER NOT NULL DEFAULT 600, h INTEGER NOT NULL DEFAULT 600,
            duration DOUBLE PRECISION NOT NULL DEFAULT 6, volume INTEGER NOT NULL DEFAULT 100,
            enabled BOOLEAN NOT NULL DEFAULT TRUE, updated_at TIMESTAMP NOT NULL DEFAULT NOW())""")
    _ready = True


def _key(title: str) -> str:
    return (title or "").strip().lower()


async def list_visuals() -> list[dict]:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT title, media, sound, x, y, w, h, duration, volume, enabled FROM reward_visuals ORDER BY title")
        return [dict(r) for r in await c.fetchall()]


async def get_visual(title: str) -> dict | None:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT title, media, sound, x, y, w, h, duration, volume, enabled FROM reward_visuals WHERE title_key = $1", (_key(title),))
        r = await c.fetchone()
    return dict(r) if r else None


def clean(raw: dict) -> dict:
    from app.services.automation_service import media_files
    title = str(raw.get("title") or "").strip()[:45]
    if not title:
        raise ValueError("Choisis une récompense.")
    files = media_files()
    media = str(raw.get("media") or "").strip()
    sound = str(raw.get("sound") or "").strip()
    if media and media not in files["images"]:
        raise ValueError(f"Image / vidéo introuvable : {media}")
    if sound and sound not in files["sounds"]:
        raise ValueError(f"Son introuvable : {sound}")
    if not media and not sound:
        raise ValueError("Choisis au moins une image / vidéo ou un son.")
    try:
        x, y, w, h = (int(round(float(raw.get(k) or 0))) for k in ("x", "y", "w", "h"))
        duration = float(raw.get("duration") or 0)
        volume = int(raw.get("volume") if raw.get("volume") is not None else 100)
    except (TypeError, ValueError):
        raise ValueError("Position, taille, durée et volume doivent être des nombres.")
    if not (20 <= w <= 3840 and 20 <= h <= 2160 and -1920 <= x <= 3840 and -1080 <= y <= 2160):
        raise ValueError("Position ou taille hors de l'écran.")
    if not 0 <= duration <= 120 or not 0 <= volume <= 100:
        raise ValueError("Durée (0 à 120 s, 0 = durée de la vidéo) ou volume (0 à 100) hors limites.")
    return {"title": title, "media": media, "sound": sound, "x": x, "y": y, "w": w, "h": h,
            "duration": duration, "volume": volume, "enabled": bool(raw.get("enabled", True))}


async def save_visual(raw: dict) -> dict:
    v = clean(raw)
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("""INSERT INTO reward_visuals (title_key, title, media, sound, x, y, w, h, duration, volume, enabled, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            ON CONFLICT (title_key) DO UPDATE SET title = EXCLUDED.title, media = EXCLUDED.media, sound = EXCLUDED.sound,
              x = EXCLUDED.x, y = EXCLUDED.y, w = EXCLUDED.w, h = EXCLUDED.h, duration = EXCLUDED.duration,
              volume = EXCLUDED.volume, enabled = EXCLUDED.enabled, updated_at = NOW()""",
                         (_key(v["title"]), v["title"], v["media"], v["sound"], v["x"], v["y"], v["w"], v["h"],
                          v["duration"], v["volume"], v["enabled"]))
    return v


async def delete_visual(title: str):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("DELETE FROM reward_visuals WHERE title_key = $1", (_key(title),))


def push(visual: dict, user: str = "", test: bool = False):
    """Met un affichage en file pour l'overlay."""
    global _next_id
    _next_id += 1
    _events.append({"id": _next_id, "at": time.time(), "user": user, "test": test,
                    **{k: visual[k] for k in FIELDS if k in visual}})
    del _events[:-50]


def events_after(after: int) -> dict:
    now = time.time()
    # premier appel de l'overlay (after = 0) : on ne rejoue rien du passé, on donne juste le dernier id
    if after <= 0:
        return {"last": _events[-1]["id"] if _events else _next_id, "events": []}
    return {"last": _events[-1]["id"] if _events else _next_id,
            "events": [e for e in _events if e["id"] > after and now - e["at"] < 120]}


async def on_redemption(title: str, user: str):
    v = await get_visual(title)
    if v and v["enabled"]:
        push(v, user)
