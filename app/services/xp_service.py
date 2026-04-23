import aiosqlite
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
                is_vip BOOLEAN DEFAULT 0,
                vip_expiry_date TIMESTAMP,
                roast_level INTEGER DEFAULT 0
            )
        """)
        # Sécurité : Si la colonne points manque dans une vieille base, on l'ajoute
        try:
            await db.execute("ALTER TABLE viewers ADD COLUMN points INTEGER DEFAULT 0")
        except:
            pass
            
        await db.commit()

async def get_viewer(twitch_id: str) -> Optional[ViewerResponse]:
    async with get_db_connection() as db:
        async with db.execute(
            "SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return ViewerResponse(**dict(row))
            return None

async def get_viewer_by_name(username: str) -> Optional[ViewerResponse]:
    async with get_db_connection() as db:
        async with db.execute(
            "SELECT * FROM viewers WHERE LOWER(username) = LOWER(?)", (username,)
        ) as cursor:
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            viewer.twitch_id, viewer.username, viewer.nickname, viewer.watchtime,
            viewer.message_count, viewer.points, viewer.is_vip, viewer.vip_expiry_date, viewer.roast_level
        ))
        await db.commit()
    return await get_viewer(viewer.twitch_id)

async def update_viewer_stats(username: str, messages_add: int = 0, watchtime_add: int = 0) -> bool:
    async with get_db_connection() as db:
        username = username.lower()
        async with db.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = ?", (username,)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute("""
                    UPDATE viewers 
                    SET message_count = message_count + ?, 
                        watchtime = watchtime + ? 
                    WHERE LOWER(username) = ?
                """, (messages_add, watchtime_add, username))
                await db.commit()
                return True
            return False

async def increment_stats(twitch_id: str, watchtime_add: int = 0, messages_add: int = 0) -> None:
    async with get_db_connection() as db:
        await db.execute("""
            UPDATE viewers
            SET watchtime = watchtime + ?,
                message_count = message_count + ?
            WHERE twitch_id = ?
        """, (watchtime_add, messages_add, twitch_id))
        await db.commit()

async def update_viewer(twitch_id: str, update_data: ViewerUpdate) -> Optional[ViewerResponse]:
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return await get_viewer(twitch_id)

    set_clause = ", ".join([f"{key} = ?" for key in update_dict.keys()])
    values = list(update_dict.values())
    values.append(twitch_id)

    async with get_db_connection() as db:
        await db.execute(f"UPDATE viewers SET {set_clause} WHERE twitch_id = ?", values)
        await db.commit()
    return await get_viewer(twitch_id)

async def get_all_viewers() -> List[ViewerResponse]:
    async with get_db_connection() as db:
        async with db.execute("SELECT * FROM viewers ORDER BY watchtime DESC") as cursor:
            rows = await cursor.fetchall()
            return [ViewerResponse(**dict(row)) for row in rows]

# =====================================================================
# 🌟 NOUVEAU : SYSTÈME D'EXPÉRIENCE
# =====================================================================
async def add_experience(twitch_id: str, username: str, amount: int) -> None:
    """Ajoute de l'EXP (points) au viewer, ou le crée s'il n'existe pas encore."""
    async with get_db_connection() as db:
        async with db.execute("SELECT twitch_id FROM viewers WHERE twitch_id = ?", (twitch_id,)) as cursor:
            row = await cursor.fetchone()
        
        if row:
            await db.execute("UPDATE viewers SET points = points + ?, username = ? WHERE twitch_id = ?", (amount, username, twitch_id))
        else:
            await db.execute("INSERT INTO viewers (twitch_id, username, points) VALUES (?, ?, ?)", (twitch_id, username, amount))
        await db.commit()
