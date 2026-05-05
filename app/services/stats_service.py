import asyncio
import aiohttp
from datetime import datetime
import logging

# --- IMPORT DES SERVICES ---
from app.services.label_service import write_label
from app.services.twitch_service import twitch_bot
from app.core.config import settings

logger = logging.getLogger("masthbot.stats")

# ==========================================
# 1. BOUCLE DE L'HORLOGE
# ==========================================
async def update_time_loop():
    """
    Boucle asynchrone qui met à jour l'heure système dans le fichier 'heure.txt'.
    Tourne en continu toutes les 10 secondes.
    """
    logger.info("⏳ Lancement de la boucle de l'horloge...")
    
    while True:
        try:
            heure_actuelle = datetime.now().strftime("%H:%M")
            write_label("heure.txt", heure_actuelle)
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"❌ Erreur dans la boucle de l'heure : {e}")
            await asyncio.sleep(5)


# ==========================================
# 2. BOUCLE DES STATISTIQUES TWITCH
# ==========================================
async def update_twitch_stats_loop():
    """
    Boucle pour récupérer les Viewers et Followers depuis Twitch.
    Tourne toutes les 60 secondes pour respecter les limites de l'API.
    """
    logger.info("📡 Lancement de la boucle Twitch (Viewers/Followers)...")
    
    # On attend 15 secondes au démarrage pour être sûr que le bot Twitch est connecté
    await asyncio.sleep(15) 

    while True:
        try:
            # --- RÉCUPÉRATION DES VIEWERS ---
            streams = await twitch_bot.fetch_streams(user_logins=[settings.TWITCH_CHANNEL.replace("#", "")])
            
            if streams:
                viewers_count = streams[0].viewer_count
                write_label("viewers.txt", str(viewers_count))
            else:
                write_label("viewers.txt", "--")

            # --- RÉCUPÉRATION DES FOLLOWERS ---
            broadcaster_id = getattr(twitch_bot, 'broadcaster_id', None)
            
            if broadcaster_id:
                client_id = getattr(twitch_bot._http, 'client_id', '')
                headers = {
                    "Client-ID": client_id,
                    "Authorization": f"Bearer {twitch_bot.master_token}"
                }
                url = f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={broadcaster_id}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            total_followers = data.get("total", 0)
                            write_label("followers.txt", str(total_followers))
                        else:
                            logger.error(f"⚠️ Erreur API Followers: Code {resp.status}")
            
            # Pause de 60 secondes pour ne pas spammer Twitch
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Erreur boucle Twitch stats : {e}")
            await asyncio.sleep(30)
