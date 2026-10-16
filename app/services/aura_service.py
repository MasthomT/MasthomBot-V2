"""Récompense de points de chaîne « Aura » : un viewer écrit une couleur (« rouge », « red », « #ff8800 »…) et
l'aura (cadre orangé des écrans de titre et des scènes) prend cette couleur.

Le bot crée lui-même la récompense (message du viewer obligatoire) pour pouvoir la valider ou la rembourser
quand la couleur n'est pas comprise. La couleur choisie est gardée en base : les overlays la relisent toutes les
2 secondes (`GET /api/aura`), elle reprend la couleur normale après la durée réglée (0 = jusqu'au prochain choix).
"""
import json
import logging
import re
import time
import unicodedata

from app.core.database import get_db_connection
from app.services import podium_service as P

logger = logging.getLogger("masthbot.aura")

DEFAULT_CONFIG = {
    "enabled": True,
    "base_color": "#ff7a18",     # couleur NORMALE de l'aura, la même sur tous les écrans de titre et toutes les scènes
    "reward_title": "Aura",
    "reward_id": "",
    "cost": 500,
    "cooldown": 30,              # secondes d'attente entre deux achats (côté Twitch)
    "prompt": "Écris une couleur (rouge, bleu, violet…) ou un code comme #ff8800 : l'aura du stream la prend !",
    "color": "#ff7a18",          # couleur de la récompense dans Twitch
    "duration_min": 10,          # retour à la couleur normale après N minutes (0 = jusqu'au prochain choix)
    "announce": True,
    "message_ok": "🎨 @{user} change l'aura du stream : {color} !",
    "message_bad": "@{user} je ne connais pas la couleur « {input} » (essaie rouge, bleu, vert… ou un code #ff8800). Points remboursés.",
}

# Noms de couleurs (sans accent, minuscules) → #rrggbb. Français et anglais.
NAMES = {
    "rouge": "#ff2d2d", "red": "#ff2d2d", "bleu": "#2d6bff", "blue": "#2d6bff", "vert": "#2dff6b", "green": "#2dff6b",
    "jaune": "#ffe62d", "yellow": "#ffe62d", "orange": "#ff7a18", "violet": "#9b4dff", "purple": "#9b4dff",
    "rose": "#ff6fb5", "pink": "#ff6fb5", "blanc": "#ffffff", "white": "#ffffff", "noir": "#000000", "black": "#000000",
    "cyan": "#2de2ff", "turquoise": "#1ad6c0", "magenta": "#ff2dd1", "fuchsia": "#ff2dd1", "marron": "#8b5a2b",
    "brown": "#8b5a2b", "gris": "#9aa0a6", "grey": "#9aa0a6", "gray": "#9aa0a6", "or": "#ffc83d", "dore": "#ffc83d",
    "gold": "#ffc83d", "argent": "#c0c0c0", "silver": "#c0c0c0", "bordeaux": "#800020", "maroon": "#800020",
    "citron": "#b6ff2d", "lime": "#b6ff2d", "indigo": "#4b2dff", "corail": "#ff7f50", "coral": "#ff7f50",
    "saumon": "#fa8072", "salmon": "#fa8072", "lavande": "#b9a1ff", "lavender": "#b9a1ff", "menthe": "#7dffc4",
    "mint": "#7dffc4", "ciel": "#7fd4ff", "sky": "#7fd4ff", "beige": "#f5deb3", "kaki": "#8a9a3b", "khaki": "#8a9a3b",
    "bleu ciel": "#7fd4ff", "bleu marine": "#1b2a8a", "bleu fonce": "#1b2a8a", "bleu clair": "#7fb8ff", "vert fonce": "#0b6b2e",
    "vert clair": "#8dffb0", "rouge fonce": "#a80f0f", "rose fluo": "#ff2dd1", "violette": "#9b4dff", "mauve": "#b36bff",
    "carmin": "#d2042d", "pourpre": "#8a1c7c", "emeraude": "#2dd37a", "emerald": "#2dd37a", "or rose": "#e8a0a0",
}
_HEX_RE = re.compile(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

_ready = False


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFD", text or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9# ]+", " ", t).strip()


