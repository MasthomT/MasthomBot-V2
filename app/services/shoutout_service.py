import asyncio
import aiohttp
import logging
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.shoutout")
NODE_URL = "http://192.168.1.32:3005"

class ShoutoutService:
    async def get_config(self):
        """Récupère la config depuis PostgreSQL."""
        async with get_db_connection() as conn:
            c = await conn.execute("SELECT * FROM settings LIMIT 1")
            row = await c.fetchone()
            return dict(row) if row else {}

    async def trigger_replay(self, slug=None, query=None):
        payload = {"slug": slug, "query": query}
        timeout_node = aiohttp.ClientTimeout(total=5) # ⏱️ On passe à 5 secondes
        
        try:
            async with aiohttp.ClientSession(timeout=timeout_node) as session:
                await session.post(f"{NODE_URL}/api/replay", json=payload)
                return True
        except asyncio.TimeoutError:
            logger.warning("⏳ [REPLAY] L'overlay Node.js a mis trop de temps à répondre, mais le replay est sûrement lancé !")
            return True # On renvoie True pour que le Stream Deck valide quand même l'action
        except Exception as e:
            logger.error(f"❌ [REPLAY] Erreur avec l'overlay : {e}")
            return False

    async def trigger_shoutout(self, target, slug=None, duration=30):
        payload = {"target": target, "slug": slug, "duration": duration}
        timeout_node = aiohttp.ClientTimeout(total=5) # ⏱️ On passe à 5 secondes
        
        try:
            async with aiohttp.ClientSession(timeout=timeout_node) as session:
                await session.post(f"{NODE_URL}/api/shoutout", json=payload)
                return True
        except asyncio.TimeoutError:
            logger.warning("⏳ [SHOUTOUT] L'overlay Node.js a mis trop de temps à répondre, mais le SO est sûrement lancé !")
            return True # On renvoie True pour que le Stream Deck valide quand même l'action
        except Exception as e:
            logger.error(f"❌ [SHOUTOUT] Erreur avec l'overlay : {e}")
            return False

shoutout_service = ShoutoutService()
