"""
Récompenses de points de chaîne « podium » : First -> Deuz -> Troiz, gérées par le bot (plus de Streamer.bot).

Principe : trois récompenses distinctes (titre, prix, image propres) créées par le bot. Une seule est
activée à la fois : quand un viewer prend la récompense en cours, elle est désactivée et la suivante
s'active. Au début du live on repart de First, à la fin tout est désactivé.

Limites de Twitch à connaître :
  - une récompense ne peut être modifiée que par l'application qui l'a créée : les récompenses créées
    par Streamer.bot (ou à la main) ne sont PAS pilotables par le bot, il faut donc créer les trois ici ;
  - l'API ne permet pas de mettre une image : elle se règle une fois pour toutes dans le tableau de bord Twitch.
"""
import asyncio
import json
import logging
import os

import aiohttp
import dotenv

from app.core.config import settings
from app.core.database import get_db_connection
from app.core import settings_cache

logger = logging.getLogger("masthbot.podium")

POSITIONS = (1, 2, 3)
COLUMN_BY_POSITION = {1: "first_count", 2: "deuz_count", 3: "troiz_count"}
ENV_PATH = "/home/thomas/masthom/BOT_V2/.env"

DEFAULTS = {
    1: dict(title="First", cost=1, prompt="Sois le premier du stream !", color="#FFD700", user_input=True,
            win_message="🥇 @{user} prend la place de FIRST du stream ! GG !"),
    2: dict(title="Deuz", cost=1, prompt="Deuxième place du podium !", color="#C0C0C0", user_input=True,
            win_message="🥈 @{user} s'empare du DEUZ ! Il reste le TROIZ !"),
    3: dict(title="Troiz", cost=1, prompt="Dernière place du podium !", color="#CD7F32", user_input=True,
            win_message="🥉 @{user} termine le podium avec le TROIZ ! Podium complet !"),
}
RESET_MESSAGE_DEFAULT = ""  # rien à annoncer par défaut au début du live

_lock = asyncio.Lock()
_ready = False


# ── Base de données ──────────────────────────────────────────────────────────

