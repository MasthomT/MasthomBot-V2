"""Fusionne les comptes hérités `streamerbot_*` dans les vrais comptes Twitch (même pseudo).

Usage (depuis la racine du projet, avec le venv) :
    python3 scripts/merge_legacy_viewers.py           # simulation : affiche ce qui serait fait
    python3 scripts/merge_legacy_viewers.py --apply   # écrit en base (sauvegarde JSON avant)
"""
import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.getcwd())

from app.core.database import get_db_connection  # noqa: E402
from app.repositories import viewer_repo  # noqa: E402


async def snapshot() -> dict:
    async with get_db_connection() as db:
        cur = await db.execute("""
            SELECT v.* FROM viewers v
            WHERE v.twitch_id LIKE 'streamerbot\\_%'
               OR LOWER(v.username) IN (SELECT LOWER(username) FROM viewers WHERE twitch_id LIKE 'streamerbot\\_%')
            ORDER BY LOWER(v.username), v.twitch_id
        """)
        viewers = [dict(r) for r in await cur.fetchall()]
        cur = await db.execute("SELECT * FROM viewer_daily_stats WHERE twitch_id LIKE 'streamerbot\\_%' ORDER BY twitch_id, day")
        daily = [dict(r) for r in await cur.fetchall()]
    return {"viewers": viewers, "daily_stats_legacy": daily}


async def main(apply: bool):
    snap = await snapshot()
    legacy = [v for v in snap["viewers"] if v["twitch_id"].startswith("streamerbot_")]
    print(f"{len(legacy)} compte(s) hérité(s), {len(snap['daily_stats_legacy'])} ligne(s) quotidienne(s) héritée(s) :")
    for v in snap["viewers"]:
        tag = "HÉRITÉ" if v["twitch_id"].startswith("streamerbot_") else "réel  "
        print(f"  [{tag}] {v['username']:<18} id={v['twitch_id']:<28} msgs={v['messages']:<5} xp={v['points']:<6} watchtime={v['watchtime']}s")
    if not apply:
        print("\nSimulation uniquement. Relance avec --apply pour fusionner.")
        return

    os.makedirs("backups", exist_ok=True)
    path = f"backups/merge_legacy_viewers_{datetime.now():%Y-%m-%d_%Hh%M%S}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, default=str, ensure_ascii=False, indent=2)
    print(f"\nSauvegarde des lignes concernées : {path}")

    n = await viewer_repo.merge_all_legacy_viewers()
    print(f"✅ {n} fusion(s) effectuée(s).")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
