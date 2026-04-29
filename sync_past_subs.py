import asyncio
import sqlite3
import os
import aiohttp
from dotenv import load_dotenv

# --- PARAMÈTRES ---
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"
BROADCASTER_ID = "439356462"

async def get_broadcaster_login(session, headers):
    """Récupère ton pseudo exact via l'API Twitch"""
    url = f"https://api.twitch.tv/helix/users?id={BROADCASTER_ID}"
    async with session.get(url, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data['data'][0]['login']
    return None

async def fetch_real_months(session, user_login, broadcaster_login):
    """Interroge l'API IVR pour voir l'historique complet, même passé"""
    url = f"https://api.ivr.fi/v2/twitch/subage/{user_login}/{broadcaster_login}"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                # On récupère le cumul. Si la personne n'a jamais sub, ça renvoie 0.
                return data.get('cumulative', {}).get('months', 0)
    except Exception as e:
        pass
    return 0

async def sync_all_known_viewers():
    load_dotenv(override=True)
    token = os.getenv('TWITCH_ACCESS_TOKEN')
    client_id = os.getenv('TWITCH_CLIENT_ID')

    if not token or not client_id:
        print("❌ ERREUR : TOKEN ou CLIENT_ID manquant.")
        return

    clean_token = token.replace('oauth:', '').replace("'", "").replace('"', '').strip()
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {clean_token}'
    }

    async with aiohttp.ClientSession() as session:
        print("🚀 ÉTAPE 1 : Préparation du scanner...")
        broadcaster_login = await get_broadcaster_login(session, headers)
        
        if not broadcaster_login:
            print("❌ Impossible d'identifier ta chaîne.")
            return

        # Connexion à la base de données
        conn = sqlite3.connect(DB_PATH)
        db_cursor = conn.cursor()
        
        # On récupère TOUS les viewers que Félix connaît
        db_cursor.execute("SELECT twitch_id, username FROM viewers WHERE username IS NOT NULL")
        all_viewers = db_cursor.fetchall()
        
        print(f"📥 {len(all_viewers)} viewers trouvés dans la mémoire de Félix.")
        print("🚀 ÉTAPE 2 : Analyse de l'historique de chaque viewer (Cela peut prendre du temps)...")
        
        count = 0
        
        for twitch_id, username in all_viewers:
            # On vérifie l'historique d'abonnement (passé ou présent)
            real_months = await fetch_real_months(session, username.lower(), broadcaster_login)
            
            # Si le viewer a au moins 1 mois d'abonnement dans son historique
            if real_months > 0:
                db_cursor.execute("""
                    UPDATE viewers 
                    SET sub_months = ? 
                    WHERE twitch_id = ?
                """, (real_months, twitch_id))
                
                count += 1
                print(f"💎 Historique trouvé : {username} -> {real_months} mois au total")
            
            # Pause de 0.2s pour ne pas se faire bloquer par l'API
            await asyncio.sleep(0.2)

        # On sauvegarde toutes les modifications
        conn.commit()
        conn.close()
        
        print("=" * 50)
        print(f"✨ SCAN DES ANCIENS ABONNÉS TERMINÉ !")
        print(f"✅ {count} profils avec un historique de sub ont été mis à jour.")
        print("=" * 50)

if __name__ == "__main__":
    asyncio.run(sync_all_known_viewers())
