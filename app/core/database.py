import os
import dotenv
import asyncpg
import re
import logging
import asyncio
import random
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger("masthbot.database")

env_vars = dotenv.dotenv_values(".env")
DATABASE_URL = env_vars.get("DATABASE_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL est introuvable dans le fichier .env !")

write_queue: Optional[asyncio.Queue] = None

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

def get_write_queue() -> asyncio.Queue:
    global write_queue
    if write_queue is None:
        write_queue = asyncio.Queue()
    return write_queue


class PostgresCursorWrapper:
    """
    Le traducteur magique final : 
    Mémorise correctement la requête pour ne plus perdre les paramètres du bot.
    """
    def __init__(self, conn, sql=None, params=()):
        self.conn = conn
        self.sql = sql
        self.params = params
        self._results = []
        self._iter = None

    def execute(self, sql: str, *params):
        # Si on reçoit un tuple unique (ex: (a, b, c)), on le déballe
        if len(params) == 1 and isinstance(params[0], (tuple, list)):
            self.params = params[0]
        else:
            self.params = params
        self.sql = sql
        return self

    async def __aenter__(self):
        await self._do_execute()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __await__(self):
        return self._do_execute().__await__()

    async def _do_execute(self):
        if not self.sql: return self
            
        upper_sql = self.sql.upper()
        
        if "PRAGMA" in upper_sql:
            self._results = []
            self._iter = iter(self._results)
            return self

        count = 0
        def replace(match):
            nonlocal count
            count += 1
            return f"${count}"
        fixed_sql = re.sub(r'\?', replace, self.sql)

        fixed_sql = fixed_sql.replace("datetime('now', 'localtime')", "NOW()")
        fixed_sql = fixed_sql.replace("datetime('now')", "NOW()")
        fixed_sql = fixed_sql.replace("date('now', 'localtime')", "CURRENT_DATE")
        fixed_sql = fixed_sql.replace("date('now')", "CURRENT_DATE")

        fixed_sql = re.sub(r'(?i)INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'SERIAL PRIMARY KEY', fixed_sql)

        if "VIEWER_DAILY_STATS" in fixed_sql.upper():
            fixed_sql = re.sub(r'=\s*messages\s*\+\s*excluded\.messages', '= viewer_daily_stats.messages + excluded.messages', fixed_sql, flags=re.IGNORECASE)
            fixed_sql = re.sub(r'=\s*watchtime\s*\+\s*excluded\.watchtime', '= viewer_daily_stats.watchtime + excluded.watchtime', fixed_sql, flags=re.IGNORECASE)
            fixed_sql = re.sub(r'=\s*points_gained\s*\+\s*excluded\.points_gained', '= viewer_daily_stats.points_gained + excluded.points_gained', fixed_sql, flags=re.IGNORECASE)
        if "INSERT INTO VIEWERS" in fixed_sql.upper() and "ON CONFLICT" in fixed_sql.upper():
            # Force la table devant 'points' pour lever l'ambiguïté Postgres
            fixed_sql = re.sub(r'points\s*=\s*points\s*\+\s*excluded\.points', 'points = viewers.points + excluded.points', fixed_sql, flags=re.IGNORECASE)

        upper_fixed = self.sql.upper()
        # Ici, on utilise *self.params pour envoyer les arguments proprement à asyncpg
        first_word = upper_fixed.lstrip().split()[0] if upper_fixed.strip() else ""
        if first_word in ["INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"]:
            await self.conn.execute(fixed_sql, *self.params)
            self._results = []
        else:
            self._results = await self.conn.fetch(fixed_sql, *self.params)
        
        self._iter = iter(self._results)
        return self

    async def commit(self):
        pass

    async def fetchall(self):
        return self._results

    async def fetchone(self):
        if self._iter:
            try:
                return next(self._iter)
            except StopIteration:
                return None
        return None


async def db_writer_worker(db_path: str):
    logger.info("🛠️ [SINGLE WRITER] Bascule de la file d'attente d'écriture sur PostgreSQL.")
    queue = get_write_queue()
    conn = await asyncpg.connect(DATABASE_URL)
    cursor = PostgresCursorWrapper(conn)

    try:
        while True:
            sql = None
            try:
                sql, params = await queue.get()
                if sql is None:
                    queue.task_done()
                    break
                await cursor.execute(sql, params)
                queue.task_done()
            except Exception as e:
                sql_str = sql if sql else "Aucune requête lue"
                logger.error(f"❌ [SINGLE WRITER ERROR] Échec de la requête Postgres : {e} | SQL: {sql_str}")
    finally:
        await conn.close()


async def queue_write(sql: str, params: tuple = ()):
    queue = get_write_queue()
    await queue.put((sql, params))


@asynccontextmanager
async def get_db_connection(max_retries=5, base_delay=0.1):
    conn = None
    for attempt in range(max_retries):
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(f"⚠️ Échec connexion PostgreSQL (Tentative {attempt + 1}/{max_retries}). Réessai dans {delay:.2f}s... (Erreur: {e})")
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ [DB FATAL] Impossible de joindre PostgreSQL après {max_retries} tentatives : {e}")
                raise e

    wrapper = PostgresCursorWrapper(conn)
    try:
        yield wrapper
    finally:
        if conn:
            await conn.close()


async def init_db():
    logger.info("🛠️ [DB INIT] Vérification de la structure sur PostgreSQL...")
    async with get_db_connection() as conn:
        migrations = [
            "ALTER TABLE viewers ADD COLUMN IF NOT EXISTS is_mod INTEGER DEFAULT 0",
            "ALTER TABLE viewers ADD COLUMN IF NOT EXISTS is_artist INTEGER DEFAULT 0",
            "ALTER TABLE announcements ADD COLUMN IF NOT EXISTS last_triggered TIMESTAMP",
            "ALTER TABLE viewer_exp_log ADD COLUMN IF NOT EXISTS twitch_id TEXT",
            "ALTER TABLE viewers ADD COLUMN IF NOT EXISTS vip_expiry TIMESTAMP",
            "ALTER TABLE viewers ADD COLUMN IF NOT EXISTS poll_votes_count INTEGER DEFAULT 0",
            "ALTER TABLE viewers ADD COLUMN IF NOT EXISTS questions_asked_count INTEGER DEFAULT 0",

            # --- NOUVELLE TABLE POUR LE DASHBOARD ADMIN (PAGE INFOS) ---
            """
            CREATE TABLE IF NOT EXISTS channel_info (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                about_text TEXT DEFAULT 'Bienvenue sur la chaîne !',
                social_discord TEXT DEFAULT '',
                social_youtube TEXT DEFAULT '',
                social_twitch TEXT DEFAULT '',
                social_tiktok TEXT DEFAULT '',
                social_tips TEXT DEFAULT '',
                rules_json TEXT DEFAULT '[]',
                schedule_json TEXT DEFAULT '[]'
            )
            """,
            # Postgres: Si la ligne 1 existe déjà, on ne fait rien
            "INSERT INTO channel_info (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
        ]
        for query in migrations:
            try:
                await conn.execute(query)
            except Exception as e:
                logger.error(f"❌ [DB INIT] Erreur de migration PostgreSQL : {e}")
        logger.info("🚀 [DB INIT] Structure PostgreSQL synchronisée et opérationnelle !")
