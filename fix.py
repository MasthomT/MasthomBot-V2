import asyncio
from app.core.database import get_db_connection

async def fix():
    async with get_db_connection() as db:
        # 1. On supprime le pseudo buggué
        await db.execute("DELETE FROM viewers WHERE username = 'killfouine'")
        # 2. On retire la règle stricte pour éviter que ça ne recommence
        await db.execute("ALTER TABLE viewers DROP CONSTRAINT IF EXISTS viewers_username_key")
        print("✅ Opération réussie ! Le pseudo est débloqué.")

asyncio.run(fix())
