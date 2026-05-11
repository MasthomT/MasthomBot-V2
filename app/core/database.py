import aiosqlite
import logging
import asyncio
import random
from contextlib import asynccontextmanager

logger = logging.getLogger("masthbot.database")

from typing import Optional
# LE CHEMIN ABSOLU ET UNIQUE POUR TOUT LE BOT
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

write_queue: Optional[asyncio.Queue] = None

def get_write_queue() -> asyncio.Queue:
    """Crée la file d'attente au bon moment (quand l'Event Loop est active)."""
    global write_queue
    if write_queue is None:
        write_queue = asyncio.Queue()
    return write_queue

async def db_writer_worker(db_path: str):
    """
    Le 'Facteur' unique : Il tourne en arrière-plan et traite la file d'attente.
    """
    logger.info("🛠️ [SINGLE WRITER] Démarrage de la file d'attente d'écriture.")
    queue = get_write_queue()
    
    async with aiosqlite.connect(db_path) as db:
        while True:
            # Sécurité : on initialise 'sql' à None pour éviter l'UnboundLocalError
            sql = None 
            try:
                # Il attend patiemment qu'une requête arrive dans la file
                sql, params = await queue.get()
                
                # Sécurité pour pouvoir éteindre le bot proprement
                if sql is None:
                    queue.task_done()
                    break

                # Il exécute la requête et sauvegarde
                await db.execute(sql, params)
                await db.commit()
                
                # Il signale que le travail est terminé
                queue.task_done()
                
            except Exception as e:
                # On gère l'affichage même si 'sql' est resté à None
                sql_str = sql if sql else "Aucune requête lue"
                logger.error(f"❌ [SINGLE WRITER ERROR] Échec de la requête : {e} | SQL: {sql_str}")

async def queue_write(sql: str, params: tuple = ()):
    """
    Fonction à utiliser dans tes services pour envoyer une requête dans la file d'attente.
    """
    queue = get_write_queue()
    await queue.put((sql, params))

@asynccontextmanager
async def get_db_connection(max_retries=5, base_delay=0.1):
    """
    Fournit une connexion asynchrone à la base de données centrale V2.
    Inclut les optimisations WAL et une gestion des blocages (Retry + Jitter).
    """
    conn = None
    
    # 🔄 BOUCLE DE RETRY : On essaie de se connecter plusieurs fois si c'est bloqué
    for attempt in range(max_retries):
        try:
            # On se connecte avec un timeout natif
            conn = await aiosqlite.connect(DB_PATH, timeout=20.0)
            conn.row_factory = aiosqlite.Row 
            
            # ⚡ POINT 1 (P0) : Activation des optimisations SQLite
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA busy_timeout=5000;")
            
            # Si tout s'est bien passé, on sort de la boucle de tentative
            break 
            
        except aiosqlite.OperationalError as e:
            # 🛡️ POINT 4 (P0) : Gestion du "database is locked"
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                # Si la connexion avait réussi mais que le PRAGMA a planté, on referme proprement
                if conn:
                    await conn.close()
                
                # Calcul du temps d'attente : exponentiel + variation aléatoire (Jitter)
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(f"⚠️ Base verrouillée (Tentative {attempt + 1}/{max_retries}). Réessai dans {delay:.2f}s...")
                await asyncio.sleep(delay)
            else:
                # 📝 POINT 5 (P0) : Log structuré et clair en cas d'échec définitif
                logger.error(f"❌ [DB FATAL] Impossible d'accéder à la base après {max_retries} tentatives : {e}")
                if conn:
                    await conn.close()
                raise e # On signale l'erreur au reste du code
    
    # On transmet la connexion sécurisée à ton code
    try:
        yield conn
    finally:
        # On garantit la fermeture, quoi qu'il arrive
        if conn:
            await conn.close()

async def init_db():
    """
    Vérifie et met à jour la structure de la base de données au démarrage.
    Remplace les migrations "runtime" dangereuses.
    """
    logger.info("🛠️ [DB INIT] Vérification de la structure de la base de données...")
    
    async with get_db_connection() as conn:
        # Liste des modifications de structure à appliquer
        migrations = [
            "ALTER TABLE viewers ADD COLUMN is_mod INTEGER DEFAULT 0",
            "ALTER TABLE viewers ADD COLUMN is_artist INTEGER DEFAULT 0",
            "ALTER TABLE announcements ADD COLUMN last_triggered DATETIME"
        ]
        
        for query in migrations:
            try:
                await conn.execute(query)
                logger.info(f"✅ [DB INIT] Nouvelle colonne ajoutée avec succès : {query.split('ADD COLUMN ')[1]}")
            except aiosqlite.OperationalError as e:
                # Si l'erreur dit que la colonne existe déjà, c'est normal, on ignore en silence !
                if "duplicate column name" not in str(e).lower():
                    logger.error(f"❌ [DB INIT] Erreur inattendue de migration : {e}")
        
        await conn.commit()
        logger.info("🚀 [DB INIT] Structure de la base de données prête et sécurisée !")
