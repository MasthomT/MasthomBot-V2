"""
app/services/wheel_service.py — Roues de la fortune configurables, déclenchables à la demande.

Plusieurs roues indépendantes peuvent exister en même temps (chacune avec son propre overlay
OBS via /overlay/wheel/{id}) — utile pour avoir par exemple une roue "jeux" et une roue "défis"
distinctes, lancées séparément depuis l'admin.

Le tirage est calculé côté serveur (random.choices, pondéré si des poids sont définis) puis
diffusé à l'overlay concerné via SSE — l'overlay se contente d'animer jusqu'au résultat déjà
décidé, il ne tire jamais lui-même (évite toute incohérence si plusieurs overlays/onglets sont
ouverts en même temps).
"""

import json
import logging
import random

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.wheel")


async def init_wheel_tables() -> None:
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wheels (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL,
                items_json  TEXT NOT NULL DEFAULT '[]',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def _parse_items(items_json: str) -> list[dict]:
    try:
        items = json.loads(items_json or "[]")
        return items if isinstance(items, list) else []
    except Exception:
        return []


async def get_all_wheels() -> list[dict]:
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM wheels ORDER BY id ASC")
        rows = await db.fetchall()
    wheels = []
    for r in rows:
        w = dict(r)
        w["items"] = _parse_items(w.pop("items_json"))
        wheels.append(w)
    return wheels


async def get_wheel(wheel_id: int) -> dict | None:
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM wheels WHERE id = ?", wheel_id)
        row = await db.fetchone()
    if not row:
        return None
    w = dict(row)
    w["items"] = _parse_items(w.pop("items_json"))
    return w


async def create_wheel(name: str, items: list[dict]) -> int:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "INSERT INTO wheels (name, items_json) VALUES (?, ?) RETURNING id",
            name.strip() or "Roue sans nom", json.dumps(items)
        )
        row = await cursor.fetchone()
    return row["id"]


async def update_wheel(wheel_id: int, name: str, items: list[dict]) -> None:
    async with get_db_connection() as db:
        await db.execute(
            "UPDATE wheels SET name = ?, items_json = ? WHERE id = ?",
            name.strip() or "Roue sans nom", json.dumps(items), wheel_id
        )


async def delete_wheel(wheel_id: int) -> None:
    async with get_db_connection() as db:
        await db.execute("DELETE FROM wheels WHERE id = ?", wheel_id)


def pick_winner(items: list[dict]) -> int:
    """Tire un index gagnant parmi les segments. Respecte un champ 'weight' optionnel par
    segment (défaut 1, donc équiprobable si aucun poids n'est défini)."""
    weights = [max(float(it.get("weight") or 1), 0.01) for it in items]
    return random.choices(range(len(items)), weights=weights, k=1)[0]
