"""Thème automatique selon la catégorie Twitch.

Quand la catégorie de la chaîne change (EventSub channel.update, même hors live) ou au début du live, on cherche
la première règle dont le texte est contenu dans le nom de la catégorie (sans tenir compte des majuscules) et on
applique le thème correspondant, comme un clic sur ce thème dans /admin/labels (réglages propres aux labels conservés).
Si aucune règle ne correspond : on garde le thème actuel, ou on applique le thème « autre catégorie » choisi.
Le choix manuel reste possible : on ne réagit qu'à un vrai changement de catégorie.
"""
import json
import logging

import aiohttp

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.theme_auto")

# Règles proposées au départ, tirées des jeux streamés sur la chaîne (modifiables dans /admin/labels)
DEFAULT_RULES = [
    ("Zelda", "zelda"),
    ("Silent Hill", "fog"), ("Hellraiser", "fog"), ("Silent Still", "fog"),
    ("Dead by Daylight", "werewolf"), ("Lycans", "werewolf"),
    ("Phasmophobia", "horror"), ("Mortuary Assistant", "horror"), ("Outlast", "horror"), ("Visage", "horror"),
    ("MADiSON", "horror"), ("Demonologist", "horror"), ("Resident Evil", "horror"), ("Song of Horror", "horror"),
    ("Unholy Priest", "horror"), ("Layers of Fear", "horror"), ("Little Nightmares", "horror"),
    ("Lethal Company", "horror"), ("Dark Hours", "horror"), ("Ghost Watchers", "horror"),
    ("Sea of Thieves", "pirate"), ("Black Flag", "pirate"),
    ("R.E.P.O", "repo"),
    ("Fortnite", "fortnite"),
    ("Elden Ring", "darkfantasy"), ("Lies of P", "darkfantasy"), ("Witcher", "darkfantasy"),
    ("Baldur's Gate", "darkfantasy"), ("Oblivion", "darkfantasy"),
    ("Fallout", "vault"), ("ARC Raiders", "vault"), ("HELLDIVERS", "vault"), ("Quarantine Zone", "vault"),
    ("No Man's Sky", "space"), ("Outer Wilds", "space"),
    ("Watch_Dogs", "cyber"), ("Watch Dogs", "cyber"), ("Detroit", "cyber"),
    ("Pokémon", "pokemon"),
    ("Dreamlight Valley", "cosy"), ("Animal Crossing", "cosy"), ("Planet Zoo", "cosy"), ("Cult of the Lamb", "cosy"),
    ("Grounded", "cosy"),
    ("Grand Theft Auto", "gta6"),
    ("Mario", "arcade"),
]
DEFAULT = {"enabled": True, "fallback": "", "rules": [{"match": m, "theme": t} for m, t in DEFAULT_RULES],
           "last_category": "", "last_applied": ""}

_ready = False


async def _ensure():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS theme_auto (id INTEGER PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}')")
        await db.execute("INSERT INTO theme_auto (id, data) VALUES (1, $1) ON CONFLICT (id) DO NOTHING",
                         (json.dumps(DEFAULT, ensure_ascii=False),))
    _ready = True


async def get_config() -> dict:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT data FROM theme_auto WHERE id = 1")
        row = await c.fetchone()
    try:
        data = json.loads(row["data"]) if row else {}
    except Exception:
        data = {}
    return {**DEFAULT, **data}


async def _write(cfg: dict):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("UPDATE theme_auto SET data = $1 WHERE id = 1", (json.dumps(cfg, ensure_ascii=False),))


def clean(raw: dict, presets: dict) -> dict:
    """Valide la configuration envoyée par la page d'admin (ValueError si invalide)."""
    rules = []
    for r in (raw.get("rules") or [])[:200]:
        match = str(r.get("match") or "").strip()[:80]
        theme = str(r.get("theme") or "").strip()
        if not match:
            continue
        if theme not in presets:
            raise ValueError(f"Thème inconnu pour « {match} ».")
        rules.append({"match": match, "theme": theme})
    fallback = str(raw.get("fallback") or "").strip()
    if fallback and fallback not in presets:
        raise ValueError("Thème « autre catégorie » inconnu.")
    return {"enabled": bool(raw.get("enabled")), "fallback": fallback, "rules": rules}


def theme_for(category: str, cfg: dict) -> str:
    """Thème à appliquer pour cette catégorie ('' = ne rien changer)."""
    name = (category or "").casefold()
    for r in cfg.get("rules", []):
        if r["match"].casefold() in name:
            return r["theme"]
    return cfg.get("fallback") or ""


async def save_config(new: dict):
    cfg = await get_config()
    cfg.update(new)
    await _write(cfg)
    return cfg


async def on_category(category: str, force: bool = False):
    """Appelé quand la catégorie change. force=False : rien si la catégorie est la même que la dernière vue."""
    if not category:
        return
    cfg = await get_config()
    if not force and category == cfg.get("last_category"):
        return
    cfg["last_category"] = category
    theme = theme_for(category, cfg) if cfg.get("enabled") else ""
    if theme:
        from app.routes.label_style import apply_preset, get_style
        current = await get_style()
        if current.get("preset") != theme:
            await apply_preset(theme)
            logger.info(f"🎨 [THÈME AUTO] Catégorie « {category} » → thème « {theme} ».")
        cfg["last_applied"] = theme
    else:
        cfg["last_applied"] = ""
        logger.info(f"🎨 [THÈME AUTO] Catégorie « {category} » : aucune règle, thème inchangé.")
    await _write(cfg)


async def current_category() -> str:
    """Catégorie actuelle de la chaîne (API Twitch), '' si indisponible."""
    from app.core.config import settings
    headers = {"Client-Id": settings.TWITCH_CLIENT_ID, "Authorization": f"Bearer {settings.TWITCH_OAUTH_TOKEN.replace('oauth:', '')}"}
    url = f"https://api.twitch.tv/helix/channels?broadcaster_id={settings.TWITCH_BROADCASTER_ID}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    return ""
                data = (await r.json()).get("data") or []
                return data[0].get("game_name", "") if data else ""
    except Exception as e:
        logger.warning(f"⚠️ [THÈME AUTO] Catégorie actuelle illisible : {e}")
        return ""
