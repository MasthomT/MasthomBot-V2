import asyncio
import aiohttp
import logging
import os
from datetime import datetime
from app.core.database import get_db_connection
from app.core.config import settings # IMPORTANT pour récupérer les IDs

logger = logging.getLogger("masthbot.unfollows")

async def init_cache_table():
    """Initialise la table de cache dans PostgreSQL."""
    async with get_db_connection() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS followers_cache (user_id TEXT PRIMARY KEY, user_name TEXT)")

async def fetch_all_followers(session, client_id, token, broadcaster_id):
    url = f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={broadcaster_id}&first=100"
    headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
    followers = {}
    cursor = ""
    while True:
        page_url = url if not cursor else f"{url}&after={cursor}"
        async with session.get(page_url, headers=headers) as resp:
            if resp.status != 200: break
            data = await resp.json()
            for item in data.get("data", []):
                followers[item["user_id"]] = item["user_name"]
            cursor = data.get("pagination", {}).get("cursor")
            if not cursor: break
    return followers

async def unfollow_monitor_routine():
    await init_cache_table()
    
    # Récupération propre des infos Twitch
    client_id = settings.TWITCH_CLIENT_ID
    token = settings.TWITCH_OAUTH_TOKEN.replace("oauth:", "")
    # Note : Si tu n'as pas le broadcaster_id, il faut le récupérer via l'API ou le mettre en dur
    broadcaster_id = "439356462" 

    while True:
        try:
            async with get_db_connection() as conn:
                # 1. Charger le cache actuel (On utilise execute + fetchall)
                await conn.execute("SELECT * FROM followers_cache")
                rows = await conn.fetchall()
                cached_followers = {row['user_id']: row['user_name'] for row in rows}

                # 2. Scanner Twitch
                async with aiohttp.ClientSession() as session:
                    current_followers = await fetch_all_followers(session, client_id, token, broadcaster_id)

                    unfollowers = [name for uid, name in cached_followers.items() if uid not in current_followers]

                    # 3. Mise à jour PostgreSQL (SYNTAXE CORRECTE $1, $2)
                    for uid in [uid for uid in cached_followers if uid not in current_followers]:
                        await conn.execute("DELETE FROM followers_cache WHERE user_id = $1", (uid,))

                    for uid, uname in current_followers.items():
                        if uid not in cached_followers:
                            await conn.execute("INSERT INTO followers_cache (user_id, user_name) VALUES ($1, $2)", (uid, uname))

                    if unfollowers:
                        for uname in unfollowers:
                            await conn.execute("INSERT INTO unfollows (username, timestamp) VALUES ($1, NOW())", (uname,))
                            
        except Exception as e:
            logger.error(f"❌ [UNFOLLOWS] Erreur : {e}")
        
        await asyncio.sleep(21600)