async def ensure_tables():
    global _ready
    if _ready:
        return
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS podium_rewards (
                position    INTEGER PRIMARY KEY,
                title       TEXT NOT NULL,
                cost        INTEGER NOT NULL DEFAULT 1,
                prompt      TEXT NOT NULL DEFAULT '',
                color       TEXT NOT NULL DEFAULT '#9146FF',
                user_input  BOOLEAN NOT NULL DEFAULT FALSE,
                win_message TEXT NOT NULL DEFAULT '',
                reward_id   TEXT NOT NULL DEFAULT ''
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS podium_state (
                id      INTEGER PRIMARY KEY,
                live_id TEXT NOT NULL DEFAULT '',
                stage   INTEGER NOT NULL DEFAULT 0,
                winners TEXT NOT NULL DEFAULT '{}'
            )
        """)
        for pos, d in DEFAULTS.items():
            await db.execute(
                """INSERT INTO podium_rewards (position, title, cost, prompt, color, user_input, win_message)
                   VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (position) DO NOTHING""",
                (pos, d["title"], d["cost"], d["prompt"], d["color"], d["user_input"], d["win_message"]),
            )
        await db.execute("INSERT INTO podium_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
    _ready = True


async def get_config() -> list[dict]:
    await ensure_tables()
    async with get_db_connection() as db:
        c = await db.execute("SELECT * FROM podium_rewards ORDER BY position")
        return [dict(r) for r in await c.fetchall()]


async def get_state() -> dict:
    await ensure_tables()
    async with get_db_connection() as db:
        c = await db.execute("SELECT live_id, stage, winners FROM podium_state WHERE id = 1")
        r = dict(await c.fetchone())
    try:
        r["winners"] = json.loads(r["winners"] or "{}")
    except Exception:
        r["winners"] = {}
    return r


async def _save_state(live_id: str, stage: int, winners: dict):
    async with get_db_connection() as db:
        await db.execute(
            "UPDATE podium_state SET live_id = $1, stage = $2, winners = $3 WHERE id = 1",
            (live_id, stage, json.dumps(winners, ensure_ascii=False)),
        )


async def _current_live_id() -> str:
    return await settings_cache.current_live_id()


# ── API Twitch ───────────────────────────────────────────────────────────────

def _creds() -> tuple[str, str, str]:
    env = dotenv.dotenv_values(ENV_PATH)
    client_id = (env.get("TWITCH_CLIENT_ID") or "").strip().strip("'\"")
    token = (env.get("TWITCH_OAUTH_TOKEN") or "").strip().strip("'\"").replace("oauth:", "")
    broadcaster = (env.get("TWITCH_BROADCASTER_ID") or "").strip().strip("'\"")
    return client_id, token, broadcaster


async def _helix(method: str, path: str, params: dict | None = None, body: dict | None = None) -> tuple[int, dict]:
    client_id, token, _ = _creds()
    headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        async with s.request(method, f"https://api.twitch.tv/helix{path}", params=params, json=body, headers=headers) as r:
            try:
                data = await r.json()
            except Exception:
                data = {}
            return r.status, data


def _reward_body(cfg: dict, enabled: bool | None = None) -> dict:
    body = {
        "title": cfg["title"],
        "cost": int(cfg["cost"]),
        "prompt": cfg["prompt"] or "",
        "background_color": cfg["color"],
        "is_user_input_required": bool(cfg["user_input"]),
        "is_max_per_stream_enabled": True,   # une seule prise par stream : Twitch tranche les égalités
        "max_per_stream": 1,
        "should_redemptions_skip_request_queue": False,  # reste « à traiter » : le bot valide ou rembourse
    }
    if enabled is not None:
        body["is_enabled"] = enabled
    return body


async def create_rewards() -> dict:
    """Crée sur Twitch les récompenses qui n'existent pas encore (désactivées). Renvoie un rapport par position."""
    cfgs = await get_config()
    _, _, broadcaster = _creds()
    report = {}
    for cfg in cfgs:
        if cfg["reward_id"]:
            report[cfg["position"]] = {"ok": True, "message": "Déjà créée."}
            continue
        status, data = await _helix("POST", "/channel_points/custom_rewards", {"broadcaster_id": broadcaster},
                                    _reward_body(cfg, enabled=False))
        if status == 200 and data.get("data"):
            rid = data["data"][0]["id"]
            async with get_db_connection() as db:
                await db.execute("UPDATE podium_rewards SET reward_id = $1 WHERE position = $2", (rid, cfg["position"]))
            report[cfg["position"]] = {"ok": True, "message": f"Créée (« {cfg['title']} »)."}
        else:
            msg = data.get("message") or f"Erreur {status}"
            if "DUPLICATE" in (data.get("message") or "").upper() or "duplicate" in str(data).lower():
                msg = (f"Une récompense « {cfg['title']} » existe déjà (créée par Streamer.bot ou à la main) : "
                       f"renomme-la ou supprime-la dans Twitch, puis réessaie.")
            report[cfg["position"]] = {"ok": False, "message": msg}
    return report


async def push_config_to_twitch() -> dict:
    """Répercute titre / prix / texte / couleur sur les récompenses déjà créées."""
    cfgs = await get_config()
    _, _, broadcaster = _creds()
    report = {}
    for cfg in cfgs:
        if not cfg["reward_id"]:
            continue
        status, data = await _helix("PATCH", "/channel_points/custom_rewards",
                                    {"broadcaster_id": broadcaster, "id": cfg["reward_id"]}, _reward_body(cfg))
        report[cfg["position"]] = {"ok": status == 200, "message": "Mise à jour." if status == 200 else (data.get("message") or f"Erreur {status}")}
    return report


async def _set_stage_on_twitch(stage: int):
    """stage 1..3 : seule la récompense de cette position est active. 0 ou 4 : tout est désactivé."""
    _, _, broadcaster = _creds()
    for cfg in await get_config():
        if not cfg["reward_id"]:
            continue
        status, data = await _helix(
            "PATCH", "/channel_points/custom_rewards",
            {"broadcaster_id": broadcaster, "id": cfg["reward_id"]},
            {"is_enabled": cfg["position"] == stage},
        )
        if status != 200:
            logger.error(f"❌ [PODIUM] Impossible de régler « {cfg['title']} » : {status} {data.get('message')}")


async def _resolve_redemption(redemption_id: str, reward_id: str, ok: bool):
    _, _, broadcaster = _creds()
    status, data = await _helix(
        "PATCH", "/channel_points/custom_rewards/redemptions",
        {"id": redemption_id, "broadcaster_id": broadcaster, "reward_id": reward_id},
        {"status": "FULFILLED" if ok else "CANCELED"},
    )
    if status != 200:
        logger.warning(f"⚠️ [PODIUM] Validation de la récompense impossible : {status} {data.get('message')}")


async def _say(message: str):
    if not message:
        return
    try:
        from app.services.twitch_service import twitch_bot
        channel = twitch_bot.get_channel(settings.TWITCH_CHANNEL.replace("#", "").lower())
        if channel:
            await channel.send(message)
    except Exception as e:
        logger.error(f"❌ [PODIUM] Message chat impossible : {e}")


# ── Cycle du live ────────────────────────────────────────────────────────────

async def on_stream_start(live_id: str):
    """Nouveau live : on repart de First (sans effet si ce live est déjà en cours de suivi)."""
    async with _lock:
        state = await get_state()
        if state["live_id"] == live_id and state["stage"] != 0:
            return
        cfgs = await get_config()
        if not any(c["reward_id"] for c in cfgs):
            await _save_state(live_id, 1, {})
            return
        await _save_state(live_id, 1, {})
        await _set_stage_on_twitch(1)
        logger.info("🏁 [PODIUM] Nouveau live : First est actif.")


async def on_stream_end():
    async with _lock:
        state = await get_state()
        await _save_state(state["live_id"], 0, state["winners"])
        if any(c["reward_id"] for c in await get_config()):
            await _set_stage_on_twitch(0)
            logger.info("🏁 [PODIUM] Fin du live : récompenses désactivées.")


async def manual_set_stage(stage: int):
    """Depuis l'admin : forcer l'étape (1..3) ou tout éteindre (0). Le podium des gagnants est remis à zéro au passage à 1."""
    async with _lock:
        state = await get_state()
        winners = {} if stage == 1 else state["winners"]
        await _save_state(state["live_id"] or await _current_live_id(), stage, winners)
        await _set_stage_on_twitch(stage)


# ── Prise d'une récompense (appelé par EventSub) ─────────────────────────────

async def handle_redemption(event: dict) -> bool:
    """True si la récompense appartient au podium (traitée ici), False sinon."""
    reward = event.get("reward") or {}
    reward_id = reward.get("id")
    if not reward_id:
        return False
    cfgs = await get_config()
    cfg = next((c for c in cfgs if c["reward_id"] == reward_id), None)
    if not cfg:
        return False

    user_id = str(event.get("user_id") or "")
    user_name = event.get("user_name") or event.get("user_login") or "Inconnu"
    redemption_id = event.get("id") or ""
    position = cfg["position"]

    async with _lock:
        live_id = await _current_live_id()
        state = await get_state()
        if live_id and state["live_id"] != live_id:
            # live démarré alors que le bot n'était pas là : on repart proprement
            state = {"live_id": live_id, "stage": 1, "winners": {}}

        already = any(w.get("id") == user_id for w in state["winners"].values())
        if state["stage"] != position or already:
            reason = "déjà une place sur le podium" if already else "cette place n'est plus disponible"
            logger.info(f"⛔ [PODIUM] {user_name} : {reason} → remboursé.")
            await _resolve_redemption(redemption_id, reward_id, ok=False)
            return True

        # Place attribuée
        column = COLUMN_BY_POSITION[position]
        async with get_db_connection() as db:
            await db.execute(
                f"""INSERT INTO viewers (twitch_id, username, points, messages, watchtime, {column})
                    VALUES ($1, $2, 0, 0, 0, 1)
                    ON CONFLICT (twitch_id) DO UPDATE
                    SET username = EXCLUDED.username, {column} = COALESCE(viewers.{column}, 0) + 1""",
                (user_id, user_name),
            )
        winners = dict(state["winners"])
        winners[str(position)] = {"id": user_id, "name": user_name}
        next_stage = position + 1 if position < 3 else 4
        await _save_state(live_id or state["live_id"], next_stage, winners)
        await _set_stage_on_twitch(next_stage if next_stage <= 3 else 0)
        logger.info(f"🏆 [PODIUM] {user_name} prend {cfg['title']} (étape suivante : {next_stage}).")

    await _resolve_redemption(redemption_id, reward_id, ok=True)
    msg = (cfg["win_message"] or "").replace("{user}", user_name).replace("{title}", cfg["title"])
    await _say(msg)
    return True
