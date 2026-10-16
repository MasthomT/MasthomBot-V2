"""Protection des modérateurs : si un modérateur de la liste perd son statut sur Twitch, le bot le lui remet.

Fonctionnement
  - Une liste de « modérateurs protégés » est tenue en base. Elle se remplit toute seule : les modérateurs actuels de
    la chaîne sont ajoutés, et tout nouveau modérateur nommé sur Twitch l'est aussi (réglable).
  - Retrait détecté en direct (EventSub « channel.moderator.remove ») ou par la vérification régulière (toutes les
    10 minutes) : le bot appelle Twitch pour remettre le statut (scope channel:manage:moderators).
  - Pour retirer VOLONTAIREMENT un modérateur, il faut d'abord le sortir de la liste protégée dans l'admin
    (Modération Twitch) — le bouton « Retirer le modo » le fait dans le bon ordre, sinon le bot le remettrait.
"""
import asyncio
import json
import logging
import time

from app.core.database import get_db_connection
from app.services import podium_service as P

logger = logging.getLogger("masthbot.modguard")

DEFAULT_CONFIG = {
    "enabled": True,          # remettre automatiquement le statut perdu
    "auto_protect": True,     # protéger automatiquement les nouveaux modérateurs nommés sur Twitch
    "announce": False,        # message dans le t'chat quand un modo est remis
    "message": "🛡️ @{user} retrouve son statut de modérateur.",
}

_ready = False
_lock = asyncio.Lock()
_last_restore: dict[str, float] = {}     # twitch_id -> instant, évite de marteler Twitch


