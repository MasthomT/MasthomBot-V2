"""Clonage des récompenses de points de chaîne pour que le bot puisse les gérer.

Twitch ne laisse une application modifier que les récompenses qu'elle a créées elle-même. Pour reprendre la main
sur une récompense créée dans le tableau de bord, le bot en fait une copie, en trois temps :
  1. clone()    : copie créée par le bot, désactivée, sous un nom provisoire (les titres doivent être uniques) ;
  2. l'utilisateur supprime l'original dans le tableau de bord Twitch (l'API ne peut pas y toucher) ;
  3. finalize() : la copie reprend le vrai nom et l'état (active / en pause) de l'original.
L'image personnalisée ne peut pas être recopiée (l'API n'accepte pas d'image) et l'identifiant change :
la correspondance ancien → nouveau est gardée ici, et `same()` sert partout où le bot repère une récompense par son id.
"""
import json
import logging

from app.core.database import get_db_connection
from app.services import podium_service as P

logger = logging.getLogger("masthbot.reward_clone")

TEMP_SUFFIX = " ⧉"
_ready = False
_alias: dict[str, str] = {}          # id d'origine -> id de la copie (clonages finalisés)


async def _ensure():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS reward_clones (
            orig_id TEXT PRIMARY KEY, clone_id TEXT NOT NULL, title TEXT NOT NULL, orig TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', created_at TIMESTAMP NOT NULL DEFAULT NOW(), done_at TIMESTAMP)""")
    _ready = True


async def load_aliases():
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT orig_id, clone_id FROM reward_clones WHERE status = 'done'")
        rows = await c.fetchall()
    _alias.clear()
    _alias.update({r["orig_id"]: r["clone_id"] for r in rows})


def same(reward_id: str | None, original_id: str) -> bool:
    """Vrai si `reward_id` est la récompense `original_id`, ou sa copie faite par le bot."""
    return bool(reward_id) and (reward_id == original_id or reward_id == _alias.get(original_id))


def resolve(mapping: dict) -> dict:
    """Ajoute à un dictionnaire {id d'origine: valeur} les ids des copies."""
    out = dict(mapping)
    for old, new in _alias.items():
        if old in mapping:
            out[new] = mapping[old]
    return out


async def pending() -> dict[str, dict]:
    """Clonages en cours : {id d'origine: {clone_id, title}}."""
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT orig_id, clone_id, title FROM reward_clones WHERE status = 'pending'")
        return {r["orig_id"]: {"clone_id": r["clone_id"], "title": r["title"]} for r in await c.fetchall()}


async def _get(reward_id: str, manageable: bool = False) -> dict | None:
    _, _, broadcaster = P._creds()
    params = {"broadcaster_id": broadcaster, "id": reward_id}
    if manageable:
        params["only_manageable_rewards"] = "true"
    status, data = await P._helix("GET", "/channel_points/custom_rewards", params)
    rows = (data.get("data") or []) if status == 200 else []
    return rows[0] if rows else None


def _copy_body(r: dict, title: str, enabled: bool) -> dict:
    ms = r.get("max_per_stream_setting") or {}
    mu = r.get("max_per_user_per_stream_setting") or {}
    cd = r.get("global_cooldown_setting") or {}
    body = {
        "title": title[:45],
        "cost": int(r.get("cost") or 1),
        "prompt": r.get("prompt") or "",
        "is_enabled": enabled,
        "is_user_input_required": bool(r.get("is_user_input_required")),
        "should_redemptions_skip_request_queue": bool(r.get("should_redemptions_skip_request_queue")),
        "is_max_per_stream_enabled": bool(ms.get("is_enabled")),
        "is_max_per_user_per_stream_enabled": bool(mu.get("is_enabled")),
        "is_global_cooldown_enabled": bool(cd.get("is_enabled")),
    }
    if r.get("background_color"):
        body["background_color"] = r["background_color"]
    if ms.get("is_enabled"):
        body["max_per_stream"] = int(ms.get("max_per_stream") or 1)
    if mu.get("is_enabled"):
        body["max_per_user_per_stream"] = int(mu.get("max_per_user_per_stream") or 1)
    if cd.get("is_enabled"):
        body["global_cooldown_seconds"] = int(cd.get("global_cooldown_seconds") or 1)
    return body


async def clone(orig_id: str) -> dict:
    await _ensure()
    if orig_id in await pending():
        raise ValueError("Une copie est déjà prête pour cette récompense : supprime l'original sur Twitch puis clique « Finaliser ».")
    r = await _get(orig_id)
    if not r:
        raise ValueError("Récompense introuvable sur Twitch.")
    if await _get(orig_id, manageable=True):
        raise ValueError("Cette récompense est déjà gérée par le bot.")
    temp = (r["title"][:45 - len(TEMP_SUFFIX)] + TEMP_SUFFIX)
    _, _, broadcaster = P._creds()
    status, data = await P._helix("POST", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster},
                                  _copy_body(r, temp, enabled=False))
    if status != 200 or not data.get("data"):
        raise ValueError("Twitch a refusé la copie : " + (data.get("message") or f"erreur {status}"))
    new = data["data"][0]
    async with get_db_connection() as db:
        await db.execute("INSERT INTO reward_clones (orig_id, clone_id, title, orig) VALUES ($1, $2, $3, $4)",
                         (orig_id, new["id"], r["title"], json.dumps(r, ensure_ascii=False)))
    logger.info(f"🎁 [REWARDS] Copie créée pour « {r['title']} » ({new['id']})")
    return {"clone_id": new["id"], "title": r["title"]}


