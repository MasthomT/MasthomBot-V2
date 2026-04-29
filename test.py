import asyncio
import sqlite3
import os
import aiohttp
from dotenv import load_dotenv

# --- 1. PARAMÈTRES FIXES ---
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"
BROADCASTER_ID = "439356462" # Ton ID Streamer mis en dur

def update_env_file(key, value):
    """Fonction utilitaire pour mettre à jour le fichier .env proprement"""
    try:
        with open(".env", "r") as f:
            lines = f.readlines()
        with open(".env", "w") as f:
            for line in lines:
                if line.startswith(f"{key}="):
                    # On garde le format avec les simples guillemets pour l'accès token
                    f.write(f"{key}='{value}'\n")
                else:
                    f.write(line)
    except Exception as e:
        print(f"❌ Erreur lors de l'écriture dans le .env : {e}")

async def get_new_token(session):
    """Fonction qui demande un nouveau token à Twitch si l'ancien est périmé"""
    print("🔄 Le token a expiré ! Tentative de rafraîchissement automatique...")
    client_id = os.getenv('TWITCH_CLIENT_ID')
    client_secret = os.getenv('TWITCH_CLIENT_SECRET')
    refresh_token = os.getenv('TWITCH_REFRESH_TOKEN')

    if not client_secret:
        print("❌ ERREUR : Il te manque TWITCH_CLIENT_SECRET dans ton .env !")
        return None

    url = "https://id.twitch.tv/oauth2/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    async with session.post(url, data=payload) as resp:
        if resp.status == 200:
            data = await resp.json()
            new_access = data['access_token']
            new_refresh = data['refresh_token']
            
            # On met à jour le fichier .env pour les prochains lancements
            update_env_file("TWITCH_ACCESS_TOKEN", f"oauth:{new_access}")
            update_env_file("TWITCH_REFRESH_TOKEN", new_refresh)
            
            print("✅ Token rafraîchi avec succès et sauvegardé !")
            return new_access
        else:
            print(f"❌ Échec du rafraîchissement (Code {resp.status})")
            return None

async def sync_twitch_subs():
    # On charge le .env pour avoir les variables à jour
    load_dotenv()
    token = os.getenv('TWITCH_ACCESS_TOKEN')
    client_id = os.getenv('TWITCH_CLIENT_ID')

    if not token:
        print("❌ ERREUR : TWITCH_ACCESS_TOKEN introuvable.")
        return

    # Nettoyage du token pour l'en-tête API
    clean_token = token.replace('oauth:', '').replace("'", "").replace('"', '')
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {clean_token}'
    }

    async with aiohttp.ClientSession() as session:
        all_subs = []
        cursor = None
        print(f"🚀 Démarrage de la synchro des subs pour l'ID : {BROADCASTER_ID}")
        
        # --- 2. RÉCUPÉRATION DES ABONNÉS (BOUCLE PRINCIPALE) ---
        while True:
            url = f'https://api.twitch.tv/helix/subscriptions?broadcaster_id={BROADCASTER_ID}'
            if cursor:
                url += f'&after={cursor}'
            
            async with session.get(url, headers=headers) as resp:
                # Si erreur 401, on déclenche le plan de secours !
                if resp.status == 401:
                    new_token = await get_new_token(session)
                    if new_token:
                        # On met à jour l'en-tête avec la nouvelle clé et on recommence ce tour de boucle
                        headers['Authorization'] = f'Bearer {new_token}'
                        continue 
                    else:
                        print("🛑 Impossible de continuer sans un token valide.")
                        return

                if resp.status != 200:
                    err_text = await resp.text()
                    print(f"❌ Erreur API Twitch ({resp.status}): {err_text}")
                    return
                
                data = await resp.json()
                current_page = data.get('data', [])
                all_subs.extend(current_page)
                
                print(f"📥 {len(all_subs)} abonnés récupérés...")
                
                # Gestion de la page suivante
                cursor = data.get('pagination', {}).get('cursor')
                if not cursor:
                    break

        # --- 3. MISE À JOUR DE LA BASE DE DONNÉES SQL ---
        try:
            conn = sqlite3.connect(DB_PATH)
            db_cursor = conn.cursor()
            
            count = 0
            for sub in all_subs:
                t_id = sub['user_id']
                u_name = sub['user_name']
                # cumulative_months est la vraie valeur officielle de Twitch !
                months = sub.get('cumulative_months', 1)

                db_cursor.execute("""
                    INSERT INTO viewers (twitch_id, username, sub_months)
                    VALUES (?, ?, ?)
                    ON CONFLICT(twitch_id) DO UPDATE SET
                        sub_months = excluded.sub_months,
                        username = excluded.username
                """, (t_id, u_name, months))
                count += 1

            conn.commit()
            print(f"✨ RÉUSSITE TOTALE : {count} abonnés synchronisés (dont Yukino) !")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'écriture SQL : {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    asyncio.run(sync_twitch_subs())
