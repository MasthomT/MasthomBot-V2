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

async def ensure_viewer(twitch_id: str, username: str) -> None:
    try:
        async with get_db_connection() as db:
            await db.execute("""
                INSERT INTO viewers (twitch_id, username, points, messages, watchtime)
                VALUES ($1, $2, 0, 0, 0)
                ON CONFLICT(twitch_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    last_seen = NOW()
            """, (twitch_id, username)) # 👈 REGARDE BIEN ICI : J'ai ajouté ( ) autour des variables
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur ensure_viewer : {e}")

async def get_viewer(twitch_id: str) -> Optional[ViewerResponse]:
    try:
        async with get_db_connection() as db:
            row = await db.fetchrow("SELECT * FROM viewers WHERE twitch_id = $1", twitch_id)
            if row:
                data = _inject_level(dict(row))
                try:
                    return ViewerResponse(**data)
                except Exception as e:
                    return data
            return None
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur get_viewer : {e}")
        return None

async def get_viewer_by_name(username: str) -> Optional[ViewerResponse]:
    try:
        async with get_db_connection() as db:
            row = await db.fetchrow("SELECT * FROM viewers WHERE LOWER(username) = LOWER($1)", username)
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
            rows = await db.fetch("SELECT * FROM viewers ORDER BY points DESC, watchtime DESC")
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

async def update_viewer_stats(username: str, messages_add: int = 0, watchtime_add: int = 0, points_add: int = 0) -> bool:
    try:
        async with get_db_connection() as db:
            cursor = await db.execute("SELECT * FROM viewers WHERE username = $1", (username,))
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