def parse_color(text: str) -> tuple[str, str] | None:
    """(#rrggbb, libellé) ou None si rien n'est compris. Accepte un nom (fr/en), #rgb, #rrggbb (le # est facultatif seul)."""
    raw = (text or "").strip()
    if not raw:
        return None
    t = _plain(raw)
    if t in NAMES:
        return NAMES[t], t
    m = re.search(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z])", raw)
    if not m and re.fullmatch(r"[0-9a-fA-F]{6}", raw.replace(" ", "")):
        m = re.match(r"([0-9a-fA-F]{6})", raw.replace(" ", ""))
    if m:
        h = m.group(1).lower()
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "#" + h, "#" + h
    for word in t.split():                      # « bleu ciel », « du rouge s'il vous plait »
        if word in NAMES:
            return NAMES[word], word
    return None


# ── Base de données ──────────────────────────────────────────────────────────

async def _ensure():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("CREATE TABLE IF NOT EXISTS aura_config (id INTEGER PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}')")
        await db.execute("CREATE TABLE IF NOT EXISTS aura_state (id INTEGER PRIMARY KEY, color TEXT NOT NULL DEFAULT '', "
                         "set_by TEXT NOT NULL DEFAULT '', label TEXT NOT NULL DEFAULT '', until_ts DOUBLE PRECISION)")
        await db.execute("INSERT INTO aura_config (id, data) VALUES (1, '{}') ON CONFLICT (id) DO NOTHING")
        await db.execute("INSERT INTO aura_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
    _ready = True


async def get_config() -> dict:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT data FROM aura_config WHERE id = 1")
        row = await c.fetchone()
    try:
        saved = json.loads(row["data"]) if row else {}
    except Exception:
        saved = {}
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({k: v for k, v in saved.items() if k in DEFAULT_CONFIG})
    return cfg


def clean_config(raw: dict, current: dict) -> dict:
    def txt(key, limit):
        return str(raw.get(key, current[key]) or "").strip()[:limit]
    title = txt("reward_title", 45)
    if not title:
        raise ValueError("Le titre de la récompense est obligatoire.")
    color = str(raw.get("color", current["color"]))
    base = str(raw.get("base_color", current["base_color"]))
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color) or not re.fullmatch(r"#[0-9a-fA-F]{6}", base):
        raise ValueError("Couleur invalide.")
    try:
        cost = int(raw.get("cost", current["cost"]))
        cooldown = int(raw.get("cooldown", current["cooldown"]))
        duration = float(raw.get("duration_min", current["duration_min"]))
    except (TypeError, ValueError):
        raise ValueError("Prix, attente et durée doivent être des nombres.")
    if not 1 <= cost <= 10_000_000 or not 0 <= cooldown <= 604800 or not 0 <= duration <= 1440:
        raise ValueError("Valeur hors limites (prix ≥ 1, attente ≤ 7 jours, durée ≤ 24 h).")
    return {"enabled": bool(raw.get("enabled", current["enabled"])), "base_color": base.lower(), "reward_title": title,
            "reward_id": current["reward_id"], "cost": cost, "cooldown": cooldown, "prompt": txt("prompt", 200),
            "color": color, "duration_min": duration, "announce": bool(raw.get("announce", current["announce"])),
            "message_ok": txt("message_ok", 300), "message_bad": txt("message_bad", 300)}


async def save_config(cfg: dict):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("UPDATE aura_config SET data = $1 WHERE id = 1", (json.dumps(cfg, ensure_ascii=False),))


async def get_state() -> dict:
    """Couleur d'aura en vigueur (ou color=None : les overlays gardent leur couleur normale)."""
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT color, set_by, label, until_ts FROM aura_state WHERE id = 1")
        row = await c.fetchone()
    if not row or not row["color"]:
        return {"color": None, "by": "", "label": "", "until": None}
    until = float(row["until_ts"]) if row["until_ts"] is not None else None
    if until is not None and time.time() >= until:
        await reset()
        return {"color": None, "by": "", "label": "", "until": None}
    return {"color": row["color"], "by": row["set_by"], "label": row["label"], "until": until}


async def set_color(color: str, by: str, label: str, duration_min: float):
    await _ensure()
    until = time.time() + duration_min * 60 if duration_min > 0 else None
    async with get_db_connection() as db:
        await db.execute("UPDATE aura_state SET color = $1, set_by = $2, label = $3, until_ts = $4 WHERE id = 1",
                         (color, by, label, until))


async def reset():
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("UPDATE aura_state SET color = '', set_by = '', label = '', until_ts = NULL WHERE id = 1")