async def _ensure():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS mod_guard (
            twitch_id TEXT PRIMARY KEY, username TEXT NOT NULL DEFAULT '',
            protected BOOLEAN NOT NULL DEFAULT TRUE, source TEXT NOT NULL DEFAULT 'auto',
            added_at TIMESTAMP NOT NULL DEFAULT NOW())""")
        await db.execute("""CREATE TABLE IF NOT EXISTS mod_guard_log (
            id SERIAL PRIMARY KEY, ts TIMESTAMP NOT NULL DEFAULT NOW(), username TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '')""")
        await db.execute("CREATE TABLE IF NOT EXISTS mod_guard_config (id INTEGER PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}')")
        await db.execute("INSERT INTO mod_guard_config (id, data) VALUES (1, '{}') ON CONFLICT (id) DO NOTHING")
    _ready = True


async def get_config() -> dict:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT data FROM mod_guard_config WHERE id = 1")
        row = await c.fetchone()
    try:
        saved = json.loads(row["data"]) if row else {}
    except Exception:
        saved = {}
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({k: v for k, v in saved.items() if k in DEFAULT_CONFIG})
    return cfg


async def save_config(raw: dict) -> dict:
    cur = await get_config()
    cfg = {"enabled": bool(raw.get("enabled", cur["enabled"])), "auto_protect": bool(raw.get("auto_protect", cur["auto_protect"])),
           "announce": bool(raw.get("announce", cur["announce"])),
           "message": str(raw.get("message", cur["message"]) or "").strip()[:300]}
    async with get_db_connection() as db:
        await db.execute("UPDATE mod_guard_config SET data = $1 WHERE id = 1", (json.dumps(cfg, ensure_ascii=False),))
    return cfg


async def _log(username: str, action: str, detail: str = ""):
    try:
        async with get_db_connection() as db:
            await db.execute("INSERT INTO mod_guard_log (username, action, detail) VALUES ($1, $2, $3)", (username, action, detail[:300]))
            await db.execute("DELETE FROM mod_guard_log WHERE id NOT IN (SELECT id FROM mod_guard_log ORDER BY id DESC LIMIT 60)")
    except Exception as e:
        logger.error(f"❌ [MODGUARD] Journal : {e}")


async def get_roster() -> list[dict]:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT twitch_id, username, protected, source, added_at FROM mod_guard ORDER BY LOWER(username)")
        rows = [dict(r) for r in await c.fetchall()]
        c = await db.execute("SELECT twitch_id FROM viewers WHERE is_mod = 1")
        is_mod = {str(r["twitch_id"]) for r in await c.fetchall()}
    for r in rows:
        r["added_at"] = r["added_at"].strftime("%d/%m/%Y %H:%M") if r.get("added_at") else ""
        r["is_mod_db"] = r["twitch_id"] in is_mod
    return rows


async def get_log(limit: int = 15) -> list[dict]:
    await _ensure()
    async with get_db_connection() as db:
        c = await db.execute("SELECT ts, username, action, detail FROM mod_guard_log ORDER BY id DESC LIMIT $1", (limit,))
        rows = [dict(r) for r in await c.fetchall()]
    for r in rows:
        r["ts"] = r["ts"].strftime("%d/%m %H:%M") if r.get("ts") else ""
    return rows


# ── Twitch ───────────────────────────────────────────────────────────────────

async def fetch_current_mods() -> dict[str, str] | None:
    """{twitch_id: login} des modérateurs actuels ; None si Twitch ne répond pas correctement (on ne touche alors à rien)."""
    _, _, broadcaster = P._creds()
    out, cursor = {}, ""
    for _ in range(30):
        params = {"broadcaster_id": broadcaster, "first": "100"}
        if cursor:
            params["after"] = cursor
        status, data = await P._helix("GET", "/moderation/moderators", params)
        if status != 200:
            logger.warning(f"⚠️ [MODGUARD] Liste des modérateurs indisponible ({status} {data.get('message', '')}).")
            return None
        for m in data.get("data", []):
            out[str(m["user_id"])] = m.get("user_login") or m.get("user_name") or ""
        cursor = (data.get("pagination") or {}).get("cursor")
        if not cursor:
            return out
    return out


async def _add_on_twitch(twitch_id: str) -> tuple[bool, str]:
    _, _, broadcaster = P._creds()
    status, data = await P._helix("POST", "/moderation/moderators", {"broadcaster_id": broadcaster, "user_id": twitch_id})
    if status in (200, 204):
        return True, "ok"
    msg = (data.get("message") or "").strip()
    if status == 400 and "already" in msg.lower():
        return True, "déjà modérateur"
    if status == 400 and "vip" in msg.lower():
        return False, "c'est un VIP : Twitch refuse de le passer modo tant qu'il est VIP"
    return False, f"Twitch {status} : {msg or 'erreur'}"


async def restore(twitch_id: str, username: str, reason: str) -> bool:
    now = time.time()
    if now - _last_restore.get(twitch_id, 0) < 20:         # une tentative toutes les 20 s au maximum
        return False
    _last_restore[twitch_id] = now
    ok, detail = await _add_on_twitch(twitch_id)
    if ok:
        async with get_db_connection() as db:
            await db.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = $1", (twitch_id,))
        logger.info(f"🛡️ [MODGUARD] {username} a retrouvé son statut de modérateur ({reason}).")
        await _log(username, "remis", reason)
        cfg = await get_config()
        if cfg["announce"] and cfg["message"]:
            await P._say(cfg["message"].replace("{user}", username))
    else:
        logger.error(f"❌ [MODGUARD] Impossible de remettre {username} modérateur : {detail}")
        await _log(username, "échec", detail)
    return ok


# ── Vérifications ────────────────────────────────────────────────────────────

async def reconcile(reason: str = "vérification") -> dict:
    """Compare la liste protégée aux modérateurs réels : remet les absents, protège les nouveaux (si réglé)."""
    await _ensure()
    cfg = await get_config()
    async with _lock:
        current = await fetch_current_mods()
        if current is None:
            return {"ok": False, "message": "Twitch ne répond pas : rien modifié."}
        roster = await get_roster()
        known = {r["twitch_id"] for r in roster}
        restored, added = [], []
        if cfg["enabled"]:
            for r in roster:
                if r["protected"] and r["twitch_id"] not in current:
                    if await restore(r["twitch_id"], r["username"], reason):
                        restored.append(r["username"])
        if cfg["auto_protect"] or not roster:
            async with get_db_connection() as db:
                for tid, login in current.items():
                    if tid not in known:
                        await db.execute("INSERT INTO mod_guard (twitch_id, username, protected, source) VALUES ($1, $2, TRUE, 'auto') "
                                         "ON CONFLICT (twitch_id) DO NOTHING", (tid, login))
                        added.append(login)
            for login in added:
                await _log(login, "protégé", "modérateur actuel ajouté à la liste")
        return {"ok": True, "restored": restored, "added": added,
                "message": f"{len(restored)} remis, {len(added)} ajouté(s) à la protection."}


async def on_moderator_removed(event: dict):
    """EventSub channel.moderator.remove : remet tout de suite le statut si le modo est protégé."""
    await _ensure()
    cfg = await get_config()
    if not cfg["enabled"]:
        return
    tid = str(event.get("user_id") or "")
    name = event.get("user_login") or event.get("user_name") or tid
    async with get_db_connection() as db:
        c = await db.execute("SELECT protected FROM mod_guard WHERE twitch_id = $1", (tid,))
        row = await c.fetchone()
    if not row or not row["protected"]:
        await _log(name, "retiré", "non protégé : laissé tel quel")
        async with get_db_connection() as db:
            await db.execute("UPDATE viewers SET is_mod = 0 WHERE twitch_id = $1", (tid,))
        return
    await _log(name, "perdu", "statut retiré sur Twitch")
    await asyncio.sleep(2)                                  # laisse Twitch finir son propre retrait
    await restore(tid, name, "retrait détecté")


async def on_moderator_added(event: dict):
    """EventSub channel.moderator.add : un nouveau modérateur est protégé automatiquement (si réglé)."""
    await _ensure()
    cfg = await get_config()
    tid = str(event.get("user_id") or "")
    name = event.get("user_login") or event.get("user_name") or tid
    async with get_db_connection() as db:
        await db.execute("UPDATE viewers SET is_mod = 1 WHERE twitch_id = $1", (tid,))
        if not cfg["auto_protect"]:
            return
        c = await db.execute("SELECT 1 FROM mod_guard WHERE twitch_id = $1", (tid,))
        if await c.fetchone():
            return
        await db.execute("INSERT INTO mod_guard (twitch_id, username, protected, source) VALUES ($1, $2, TRUE, 'auto')", (tid, name))
    await _log(name, "protégé", "nouveau modérateur")


# ── Actions de l'admin ───────────────────────────────────────────────────────

async def set_protected(twitch_id: str, protected: bool):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("UPDATE mod_guard SET protected = $1 WHERE twitch_id = $2", (protected, twitch_id))
    await _log(twitch_id, "protégé" if protected else "non protégé", "réglé dans l'admin")


async def demote(twitch_id: str) -> dict:
    """Retrait voulu : on sort d'abord de la liste protégée, puis on retire le statut sur Twitch."""
    await _ensure()
    _, _, broadcaster = P._creds()
    async with get_db_connection() as db:
        c = await db.execute("SELECT username FROM mod_guard WHERE twitch_id = $1", (twitch_id,))
        row = await c.fetchone()
        await db.execute("UPDATE mod_guard SET protected = FALSE WHERE twitch_id = $1", (twitch_id,))
    name = row["username"] if row else twitch_id
    status, data = await P._helix("DELETE", "/moderation/moderators", {"broadcaster_id": broadcaster, "user_id": twitch_id})
    if status in (200, 204):
        async with get_db_connection() as db:
            await db.execute("UPDATE viewers SET is_mod = 0 WHERE twitch_id = $1", (twitch_id,))
        await _log(name, "retiré", "retrait voulu depuis l'admin")
        return {"ok": True, "message": f"{name} n'est plus modérateur et n'est plus protégé."}
    return {"ok": False, "message": f"Twitch a refusé : {data.get('message') or status}"}


async def forget(twitch_id: str):
    await _ensure()
    async with get_db_connection() as db:
        await db.execute("DELETE FROM mod_guard WHERE twitch_id = $1", (twitch_id,))