async def finalize(orig_id: str) -> dict:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT clone_id, title, orig FROM reward_clones WHERE orig_id = $1 AND status = 'pending'", (orig_id,))
        row = await c.fetchone()
    if not row:
        raise ValueError("Aucun clonage en cours pour cette récompense.")
    if await _get(orig_id):
        raise ValueError(f"L'original « {row['title']} » existe encore sur Twitch : supprime-le d'abord dans le tableau de bord, puis reclique.")
    orig = json.loads(row["orig"])
    _, _, broadcaster = P._creds()
    body = {"title": row["title"][:45], "is_enabled": bool(orig.get("is_enabled")), "is_paused": bool(orig.get("is_paused"))}
    status, data = await P._helix("PATCH", "/channel_points/custom_rewards",
                                  {"broadcaster_id": broadcaster, "id": row["clone_id"]}, body)
    if status != 200:
        raise ValueError("Twitch a refusé de renommer la copie : " + (data.get("message") or f"erreur {status}"))
    async with get_db_connection() as db:
        await db.execute("UPDATE reward_clones SET status = 'done', done_at = NOW() WHERE orig_id = $1", (orig_id,))
    _alias[orig_id] = row["clone_id"]
    logger.info(f"🎁 [REWARDS] « {row['title']} » est maintenant gérée par le bot ({row['clone_id']})")
    return {"clone_id": row["clone_id"], "title": row["title"]}


async def cancel(orig_id: str) -> dict:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT clone_id, title FROM reward_clones WHERE orig_id = $1 AND status = 'pending'", (orig_id,))
        row = await c.fetchone()
    if not row:
        raise ValueError("Aucun clonage en cours pour cette récompense.")
    _, _, broadcaster = P._creds()
    status, data = await P._helix("DELETE", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster, "id": row["clone_id"]})
    if status not in (200, 204, 404):
        raise ValueError("Twitch a refusé de supprimer la copie : " + (data.get("message") or f"erreur {status}"))
    async with get_db_connection() as db:
        await db.execute("DELETE FROM reward_clones WHERE orig_id = $1", (orig_id,))
    return {"title": row["title"]}


# ── Modification d'une récompense gérée par le bot ───────────────────────────

def clean_edit(raw: dict) -> dict:
    title = str(raw.get("title") or "").strip()
    if not 1 <= len(title) <= 45:
        raise ValueError("Le titre doit faire entre 1 et 45 caractères.")
    try:
        cost = int(raw.get("cost"))
        mps = int(raw.get("max_per_stream") or 0)
        mpu = int(raw.get("max_per_user") or 0)
        cd = int(raw.get("cooldown") or 0)
    except (TypeError, ValueError):
        raise ValueError("Prix, limites et attente doivent être des nombres entiers.")
    if cost < 1:
        raise ValueError("Le prix doit être d'au moins 1 point.")
    if mps < 0 or mpu < 0 or not 0 <= cd <= 604800:
        raise ValueError("Limites hors bornes (attente max 7 jours).")
    color = str(raw.get("color") or "").strip()
    body = {
        "title": title, "cost": cost, "prompt": str(raw.get("prompt") or "")[:200],
        "is_enabled": bool(raw.get("enabled")), "is_paused": bool(raw.get("paused")),
        "is_user_input_required": bool(raw.get("user_input")),
        "is_max_per_stream_enabled": mps > 0, "is_max_per_user_per_stream_enabled": mpu > 0,
        "is_global_cooldown_enabled": cd > 0,
    }
    if mps > 0:
        body["max_per_stream"] = mps
    if mpu > 0:
        body["max_per_user_per_stream"] = mpu
    if cd > 0:
        body["global_cooldown_seconds"] = cd
    if color:
        if len(color) != 7 or not color.startswith("#"):
            raise ValueError("Couleur invalide (format #rrggbb).")
        body["background_color"] = color
    return body


async def edit(reward_id: str, raw: dict) -> dict:
    body = clean_edit(raw)
    _, _, broadcaster = P._creds()
    status, data = await P._helix("PATCH", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster, "id": reward_id}, body)
    if status != 200:
        raise ValueError("Twitch a refusé la modification : " + (data.get("message") or f"erreur {status}"))
    return data["data"][0]


async def create(raw: dict) -> dict:
    """Nouvelle récompense créée par le bot (donc modifiable ici ensuite)."""
    body = clean_edit(raw)
    body.pop("is_paused", None)                       # pas accepté à la création
    _, _, broadcaster = P._creds()
    status, data = await P._helix("POST", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster}, body)
    if status != 200 or not data.get("data"):
        msg = data.get("message") or f"erreur {status}"
        if "DUPLICATE" in msg.upper():
            msg = "une récompense porte déjà ce titre"
        raise ValueError("Twitch a refusé la création : " + msg)
    logger.info(f"🎁 [REWARDS] Récompense créée : « {body['title']} » ({data['data'][0]['id']})")
    return data["data"][0]


async def delete(reward_id: str) -> None:
    """Supprime une récompense créée par le bot (Twitch refuse pour les autres)."""
    _, _, broadcaster = P._creds()
    status, data = await P._helix("DELETE", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster, "id": reward_id})
    if status not in (200, 204):
        raise ValueError("Twitch a refusé la suppression : " + (data.get("message") or f"erreur {status}"))
    logger.info(f"🎁 [REWARDS] Récompense supprimée ({reward_id})")
