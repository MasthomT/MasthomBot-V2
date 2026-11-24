import asyncio
import aiohttp
import logging
from app.core.database import get_db_connection
from app.core import settings_cache
from app.core.config import settings

logger = logging.getLogger("masthbot.shoutout")

async def latest_clip_id() -> str | None:
    """Identifiant du dernier clip de la chaîne, en sautant les clips automatiques « Clip by inStreamly ».
    Cherche semaine par semaine en remontant (Twitch limite chaque requête à une semaine), jusqu'à un an."""
    from datetime import datetime, timedelta, timezone
    from app.services.clip_discord_service import _fetch_window, _is_ignored
    token = settings.TWITCH_OAUTH_TOKEN.replace("oauth:", "").strip()
    headers = {"Client-ID": settings.TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
    end = datetime.now(timezone.utc)
    try:
        async with aiohttp.ClientSession() as session:
            for _ in range(52):
                start = end - timedelta(days=7)
                clips = [c for c in await _fetch_window(session, headers, settings.TWITCH_BROADCASTER_ID, start, end) if not _is_ignored(c)]
                if clips:
                    return max(clips, key=lambda c: c.get("created_at", ""))["id"]
                end = start
    except Exception as e:
        logger.warning(f"⚠️ [REPLAY] Recherche du dernier clip impossible : {e}")
    return None


class ShoutoutService:
    async def get_config(self):
        """Récupère la config depuis PostgreSQL."""
        return await settings_cache.get_settings()

    async def trigger_replay(self, slug=None, query=None):
        if not slug and not query:            # « le dernier clip » : jamais un clip automatique inStreamly
            slug = await latest_clip_id()
        payload = {"slug": slug, "query": query}
        timeout_node = aiohttp.ClientTimeout(total=5) # ⏱️ On passe à 5 secondes
        
        try:
            async with aiohttp.ClientSession(timeout=timeout_node) as session:
                await session.post(f"{settings.OVERLAY_NODE_URL}/api/replay", json=payload)
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
                await session.post(f"{settings.OVERLAY_NODE_URL}/api/shoutout", json=payload)
                return True
        except asyncio.TimeoutError:
            logger.warning("⏳ [SHOUTOUT] L'overlay Node.js a mis trop de temps à répondre, mais le SO est sûrement lancé !")
            return True # On renvoie True pour que le Stream Deck valide quand même l'action
        except Exception as e:
            logger.error(f"❌ [SHOUTOUT] Erreur avec l'overlay : {e}")
            return False

shoutout_service = ShoutoutService()
