import os
import httpx
from dotenv import load_dotenv, set_key

# On s'assure que le .env est bien chargé
load_dotenv()
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

async def refresh_twitch_token(refresh_token_key, access_token_key):
    """
    Renouvelle automatiquement un jeton Twitch expiré.
    """
    print(f"🔄 [AUTH] Tentative de renouvellement pour {access_token_key}...")
    
    url = "https://id.twitch.tv/oauth2/token"
    refresh_token = os.getenv(refresh_token_key)
    
    data = {
        "client_id": os.getenv("TWITCH_CLIENT_ID"),
        "client_secret": os.getenv("TWITCH_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=data)
            if response.status_code == 200:
                new_data = response.json()
                new_access = new_data["access_token"]
                new_refresh = new_data["refresh_token"]

                # --- MISE À JOUR DU FICHIER .ENV ---
                # set_key permet d'écrire physiquement dans le fichier pour le prochain redémarrage
                set_key(ENV_PATH, access_token_key, f"oauth:{new_access}")
                set_key(ENV_PATH, refresh_token_key, new_refresh)
                
                # Mise à jour de la mémoire actuelle
                os.environ[access_token_key] = f"oauth:{new_access}"
                os.environ[refresh_token_key] = new_refresh
                
                print(f"✅ [AUTH] {access_token_key} renouvelé avec succès !")
                return f"oauth:{new_access}"
            else:
                print(f"❌ [AUTH] Erreur lors du refresh : {response.text}")
                return None
        except Exception as e:
            print(f"⚠️ [AUTH] Erreur réseau : {e}")
            return None
