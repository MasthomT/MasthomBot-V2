"""
app/services/subgoal_service.py — Objectif de subs à paliers ("SubGoal"), configurable depuis
l'admin : on définit un nombre de subs (palier) associé à un défi/récompense, et la progression
s'affiche sur l'overlay OBS au fur et à mesure que les subs arrivent (comptés via stream_events,
même source que /api/v1/compteur-defi).
"""

import logging
from datetime import datetime

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.subgoal")

DEFAULT_SINCE = "2026-09-01"


async def init_subgoal_tables() -> None:
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subgoal_tiers (
                id          SERIAL PRIMARY KEY,
                threshold   INTEGER NOT NULL,
                label       TEXT NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subgoal_config (
                id                        INTEGER PRIMARY KEY DEFAULT 1,
                since_date                TEXT NOT NULL DEFAULT '2026-09-01',
                end_date                  TEXT,
                linked_wheel_id           INTEGER,
                last_announced_threshold  INTEGER NOT NULL DEFAULT 0,
                CHECK (id = 1)
            )
        """)
        await db.execute(
            "ALTER TABLE subgoal_config ADD COLUMN IF NOT EXISTS last_announced_threshold INTEGER NOT NULL DEFAULT 0"
        )
        await db.execute("ALTER TABLE subgoal_config ADD COLUMN IF NOT EXISTS end_date TEXT")
        await db.execute("ALTER TABLE subgoal_config ADD COLUMN IF NOT EXISTS linked_wheel_id INTEGER")


async def get_config() -> dict:
    async with get_db_connection() as db:
        await db.execute("SELECT since_date, end_date, linked_wheel_id FROM subgoal_config WHERE id = 1")
        row = await db.fetchone()
    if not row:
        return {"since": DEFAULT_SINCE, "end_date": None, "linked_wheel_id": None}
    return {"since": row["since_date"], "end_date": row["end_date"], "linked_wheel_id": row["linked_wheel_id"]}


async def get_since() -> str:
    return (await get_config())["since"]


async def get_end_date() -> str | None:
    return (await get_config())["end_date"]


async def get_linked_wheel_id() -> int | None:
    return (await get_config())["linked_wheel_id"]


async def set_config(since_date: str, end_date: str | None, linked_wheel_id: int | None) -> None:
    since_date = since_date.strip() or DEFAULT_SINCE
    end_date = (end_date or "").strip() or None

    # On ne remet les annonces à zéro que si la date de départ change vraiment (nouvelle
    # période de comptage) — pas juste parce qu'on retouche la date de fin ou la roue liée.
    current = await get_config()
    last_announced = 0 if since_date != current["since"] else await get_last_announced_threshold()

    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO subgoal_config (id, since_date, end_date, linked_wheel_id, last_announced_threshold) "
            "VALUES (1, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET since_date = EXCLUDED.since_date, end_date = EXCLUDED.end_date, "
            "linked_wheel_id = EXCLUDED.linked_wheel_id, last_announced_threshold = EXCLUDED.last_announced_threshold",
            since_date, end_date, linked_wheel_id, last_announced
        )


async def get_last_announced_threshold() -> int:
    async with get_db_connection() as db:
        await db.execute("SELECT last_announced_threshold FROM subgoal_config WHERE id = 1")
        row = await db.fetchone()
    return row["last_announced_threshold"] if row else 0


async def set_last_announced_threshold(value: int) -> None:
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO subgoal_config (id, last_announced_threshold) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET last_announced_threshold = EXCLUDED.last_announced_threshold",
            value
        )


async def get_all_tiers() -> list[dict]:
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM subgoal_tiers ORDER BY threshold ASC")
        rows = await db.fetchall()
    return [dict(r) for r in rows]


async def create_tier(threshold: int, label: str) -> int:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "INSERT INTO subgoal_tiers (threshold, label) VALUES (?, ?) RETURNING id",
            threshold, label.strip()
        )
        row = await cursor.fetchone()
    return row["id"]


async def update_tier(tier_id: int, threshold: int, label: str) -> None:
    async with get_db_connection() as db:
        await db.execute(
            "UPDATE subgoal_tiers SET threshold = ?, label = ? WHERE id = ?",
            threshold, label.strip(), tier_id
        )


async def delete_tier(tier_id: int) -> None:
    async with get_db_connection() as db:
        await db.execute("DELETE FROM subgoal_tiers WHERE id = ?", tier_id)


async def check_and_announce_new_tiers() -> None:
    """À appeler après chaque sub/subgift comptabilisé : annonce dans le chat chaque palier
    qui vient d'être franchi (dans l'ordre, au cas où plusieurs le soient d'un coup)."""
    try:
        from app.routes.api import get_compteur_defi
        from app.services.twitch_service import twitch_bot
        from app.core.config import settings
        from app.routes.overlays import trigger_overlay_event

        tiers = await get_all_tiers()
        if not tiers:
            return

        since = await get_since()
        counters = await get_compteur_defi(since=since)
        total = counters.get("total_subs", 0)

        last_announced = await get_last_announced_threshold()
        newly_crossed = sorted(
            (t for t in tiers if last_announced < t["threshold"] <= total),
            key=lambda t: t["threshold"]
        )
        if not newly_crossed:
            return

        channel_name = settings.TWITCH_CHANNEL.replace("#", "").lower()
        channel = twitch_bot.get_channel(channel_name)

        for tier in newly_crossed:
            if channel:
                await channel.send(f"🎯 PALIER SUBGOAL DÉBLOQUÉ : {tier['threshold']} subs ! 🎉 {tier['label']}")
            await trigger_overlay_event({
                "type": "subgoal_tier_unlocked",
                "threshold": tier["threshold"],
                "label": tier["label"],
            })
            await set_last_announced_threshold(tier["threshold"])
    except Exception as e:
        logger.error(f"❌ [SUBGOAL] Annonce palier : {e}")


async def announce_new_sub(username: str, kind: str, count: int = 1) -> None:
    """À appeler pour CHAQUE sub/subgift compté (pas seulement les paliers) : pousse une alerte
    sur l'overlay pour donner un retour visuel immédiat et donner envie aux autres viewers de
    participer à leur tour."""
    try:
        from app.routes.overlays import trigger_overlay_event
        await trigger_overlay_event({
            "type": "subgoal_new_sub",
            "username": username,
            "kind": kind,
            "count": count,
        })
    except Exception as e:
        logger.error(f"❌ [SUBGOAL] Alerte nouveau sub : {e}")


async def maybe_spin_linked_wheel() -> None:
    """À appeler après chaque sub/subgift comptabilisé : si une roue est reliée à SubGoal dans
    l'admin, on la lance automatiquement (une fois par événement, pas par sub gifté individuel)."""
    try:
        wheel_id = await get_linked_wheel_id()
        if not wheel_id:
            return
        from app.routes.wheel import spin_wheel
        await spin_wheel(wheel_id)
    except Exception as e:
        logger.error(f"❌ [SUBGOAL] Spin de la roue liée : {e}")


def _days_left_suffix(end_date: str | None) -> str:
    if not end_date:
        return ""
    try:
        end_dt = datetime.fromisoformat(end_date).date()
    except ValueError:
        return ""
    delta = (end_dt - datetime.now().date()).days
    if delta > 0:
        return f" (J-{delta})"
    if delta == 0:
        return " (dernier jour !)"
    return " (terminé)"


SUBTEMBER_EXPLAINER = (
    "🎂 C'est quoi SUBTEMBER ? TOUT le mois de Septembre, profite de -25% sur les subs 1 et 3 mois "
    "(-30% sur 6 mois), c'est le meilleur moment pour s'abonner et soutenir la chaîne ! Pour l'occasion, "
    "à chaque palier de subs atteint, on débloque un défi en direct 🎉 Tape !subgoal pour voir la progression !"
)


async def build_subgoal_chat_reply(mode: str = "roadmap") -> str:
    """Réponse chat : mode "explainer" pour !subtember (explique le principe de l'événement),
    mode "roadmap" pour !subgoal (statut succinct : où on en est, prochain défi). Pousse en
    parallèle une carte temporaire sur l'overlay — la commande ne doit pas rester un simple
    message de chat, elle doit donner une raison de regarder l'écran."""
    from app.routes.overlays import trigger_overlay_event

    if mode == "explainer":
        config = await get_config()
        await trigger_overlay_event({
            "type": "subgoal_command", "mode": "explainer",
            "text": SUBTEMBER_EXPLAINER, "end_date": config["end_date"],
        })
        return SUBTEMBER_EXPLAINER

    from app.routes.api import get_compteur_defi

    tiers = await get_all_tiers()
    if not tiers:
        return "🎯 SubGoal : aucun palier n'est configuré pour le moment."

    config = await get_config()
    counters = await get_compteur_defi(since=config["since"])
    total = counters.get("total_subs", 0)
    suffix = _days_left_suffix(config["end_date"])
    last_tier = tiers[-1]

    next_tier = next((t for t in tiers if t["threshold"] > total), None)
    if next_tier is None:
        text = f"🎉 SubGoal{suffix} : tous les paliers débloqués, {total} subs au total — merci à vous !"
        await trigger_overlay_event({"type": "subgoal_command", "mode": "roadmap", "total": total, "completed": True})
        return text

    remaining = next_tier["threshold"] - total
    remaining_unit = "sub" if remaining == 1 else "subs"
    text = f"🎯 SubGoal{suffix} : {total}/{next_tier['threshold']} subs → {next_tier['label']} (encore {remaining} {remaining_unit})"

    idx = tiers.index(next_tier)
    slim = lambda t: {"threshold": t["threshold"], "label": t["label"]}
    await trigger_overlay_event({
        "type": "subgoal_command", "mode": "roadmap", "total": total,
        "next": slim(next_tier), "upcoming": [slim(t) for t in tiers[idx:idx + 3]], "final": last_tier["threshold"],
    })
    return text
