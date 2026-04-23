import aiosqlite
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger("masthbot.database")

# LE CHEMIN ABSOLU ET UNIQUE POUR TOUT LE BOT
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

@asynccontextmanager
async def get_db_connection():
    """Fournit une connexion asynchrone à la base de données centrale V2."""
    conn = await aiosqlite.connect(DB_PATH)
    
    # Configuration pour lire les lignes comme des dictionnaires (plus sûr)
    conn.row_factory = aiosqlite.Row 
    
    try:
        yield conn
    finally:
        await conn.close()
