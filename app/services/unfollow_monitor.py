import asyncio
import aiohttp
import logging
from app.core.database import get_db_connection
from app.core.config import settings

logger = logging.getLogger("masthbot.unfollows")

async def init_cache_table():
    """Initialise les tables dans PostgreSQL."""
    async with get_db_connection() as conn:
        # On crée les DEUX tables nécessaires pour éviter le crash
        await conn.execute("CREATE TABLE IF NOT EXISTS followers_cache (user_id TEXT PRIMARY KEY, user_name TEXT)")
        await conn.execute("CREATE TABLE IF NOT EXISTS unfollows (id SERIAL PRIMARY KEY, username TEXT, timestamp TIMESTAMP)")

async def fetch_all_followers(session, client_id, token, broadcaster_id):
    url = f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={broadcaster_id}&first=100"
    headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
    followers = {}
    cursor = ""
    
    while True:
        page_url = url if not cursor else f"{url}&after={cursor}"
        async with session.get(page_url, headers=headers) as resp:
            if resp.status != 200:
                logger.error(f"❌ [TWITCH API] Erreur lors de la récupération des followers ({resp.status})")
                return None # On renvoie None (et pas {}) pour signaler un crash Twitch
                
            data = await resp.json()
            for item in data.get("data", []):
                followers[item["user_id"]] = item["user_name"]
                
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor: 
                break
                
    return followers

async def unfollow_monitor_routine():
    await init_cache_table()

    client_id = settings.TWITCH_CLIENT_ID
    token = settings.TWITCH_OAUTH_TOKEN.replace("oauth:", "")
    broadcaster_id = "439356462"

    while True:
        try:
            async with get_db_connection() as conn:
                # 1. Charger le cache actuel proprement avec le curseur (c)
                c = await conn.execute("SELECT * FROM followers_cache")
                rows = await c.fetchall()
                
                cached_followers = {row['user_id']: row['user_name'] for row in rows} if rows else {}

                # 2. Scanner Twitch
                async with aiohttp.ClientSession() as session:
                    current_followers = await fetch_all_followers(session, client_id, token, broadcaster_id)

                # SÉCURITÉ : On ne met à jour que si Twitch a bien répondu
                if current_followers is not None:
                    unfollowers = [name for uid, name in cached_followers.items() if uid not in current_followers]

                    # 3. Mise à jour PostgreSQL (avec la syntaxe $1, $2)
                    for uid in [uid for uid in cached_followers if uid not in current_followers]:
                        await conn.execute("DELETE FROM followers_cache WHERE user_id = $1", (uid,))

                    for uid, uname in current_followers.items():
                        if uid not in cached_followers:
                            await conn.execute("INSERT INTO followers_cache (user_id, user_name) VALUES ($1, $2)", (uid, uname))

                    if unfollowers:
                        for uname in unfollowers:
                            await conn.execute("INSERT INTO unfollows (username, timestamp) VALUES ($1, NOW())", (uname,))
                            logger.info(f"💔 Unfollow détecté : {uname}")

        except Exception as e:
            logger.error(f"❌ [UNFOLLOWS] Erreur critique de la boucle : {e}")

        # Pause de 6 heures (21600 secondes)
        await asyncio.sleep(21600)
