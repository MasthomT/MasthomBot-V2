import asyncio
import aiohttp
import sqlite3
import logging
from datetime import datetime
import dotenv

logger = logging.getLogger("masthbot.unfollows")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def init_cache_table():
    """Crée une table invisible pour stocker la liste des followers entre chaque scan."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS followers_cache (user_id TEXT PRIMARY KEY, user_name TEXT)")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erreur création cache: {e}")

async def fetch_all_followers(session, client_id, token, broadcaster_id):
    """Télécharge toute la liste de tes followers en gérant les pages."""
    url = f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={broadcaster_id}&first=100"
    headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
    followers = {}
    cursor = ""

    while True:
        page_url = url if not cursor else f"{url}&after={cursor}"
        try:
            async with session.get(page_url, headers=headers) as resp:
                if resp.status != 200:
                    break
                data = await resp.json()
                for item in data.get("data", []):
                    followers[item["user_id"]] = item["user_name"]

                cursor = data.get("pagination", {}).get("cursor")
                if not cursor:
                    break
        except Exception:
            break
        await asyncio.sleep(0.1) # Petite pause pour ne pas brusquer l'API Twitch
    return followers

async def unfollow_monitor_routine():
    init_cache_table()
    await asyncio.sleep(15) # Attendre que le bot démarre bien

    while True:
        try:
            env = dotenv.dotenv_values(".env")
            client_id = env.get("TWITCH_CLIENT_ID", "").strip()
            token = env.get("TWITCH_OAUTH_TOKEN", "").replace("oauth:", "").strip()
            channel = env.get("TWITCH_CHANNEL", "masthom_").replace("#", "").strip()

            if not client_id or not token:
                await asyncio.sleep(300)
                continue

            async with aiohttp.ClientSession() as session:
                # 1. Obtenir ton ID
                headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
                async with session.get(f"https://api.twitch.tv/helix/users?login={channel}", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        broadcaster_id = data["data"][0]["id"]
                    else:
                        await asyncio.sleep(300)
                        continue

                # 2. Scanner les followers actuels
                current_followers = await fetch_all_followers(session, client_id, token, broadcaster_id)

                if not current_followers:
                    # Sécurité : Si l'API bug et renvoie 0, on annule pour ne pas croire que tout le monde a unfollow
                    await asyncio.sleep(1800)
                    continue

                # 3. Comparer avec la Base de Données
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row

                cached_rows = conn.execute("SELECT * FROM followers_cache").fetchall()
                cached_followers = {row["user_id"]: row["user_name"] for row in cached_rows}

                if not cached_followers:
                    # PREMIER LANCEMENT : On prend juste une "photo" de départ
                    logger.info(f"📸 [UNFOLLOWS] Première capture effectuée ({len(current_followers)} followers mis en cache).")
                    for uid, uname in current_followers.items():
                        conn.execute("INSERT INTO followers_cache (user_id, user_name) VALUES (?, ?)", (uid, uname))
                else:
                    # SCANS SUIVANTS : On cherche les disparus
                    unfollowers = []
                    
                    # Qui était là avant et n'est plus là ?
                    for uid, uname in cached_followers.items():
                        if uid not in current_followers:
                            unfollowers.append(uname)
                            # On le supprime du cache
                            conn.execute("DELETE FROM followers_cache WHERE user_id = ?", (uid,))

                    # Qui est nouveau ? (On l'ajoute au cache pour le surveiller)
                    for uid, uname in current_followers.items():
                        if uid not in cached_followers:
                            conn.execute("INSERT INTO followers_cache (user_id, user_name) VALUES (?, ?)", (uid, uname))

                    # Si on a trouvé des unfollows, on les ajoute à tes statistiques !
                    if unfollowers:
                        logger.info(f"💔 [UNFOLLOWS] {len(unfollowers)} traîtres détectés !")
                        for uname in unfollowers:
                            conn.execute("INSERT INTO unfollows (username, timestamp) VALUES (?, ?)",
                                         (uname, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                conn.commit()
                conn.close()

        except Exception as e:
            logger.error(f"❌ [UNFOLLOWS] Erreur routine : {e}")

        # Pause de 30 minutes avant le prochain scan (1800 secondes)
        await asyncio.sleep(1800)
