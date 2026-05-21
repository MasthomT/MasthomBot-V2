from datetime import datetime
from app.core.database import get_db_connection

class AnnouncementRepository:
    def __init__(self):
        pass

    async def init_db(self):
        async with get_db_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    label TEXT NOT NULL,
                    message_template TEXT NOT NULL,
                    trigger_type TEXT DEFAULT 'interval',
                    interval_minutes INTEGER DEFAULT 30,
                    group_name TEXT,
                    last_sent TIMESTAMP,
                    is_enabled INTEGER DEFAULT 1
                )
            """)

    async def get_all(self):
        async with get_db_connection() as conn:
            cursor = await conn.execute("SELECT * FROM announcements")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def save(self, data):
        async with get_db_connection() as conn:
            if data.get('id'):
                await conn.execute("""
                    UPDATE announcements SET label=$1, message_template=$2, trigger_type=$3, 
                    interval_minutes=$4, group_name=$5 WHERE id=$6
                """, (data['label'], data['message_template'], data['trigger_type'], 
                      data['interval_minutes'], data['group_name'], data['id']))
            else:
                await conn.execute("""
                    INSERT INTO announcements (label, message_template, trigger_type, interval_minutes, group_name)
                    VALUES ($1, $2, $3, $4, $5)
                """, (data['label'], data['message_template'], data['trigger_type'], 
                      data['interval_minutes'], data['group_name']))

    async def delete(self, ann_id):
        async with get_db_connection() as conn:
            await conn.execute("DELETE FROM announcements WHERE id = $1", (ann_id,))

    async def update_last_sent(self, ann_id):
        async with get_db_connection() as conn:
            await conn.execute("UPDATE announcements SET last_sent = $1 WHERE id = $2", 
                         (datetime.now(), ann_id))
