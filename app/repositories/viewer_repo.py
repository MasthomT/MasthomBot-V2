import logging
from typing import Optional, List
from app.models.viewer import ViewerCreate, ViewerUpdate, ViewerResponse
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.repo")

# ==========================================================
# ⚙️ MOTEUR D'INJECTION DE NIVEAU
# ==========================================================
def _inject_level(viewer_dict):
    """Fonction centrale : Calcule et greffe le niveau nativement partout."""
    if not viewer_dict:
        return None
    # FIX: asyncpg renvoie des "Records" immuables, on les force en dict
    if not isinstance(viewer_dict, dict):
        viewer_dict = dict(viewer_dict)
        
    xp = viewer_dict.get('points', 0)
    viewer_dict['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
    return viewer_dict
# ==========================================================

async def init_tables() -> None:
    """S'assure que les tables d'historique existent au démarrage."""
    try:
        async with get_db_connection() as db:
            # Table principale
            await db.execute('''
                CREATE TABLE IF NOT EXISTS viewers (
                    twitch_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    nickname TEXT,
                    messages INTEGER DEFAULT 0,
                    watchtime INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0,
                    last_seen TIMESTAMP DEFAULT NOW()
                )
            ''')

            colonnes_manquantes = [
                ("is_vip", "INTEGER DEFAULT 0"),
                ("vip_expiry_date", "TIMESTAMP"),
                ("roast_level", "INTEGER DEFAULT 0")
            ]
            for col_name, col_type in colonnes_manquantes:
                try:
                    await db.execute(f"ALTER TABLE viewers ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                except Exception:
                    pass

            await db.execute('''
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    message TEXT NOT NULL,
                    interval INTEGER DEFAULT 15,
                    is_active INTEGER DEFAULT 1
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS viewer_daily_stats (
                    id SERIAL PRIMARY KEY,
                    twitch_id TEXT,
                    day DATE DEFAULT CURRENT_DATE,
                    messages INTEGER DEFAULT 0,
                    watchtime INTEGER DEFAULT 0,
                    points_gained INTEGER DEFAULT 0,
                    UNIQUE(twitch_id, day)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS viewer_exp_log (
                    id SERIAL PRIMARY KEY,
                    twitch_id TEXT,
                    event_type TEXT,
                    amount INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            ''')
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur init_tables : {e}")

# Compteurs additifs fusionnés lorsqu'un compte "streamerbot_<pseudo>" (import Streamer.bot)
# rejoint le vrai compte Twitch du même viewer.
_ADDITIVE_COLS = [
    "messages", "watchtime", "points", "gifts_count", "emotes_count", "bits_count",
    "first_count", "deuz_count", "troiz_count", "emotes_global", "commands_global",
    "gamble_won", "ai_prompts", "bombs_won", "bombs_lost", "rewards_claimed",
    "words_guessed", "poll_votes_count", "questions_asked_count",
    "games_rank_s_count", "games_rank_a_count", "games_rank_b_count", "games_rank_c_count",
]

# Évite de refaire la vérification à chaque message d'un même viewer.
_legacy_checked: set[str] = set()


async def _merge_legacy_into(db, twitch_id: str, legacy_id: str) -> None:
    """Fusionne la ligne héritée `legacy_id` dans le vrai compte `twitch_id`.

    Sans ça, deux lignes partagent le même pseudo et `update_viewer_stats` (avant correction)
    créditait messages/XP à l'une des deux au hasard, coupant les stats d'un viewer en deux.
    """
    real = await db.execute("SELECT 1 FROM viewers WHERE twitch_id = $1", twitch_id)
    if not await real.fetchone():
        # Le vrai compte n'existe pas encore : on rebaptise simplement la ligne héritée.
        await db.execute("UPDATE viewers SET twitch_id = $1 WHERE twitch_id = $2", twitch_id, legacy_id)
    else:
        sums = ", ".join(f"{c} = COALESCE(r.{c}, 0) + COALESCE(l.{c}, 0)" for c in _ADDITIVE_COLS)
        # Un seul ordre SQL (DELETE ... RETURNING + UPDATE) : atomique, pas de double comptage
        # possible si le bot s'arrête en plein milieu.
        await db.execute(f"""
            WITH l AS (DELETE FROM viewers WHERE twitch_id = $2 RETURNING *)
            UPDATE viewers r SET {sums},
                sub_months = GREATEST(COALESCE(r.sub_months, 0), COALESCE(l.sub_months, 0))
            FROM l WHERE r.twitch_id = $1
        """, twitch_id, legacy_id)

    await _merge_legacy_daily(db, twitch_id, legacy_id)
    await db.execute("UPDATE viewer_exp_log SET twitch_id = $1 WHERE twitch_id = $2", twitch_id, legacy_id)
    logger.info(f"🔗 [MERGE] Compte hérité {legacy_id} fusionné dans {twitch_id}.")


async def _merge_legacy_daily(db, twitch_id: str, legacy_id: str) -> None:
    """Historique quotidien : (twitch_id, day) est unique, donc on additionne les jours en commun."""
    await db.execute("""
        INSERT INTO viewer_daily_stats (twitch_id, day, messages, watchtime, points_gained)
        SELECT $1, day, messages, watchtime, points_gained FROM viewer_daily_stats WHERE twitch_id = $2
        ON CONFLICT (twitch_id, day) DO UPDATE SET
            messages = viewer_daily_stats.messages + EXCLUDED.messages,
            watchtime = viewer_daily_stats.watchtime + EXCLUDED.watchtime,
            points_gained = viewer_daily_stats.points_gained + EXCLUDED.points_gained
    """, twitch_id, legacy_id)
    await db.execute("DELETE FROM viewer_daily_stats WHERE twitch_id = $1", legacy_id)


async def merge_all_legacy_viewers() -> int:
    """Fusionne tous les comptes `streamerbot_*` qui ont un vrai compte Twitch de même pseudo.
    Retourne le nombre de comptes fusionnés (utilisé par le script de nettoyage ponctuel)."""
    merged = 0
    async with get_db_connection() as db:
        cur = await db.execute("""
            SELECT l.twitch_id AS legacy_id, r.twitch_id AS real_id
            FROM viewers l JOIN viewers r ON LOWER(r.username) = LOWER(l.username)
            WHERE l.twitch_id LIKE 'streamerbot\\_%' AND r.twitch_id NOT LIKE 'streamerbot\\_%'
        """)
        for row in await cur.fetchall():
            await _merge_legacy_into(db, row["real_id"], row["legacy_id"])
            merged += 1

        # Jours orphelins : la ligne `viewers` héritée n'existe plus (fusion partielle ancienne)
        # mais ses stats quotidiennes traînent encore sous l'ancien identifiant.
        cur = await db.execute("""
            SELECT DISTINCT d.twitch_id AS legacy_id, r.twitch_id AS real_id
            FROM viewer_daily_stats d
            JOIN viewers r ON LOWER(r.username) = SUBSTRING(d.twitch_id FROM 13)
            WHERE d.twitch_id LIKE 'streamerbot\\_%'
              AND NOT EXISTS (SELECT 1 FROM viewers l WHERE l.twitch_id = d.twitch_id)
        """)
        for row in await cur.fetchall():
            await _merge_legacy_daily(db, row["real_id"], row["legacy_id"])
            merged += 1
    return merged


async def ensure_viewer(twitch_id: str, username: str) -> None:
    try:
        async with get_db_connection() as db:
            if twitch_id not in _legacy_checked:
                _legacy_checked.add(twitch_id)
                legacy_id = f"streamerbot_{username.lower()}"
                cur = await db.execute("SELECT 1 FROM viewers WHERE twitch_id = $1", legacy_id)
                if await cur.fetchone():
                    await _merge_legacy_into(db, twitch_id, legacy_id)
            # ✅ CORRECT : pas de parenthèses autour des variables, 
            # elles sont envoyées séparément.
            await db.execute("""
                INSERT INTO viewers (twitch_id, username, points, messages, watchtime)
                VALUES ($1, $2, 0, 0, 0)
                ON CONFLICT(twitch_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    last_seen = NOW()
            """, twitch_id, username) 
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur ensure_viewer : {e}")

async def get_viewer_by_name(username: str) -> Optional[ViewerResponse]:
    try:
        async with get_db_connection() as db:
            c = await db.execute("SELECT * FROM viewers WHERE LOWER(username) = LOWER($1)", (username,))
            row = await c.fetchone()
            if row:
                data = _inject_level(dict(row))
                try:
                    return ViewerResponse(**data)
                except Exception as e:
                    return data
            return None
    except Exception as e:
        return None

async def get_all_viewers():
    try:
        async with get_db_connection() as db:
            c = await db.execute("SELECT * FROM viewers ORDER BY points DESC, watchtime DESC")
            rows = await c.fetchall()
            return [_inject_level(dict(row)) for row in rows]
    except Exception as e:
        return []

async def create_viewer(viewer: ViewerCreate) -> Optional[ViewerResponse]:
    try:
        async with get_db_connection() as db:
            msgs = getattr(viewer, "messages", getattr(viewer, "message_count", 0))
            await db.execute("""
                INSERT INTO viewers (
                    twitch_id, username, nickname, watchtime, messages, points
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """, viewer.twitch_id, viewer.username, viewer.nickname, viewer.watchtime, msgs, viewer.points)
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur create_viewer : {e}")
    return await get_viewer(viewer.twitch_id)

async def update_viewer_stats(username: str, messages_add: int = 0, watchtime_add: int = 0, points_add: int = 0,
                              twitch_id: Optional[str] = None) -> bool:
    try:
        async with get_db_connection() as db:
            if twitch_id:
                # Identité fiable : on ne passe plus par le pseudo (deux lignes pouvaient le partager).
                row = {"twitch_id": twitch_id}
            else:
                # Repli par pseudo, insensible à la casse, en préférant le vrai compte Twitch
                # aux comptes hérités "streamerbot_*".
                cursor = await db.execute(
                    "SELECT twitch_id FROM viewers WHERE LOWER(username) = LOWER($1) "
                    "ORDER BY (twitch_id LIKE 'streamerbot\\_%') ASC LIMIT 1", (username,))
                row = await cursor.fetchone()

            if row:
                t_id = row['twitch_id']
                
                # ✅ CORRECTION 1 : Parenthèses autour des 4 variables
                await db.execute("""
                    UPDATE viewers
                    SET messages = messages + $1, watchtime = watchtime + $2, points = points + $3, last_seen = NOW()
                    WHERE twitch_id = $4
                """, (messages_add, watchtime_add, points_add, t_id))

                # ✅ CORRECTION 2 : Parenthèses autour des 4 variables
                await db.execute("""
                    INSERT INTO viewer_daily_stats (twitch_id, day, messages, watchtime, points_gained)
                    VALUES ($1, CURRENT_DATE, $2, $3, $4)
                    ON CONFLICT(twitch_id, day) DO UPDATE SET
                        messages = viewer_daily_stats.messages + EXCLUDED.messages,
                        watchtime = viewer_daily_stats.watchtime + EXCLUDED.watchtime,
                        points_gained = viewer_daily_stats.points_gained + EXCLUDED.points_gained
                """, (t_id, messages_add, watchtime_add, points_add))
                
                return True
        return False
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur update_viewer_stats : {e}")
        return False

async def add_experience(twitch_id: str, username: str, amount: int, event_type: str = "event", details: str = "") -> None:
    try:
        async with get_db_connection() as db:
            await db.execute("""
                INSERT INTO viewers (twitch_id, username, points) VALUES ($1, $2, $3)
                ON CONFLICT(twitch_id) DO UPDATE SET
                    points = viewers.points + EXCLUDED.points,
                    username = EXCLUDED.username
            """, twitch_id, username, amount)

            await db.execute("""
                INSERT INTO viewer_exp_log (twitch_id, event_type, amount, details)
                VALUES ($1, $2, $3, $4)
            """, twitch_id, event_type, amount, details)

            logger.info(f"📈 [EXP] {username} (+{amount}) via {event_type}")
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur add_experience : {e}")

async def update_viewer(twitch_id: str, update_data: ViewerUpdate) -> Optional[ViewerResponse]:
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict: return await get_viewer(twitch_id)

    safe_dict = {}
    for k, v in update_dict.items():
        if k == "message_count": safe_dict["messages"] = v
        elif k in ["is_vip", "vip_expiry_date", "roast_level"]: continue
        else: safe_dict[k] = v

    if not safe_dict: return await get_viewer(twitch_id)

    set_clauses = [f"{key} = ${i+1}" for i, key in enumerate(safe_dict.keys())]
    values = list(safe_dict.values())
    values.append(twitch_id)

    query = f"UPDATE viewers SET {', '.join(set_clauses)} WHERE twitch_id = ${len(values)}"

    try:
        async with get_db_connection() as db:
            await db.execute(query, *values)
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur update_viewer Pydantic : {e}")

    return await get_viewer(twitch_id)

async def update_viewer_profile(twitch_id: str, **kwargs):
    if not kwargs: return

    set_clauses = [f"{key} = ${i+1}" for i, key in enumerate(kwargs.keys())]
    values = list(kwargs.values())
    values.append(twitch_id)

    query = f"UPDATE viewers SET {', '.join(set_clauses)} WHERE twitch_id = ${len(values)}"

    try:
        async with get_db_connection() as db:
            await db.execute(query, *values)
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur update_viewer_profile : {e}")

async def increment_stats(twitch_id: str, watchtime_add: int = 0, messages_add: int = 0) -> None:
    try:
        async with get_db_connection() as db:
            await db.execute("""
                UPDATE viewers
                SET watchtime = watchtime + $1,
                    messages = messages + $2
                WHERE twitch_id = $3
            """, watchtime_add, messages_add, twitch_id)
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur increment_stats : {e}")

async def get_viewer(twitch_id: str):
    try:
        async with get_db_connection() as db:
            c = await db.execute("SELECT * FROM viewers WHERE twitch_id = $1", (twitch_id,))
            row = await c.fetchone()
            if row:
                return _inject_level(dict(row))
            return None
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur get_viewer : {e}")
        return None

async def get_daily_activity(twitch_id: str):
    try:
        async with get_db_connection() as db:
            c = await db.execute("""
                SELECT day as date, messages, watchtime, points_gained as xp 
                FROM viewer_daily_stats 
                WHERE twitch_id = $1 
                ORDER BY day DESC 
                LIMIT 30
            """, twitch_id)  # <-- La parenthèse finale est bien là !
            rows = await c.fetchall()
            
            results = []
            for r in rows:
                d = dict(r)
                if d.get('date') and hasattr(d['date'], 'isoformat'):
                    d['date'] = d['date'].isoformat()
                elif d.get('date'):
                    d['date'] = str(d['date'])
                results.append(d)
            return results
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur get_daily_activity : {e}")
        return []

async def get_exp_events(twitch_id: str):
    try:
        async with get_db_connection() as db:
            c = await db.execute("""
                SELECT event_type as type, details, amount, timestamp as date 
                FROM viewer_exp_log 
                WHERE twitch_id = $1 
                ORDER BY timestamp DESC 
                LIMIT 20
            """, twitch_id)  # <-- La parenthèse finale est bien là !
            rows = await c.fetchall()
            
            results = []
            for r in rows:
                d = dict(r)
                if d.get('date') and hasattr(d['date'], 'isoformat'):
                    d['date'] = d['date'].isoformat()
                elif d.get('date'):
                    d['date'] = str(d['date'])
                results.append(d)
            return results
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur get_exp_events : {e}")
        return []
