"""Cache des réglages (tables `settings` et `personality`) + état du live partagé.

Avant, la ligne `settings` était relue en base à chaque message du chat et dans
chaque routine (~440 000 lectures). On la garde maintenant en mémoire :
  - vidée immédiatement quand le bot l'écrit lui-même (admin, live_monitor) via
    `invalidate_settings()` ;
  - relue au plus tard après CACHE_TTL secondes (filet pour une modification faite
    hors du bot, ex. un script).

`is_live()` / `current_live_id()` remplacent les nombreuses requêtes
« SELECT personal_last_live_id FROM settings » éparpillées dans le code.
"""

import logging
import time

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.settings_cache")

CACHE_TTL = 30  # secondes

_cache: dict[str, tuple[dict, float]] = {}


async def _load(table: str) -> dict:
    hit = _cache.get(table)
    now = time.monotonic()
    if hit and hit[1] > now:
        return dict(hit[0])
    async with get_db_connection() as conn:
        cur = await conn.execute(f"SELECT * FROM {table} ORDER BY id LIMIT 1")
        row = await cur.fetchone()
    data = dict(row) if row else {}
    _cache[table] = (data, now + CACHE_TTL)
    return dict(data)


async def get_settings() -> dict:
    """Ligne unique de la table `settings` (copie : la modifier ne touche pas le cache)."""
    return await _load("settings")


async def get_personality() -> dict:
    """Ligne unique de la table `personality` (peut être vide)."""
    return await _load("personality")


def invalidate_settings() -> None:
    """À appeler juste après toute écriture dans `settings` ou `personality`."""
    _cache.clear()


async def current_live_id() -> str:
    """Identifiant du live en cours ('' hors live)."""
    return (await get_settings()).get("personal_last_live_id") or ""


async def is_live() -> bool:
    return bool(await current_live_id())
