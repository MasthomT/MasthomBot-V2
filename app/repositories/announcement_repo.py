import sqlite3
from datetime import datetime

class AnnouncementRepository:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    message_template TEXT NOT NULL,
                    trigger_type TEXT DEFAULT 'interval',
                    interval_minutes INTEGER DEFAULT 30,
                    group_name TEXT,
                    last_sent DATETIME,
                    is_enabled INTEGER DEFAULT 1
                )
            """)
            conn.commit()

    def get_all(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM announcements")
            return [dict(row) for row in cursor.fetchall()]

    def save(self, data):
        with sqlite3.connect(self.db_path) as conn:
            if data.get('id'):
                conn.execute("""
                    UPDATE announcements SET label=?, message_template=?, trigger_type=?, 
                    interval_minutes=?, group_name=? WHERE id=?
                """, (data['label'], data['message_template'], data['trigger_type'], 
                      data['interval_minutes'], data['group_name'], data['id']))
            else:
                conn.execute("""
                    INSERT INTO announcements (label, message_template, trigger_type, interval_minutes, group_name)
                    VALUES (?, ?, ?, ?, ?)
                """, (data['label'], data['message_template'], data['trigger_type'], 
                      data['interval_minutes'], data['group_name']))
            conn.commit()

    def delete(self, ann_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
            conn.commit()

    def update_last_sent(self, ann_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE announcements SET last_sent = ? WHERE id = ?", 
                         (datetime.now(), ann_id))
            conn.commit()