# ── Twitch ───────────────────────────────────────────────────────────────────

def _reward_body(cfg: dict, enabled: bool | None = None) -> dict:
    body = {
        "title": cfg["reward_title"], "cost": int(cfg["cost"]), "prompt": cfg["prompt"], "background_color": cfg["color"],
        "is_user_input_required": True,
        "should_redemptions_skip_request_queue": False,      # reste « à traiter » : le bot valide ou rembourse
        "is_global_cooldown_enabled": int(cfg["cooldown"]) > 0, "global_cooldown_seconds": max(1, int(cfg["cooldown"])),
    }
    if enabled is not None:
        body["is_enabled"] = enabled
    return body


async def create_reward() -> dict:
    cfg = await get_config()
    if cfg["reward_id"]:
        return {"ok": True, "message": "La récompense existe déjà."}
    _, _, broadcaster = P._creds()
    status, data = await P._helix("POST", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster},
                                  _reward_body(cfg, enabled=False))
    if status == 200 and data.get("data"):
        cfg["reward_id"] = data["data"][0]["id"]
        await save_config(cfg)
        return {"ok": True, "message": f"Récompense « {cfg['reward_title']} » créée (désactivée : active-la ici ou dans Twitch)."}
    msg = data.get("message") or f"Erreur {status}"
    if "duplicate" in str(data).lower():
        msg = (f"Une récompense « {cfg['reward_title']} » existe déjà dans Twitch (créée à la main) : le bot ne peut pas la piloter. "
               "Renomme-la ou supprime-la, puis réessaie.")
    return {"ok": False, "message": msg}


async def push_config() -> dict:
    cfg = await get_config()
    if not cfg["reward_id"]:
        return {"ok": False, "message": "Pas encore créée sur Twitch."}
    _, _, broadcaster = P._creds()
    status, data = await P._helix("PATCH", "/channel_points/custom_rewards",
                                  {"broadcaster_id": broadcaster, "id": cfg["reward_id"]}, _reward_body(cfg))
    return {"ok": status == 200, "message": "Récompense mise à jour sur Twitch." if status == 200 else (data.get("message") or f"Erreur {status}")}


async def set_reward_enabled(enabled: bool) -> dict:
    cfg = await get_config()
    if not cfg["reward_id"]:
        return {"ok": False, "message": "Pas encore créée sur Twitch."}
    _, _, broadcaster = P._creds()
    status, data = await P._helix("PATCH", "/channel_points/custom_rewards",
                                  {"broadcaster_id": broadcaster, "id": cfg["reward_id"]}, {"is_enabled": enabled})
    return {"ok": status == 200, "message": ("Récompense activée." if enabled else "Récompense désactivée.") if status == 200
            else (data.get("message") or f"Erreur {status}")}


# ── Prise de la récompense (appelé par EventSub) ─────────────────────────────

async def handle_redemption(event: dict) -> bool:
    """True si la récompense est celle de l'aura (traitée ici)."""
    cfg = await get_config()
    if not cfg["enabled"]:
        return False
    reward = event.get("reward") or {}
    rid, title = reward.get("id") or "", (reward.get("title") or "").strip().lower()
    if not ((cfg["reward_id"] and rid == cfg["reward_id"]) or (not cfg["reward_id"] and title == cfg["reward_title"].strip().lower())):
        return False
    user = event.get("user_name") or event.get("user_login") or "Inconnu"
    text = event.get("user_input") or ""
    redemption_id = event.get("id") or ""
    parsed = parse_color(text)
    if not parsed:
        logger.info(f"🎨 [AURA] {user} : couleur non comprise (« {text} ») → remboursé.")
        await P._resolve_redemption(redemption_id, rid, ok=False)
        if cfg["announce"] and cfg["message_bad"]:
            await P._say(cfg["message_bad"].replace("{user}", user).replace("{input}", text.strip()[:40]))
        return True
    color, label = parsed
    await set_color(color, user, label, float(cfg["duration_min"]))
    logger.info(f"🎨 [AURA] {user} met l'aura en {label} ({color}).")
    await P._resolve_redemption(redemption_id, rid, ok=True)
    if cfg["announce"] and cfg["message_ok"]:
        await P._say(cfg["message_ok"].replace("{user}", user).replace("{color}", label if label.startswith("#") else f"{label} ({color})"))
    return True
