import os
import dotenv
import asyncpg
import logging
import asyncio
import random
from contextlib import asynccontextmanager

logger = logging.getLogger("masthbot.database")

env_vars = dotenv.dotenv_values(".env")
DATABASE_URL = env_vars.get("DATABASE_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL est introuvable dans le fichier .env !")

# ── Pool de connexions ────────────────────────────────────────────────────────
# Avant : chaque requête ouvrait puis fermait sa propre connexion PostgreSQL (~33 ms),
# soit des centaines de connexions par minute en live. Le pool garde quelques
# connexions ouvertes et les réutilise (~0,2 ms par requête).
# Un pool par boucle asyncio (le bot n'en a qu'une ; les tests en créent d'autres).
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 20
POOL_ACQUIRE_TIMEOUT = 30          # s : au-delà, erreur explicite plutôt qu'un blocage
POOL_IDLE_LIFETIME = 300           # s : une connexion inutilisée est refermée

_pools: dict[int, asyncpg.Pool] = {}
_pool_locks: dict[int, asyncio.Lock] = {}


async def _create_pool(max_retries=5, base_delay=0.1) -> asyncpg.Pool:
    for attempt in range(max_retries):
        try:
            return await asyncpg.create_pool(
                DATABASE_URL, min_size=POOL_MIN_SIZE, max_size=POOL_MAX_SIZE,
                max_inactive_connection_lifetime=POOL_IDLE_LIFETIME,
            )
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(f"⚠️ Échec connexion PostgreSQL (Tentative {attempt + 1}/{max_retries}). Réessai dans {delay:.2f}s... (Erreur: {e})")
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ [DB FATAL] Impossible de joindre PostgreSQL après {max_retries} tentatives : {e}")
                raise


async def get_pool() -> asyncpg.Pool:
    key = id(asyncio.get_running_loop())
    pool = _pools.get(key)
    if pool is not None and not pool._closed:
        return pool
    lock = _pool_locks.setdefault(key, asyncio.Lock())
    async with lock:
        pool = _pools.get(key)
        if pool is None or pool._closed:
            pool = await _create_pool()
            _pools[key] = pool
            logger.info(f"🗄️ [DB] Pool PostgreSQL prêt ({POOL_MIN_SIZE}–{POOL_MAX_SIZE} connexions).")
    return pool


async def close_db_pool() -> None:
    """À appeler à l'arrêt du bot."""
    pool = _pools.pop(id(asyncio.get_running_loop()), None)
    if pool is not None and not pool._closed:
        await pool.close()


class DBConnection:
    """Connexion empruntée au pool, avec une interface façon « curseur » :

        cur = await conn.execute("SELECT … WHERE id = $1", (id,))
        row = await cur.fetchone()

    Les requêtes partent telles quelles à PostgreSQL (marqueurs $1, $2…). L'ancienne
    couche de traduction SQLite (« ? », datetime('now'), PRAGMA…) a été retirée le
    12/11/2026 : toutes les requêtes du code sont écrites en SQL PostgreSQL.
    """
    _WRITE_VERBS = {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}

    def __init__(self, conn):
        self.conn = conn
        self.sql = None
        self.params = ()
        self._results = []
        self._iter = None

    def execute(self, sql: str, *params):
        # Accepte execute(sql, (a, b)) comme execute(sql, a, b)
        if len(params) == 1 and isinstance(params[0], (tuple, list)):
            params = tuple(params[0])
        self.sql, self.params = sql, params
        return self

    async def __aenter__(self):
        await self._do_execute()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __await__(self):
        return self._do_execute().__await__()

    async def _do_execute(self):
        if not self.sql:
            return self
        upper = self.sql.upper()
        first_word = upper.split(None, 1)[0] if upper.strip() else ""
        # Un INSERT/UPDATE/DELETE … RETURNING doit passer par fetch(), sinon les lignes sont perdues.
        if first_word in self._WRITE_VERBS and "RETURNING" not in upper:
            await self.conn.execute(self.sql, *self.params)
            self._results = []
        else:
            self._results = await self.conn.fetch(self.sql, *self.params)
        self._iter = iter(self._results)
        return self

    async def commit(self):
        """Sans effet (asyncpg valide chaque requête) ; gardé pour compatibilité."""

    async def fetchall(self):
        return self._results

    async def fetchone(self):
        if self._iter:
            return next(self._iter, None)
        return None


@asynccontextmanager
async def get_db_connection():
    """Emprunte une connexion au pool pour la durée du bloc `async with`."""
    pool = await get_pool()
    async with pool.acquire(timeout=POOL_ACQUIRE_TIMEOUT) as conn:
        yield DBConnection(conn)


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
            # Watchtime déjà "consommé" par les crédits de fin de stream : remplace l'ancien reset
            # à 0 de viewer_daily_stats.watchtime, qui détruisait l'historique quotidien.
            "ALTER TABLE viewer_daily_stats ADD COLUMN IF NOT EXISTS watchtime_offset INTEGER DEFAULT 0",
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
