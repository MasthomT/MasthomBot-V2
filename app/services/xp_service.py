import logging
from typing import Optional, List
from app.models.viewer import ViewerCreate, ViewerUpdate, ViewerResponse
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.repo")

async def init_tables() -> None:
    """Crée la table au démarrage si elle n'existe pas."""
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS viewers (
                twitch_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                nickname TEXT,
                watchtime INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0,
                vip_expiry_date TIMESTAMP,
                roast_level INTEGER DEFAULT 0
            )
        """)
        # Sécurité : Si la colonne points manque, on l'ajoute (Syntaxe PostgreSQL propre)
        try:
            await db.execute("ALTER TABLE viewers ADD COLUMN IF NOT EXISTS points INTEGER DEFAULT 0")
        except:
            pass

async def get_viewer(twitch_id: str) -> Optional[ViewerResponse]:
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT * FROM viewers WHERE twitch_id = $1", (twitch_id,))
        row = await cursor.fetchone()
        if row:
            return ViewerResponse(**dict(row))
        return None

async def get_viewer_by_name(username: str) -> Optional[ViewerResponse]:
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT * FROM viewers WHERE LOWER(username) = LOWER($1)", (username,))
        row = await cursor.fetchone()
        if row:
            return ViewerResponse(**dict(row))
        return None

async def create_viewer(viewer: ViewerCreate) -> ViewerResponse:
    async with get_db_connection() as db:
        await db.execute("""
            INSERT INTO viewers (
                twitch_id, username, nickname, watchtime, message_count,
                points, is_vip, vip_expiry_date, roast_level
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, (
            viewer.twitch_id, viewer.username, viewer.nickname, viewer.watchtime,
            viewer.message_count, viewer.points, viewer.is_vip, viewer.vip_expiry_date, viewer.roast_level
        ))
    return await get_viewer(viewer.twitch_id)

async def update_viewer_stats(username: str, messages_add: int = 0, watchtime_add: int = 0) -> bool:
    async with get_db_connection() as db:
        username = username.lower()
        cursor = await db.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = $1", (username,))
        row = await cursor.fetchone()
        if row:
            await db.execute("""
                UPDATE viewers 
                SET message_count = message_count + $1, 
                    watchtime = watchtime + $2 
                WHERE LOWER(username) = $3
            """, (messages_add, watchtime_add, username))
            return True
        return False

async def increment_stats(twitch_id: str, watchtime_add: int = 0, messages_add: int = 0) -> None:
    async with get_db_connection() as db:
        await db.execute("""
            UPDATE viewers
            SET watchtime = watchtime + $1,
                message_count = message_count + $2
            WHERE twitch_id = $3
        """, (watchtime_add, messages_add, twitch_id))

async def update_viewer(twitch_id: str, update_data: ViewerUpdate) -> Optional[ViewerResponse]:
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return await get_viewer(twitch_id)

    set_clause = ", ".join([f"{key} = ${i+1}" for i, key in enumerate(update_dict.keys())])
    values = list(update_dict.values())
    values.append(twitch_id)

    async with get_db_connection() as db:
        await db.execute(f"UPDATE viewers SET {set_clause} WHERE twitch_id = ${len(values)}", tuple(values))
    return await get_viewer(twitch_id)

async def get_all_viewers() -> List[ViewerResponse]:
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT * FROM viewers ORDER BY watchtime DESC")
        rows = await cursor.fetchall()
        return [ViewerResponse(**dict(row)) for row in rows]

async def add_experience(twitch_id: str, username: str, amount: int) -> None:
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT twitch_id FROM viewers WHERE twitch_id = $1", (twitch_id,))
        row = await cursor.fetchone()
        
        if row:
            await db.execute("UPDATE viewers SET points = points + $1, username = $2 WHERE twitch_id = $3", (amount, username, twitch_id))
        else:
            await db.execute("INSERT INTO viewers (twitch_id, username, points) VALUES ($1, $2, $3)", (twitch_id, username, amount))
