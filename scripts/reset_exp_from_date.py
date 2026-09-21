"""Remet XP, watchtime et messages des viewers à zéro puis les recalcule depuis une date.

Recalcul par viewer, à partir du `--since` (défaut 2026-08-01) :
  messages  = somme des messages    de viewer_daily_stats
  watchtime = somme du watchtime    de viewer_daily_stats
  points    = somme des points_gained de viewer_daily_stats
              + somme des XP d'événements de viewer_exp_log (subs, subgifts, raids, bits, ajustements admin)
              SANS l'XP des trophées (les trophées débloqués, table viewer_trophies, ne sont pas touchés)
  puis borné à 0 minimum.

Usage (racine du projet, avec le venv) :
    python3 scripts/reset_exp_from_date.py                      # simulation, n'écrit rien
    python3 scripts/reset_exp_from_date.py --apply              # sauvegarde puis écrit
    python3 scripts/reset_exp_from_date.py --restore backups/reset_exp_snapshot_XXXX.json   # remet les anciennes valeurs
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import date, datetime

import asyncpg
import dotenv

EXCLUDED = ("masthou", "felixthebigblackcat", "vestale7", "streamelements", "wizebot", "nightbot")

NEW_VALUES_SQL = """
    SELECT v.twitch_id, v.username,
        v.messages AS old_messages, v.watchtime AS old_watchtime, v.points AS old_points,
        COALESCE((SELECT SUM(messages) FROM viewer_daily_stats d WHERE d.twitch_id = v.twitch_id AND d.day >= $1), 0)::int AS new_messages,
        COALESCE((SELECT SUM(watchtime) FROM viewer_daily_stats d WHERE d.twitch_id = v.twitch_id AND d.day >= $1), 0)::int AS new_watchtime,
        COALESCE((SELECT SUM(points_gained) FROM viewer_daily_stats d WHERE d.twitch_id = v.twitch_id AND d.day >= $1), 0)::bigint AS xp_activity,
        COALESCE((SELECT SUM(amount) FROM viewer_exp_log e WHERE e.twitch_id = v.twitch_id AND e.timestamp >= $2
                  AND UPPER(e.event_type) <> 'TROPHY'), 0)::bigint AS xp_events
    FROM viewers v
"""

UPDATE_SQL = """
    UPDATE viewers v SET
        messages  = COALESCE((SELECT SUM(messages)  FROM viewer_daily_stats d WHERE d.twitch_id = v.twitch_id AND d.day >= $1), 0)::int,
        watchtime = COALESCE((SELECT SUM(watchtime) FROM viewer_daily_stats d WHERE d.twitch_id = v.twitch_id AND d.day >= $1), 0)::int,
        points    = GREATEST(
            COALESCE((SELECT SUM(points_gained) FROM viewer_daily_stats d WHERE d.twitch_id = v.twitch_id AND d.day >= $1), 0)
          + COALESCE((SELECT SUM(amount) FROM viewer_exp_log e WHERE e.twitch_id = v.twitch_id AND e.timestamp >= $2
                      AND UPPER(e.event_type) <> 'TROPHY'), 0), 0)::int
"""


async def main(args):
    env = dotenv.dotenv_values(".env")
    url = env["DATABASE_URL"]
    conn = await asyncpg.connect(url)

    if args.restore:
        with open(args.restore, encoding="utf-8") as f:
            snap = json.load(f)
        await conn.executemany(
            "UPDATE viewers SET messages = $2, watchtime = $3, points = $4 WHERE twitch_id = $1",
            [(r["twitch_id"], r["messages"], r["watchtime"], r["points"]) for r in snap],
        )
        print(f"✅ Valeurs restaurées pour {len(snap)} viewers depuis {args.restore}")
        return

    since_d = date.fromisoformat(args.since)
    since_ts = datetime.combine(since_d, datetime.min.time())
    rows = [dict(r) for r in await conn.fetch(NEW_VALUES_SQL, since_d, since_ts)]
    for r in rows:
        r["new_points"] = max(0, r["xp_activity"] + r["xp_events"])

    shown = [r for r in rows if r["username"].lower() not in EXCLUDED]
    clamped = [r for r in rows if r["xp_activity"] + r["xp_events"] < 0]
    print(f"Recalcul depuis le {since_d} — {len(rows)} viewers en base")
    print(f"  viewers avec XP > 0 : {sum(1 for r in rows if r['old_points'] > 0)} -> {sum(1 for r in rows if r['new_points'] > 0)}")
    print(f"  XP total            : {sum(r['old_points'] for r in rows)} -> {sum(r['new_points'] for r in rows)}")
    print(f"  bornés à 0 (total négatif) : {[(r['username'], r['xp_activity'] + r['xp_events']) for r in clamped]}")
    print(f"\n{'pseudo':<18}{'XP avant':>10}{'XP après':>10}{'h avant':>9}{'h après':>9}{'msgs avant':>11}{'msgs après':>11}")
    for r in sorted(shown, key=lambda x: x["new_points"], reverse=True)[:15]:
        print(f"{r['username']:<18}{r['old_points']:>10}{r['new_points']:>10}{r['old_watchtime']//3600:>9}{r['new_watchtime']//3600:>9}{r['old_messages']:>11}{r['new_messages']:>11}")

    if not args.apply:
        print("\nSimulation uniquement, rien n'a été écrit. Relance avec --apply.")
        return

    os.makedirs("backups", exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%Hh%M%S")
    dump = f"backups/pre_reset_exp_{stamp}.dump"
    subprocess.run(["pg_dump", url, "-Fc", "-f", dump], check=True)   # abandon si la sauvegarde échoue
    snap_path = f"backups/reset_exp_snapshot_{stamp}.json"
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump([{"twitch_id": r["twitch_id"], "messages": r["old_messages"], "watchtime": r["old_watchtime"],
                    "points": r["old_points"]} for r in rows], f)
    print(f"\nSauvegarde complète : {dump}\nInstantané des anciennes valeurs : {snap_path}")

    result = await conn.execute(UPDATE_SQL, since_d, since_ts)
    print(f"✅ {result} — XP, watchtime et messages recalculés depuis le {since_d}.")
    print(f"   Pour annuler : python3 scripts/reset_exp_from_date.py --restore {snap_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--since", default="2026-08-01")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--restore")
    asyncio.run(main(p.parse_args()))
