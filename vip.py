import asyncio
import aiohttp
import sqlite3
import os
from dotenv import load_dotenv

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

async def main():
    print("🚀 Lancement de l'Aspirateur à VIPs...")
    
    # 1. Charger le Token depuis ton fichier .env
    load_dotenv("/home/masthom/BOT_V2/.env")
    token = os.getenv("TWITCH_OAUTH_TOKEN", "").replace("oauth:", "").strip()
    
    if not token:
        print("❌ Erreur : Impossible de trouver le token dans le fichier .env")
        return
        
    async with aiohttp.ClientSession() as session:
        # 2. Validation du token et récupération automatique de ton ID de chaîne
        print("🔑 Connexion à Twitch...")
        async with session.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {token}"}) as r:
            if r.status != 200:
                print("❌ Erreur : Ton token Twitch est invalide.")
                return
            data = await r.json()
            client_id = data['client_id']
            broadcaster_id = data['user_id']

        headers = {
            "Client-ID": client_id,
            "Authorization": f"Bearer {token}"
        }
        
        # 3. Récupérer les VIPs
        print("📡 Récupération de ta liste officielle de VIPs...")
        async with session.get(f"https://api.twitch.tv/helix/channels/vips?broadcaster_id={broadcaster_id}", headers=headers) as r:
            if r.status in [401, 403]:
                print("\n⚠️ TWITCH REFUSE L'ACCÈS (Erreur 401/403) ⚠️")
                print("Ton token a été généré sans la permission 'channel:read:vips'.")
                print("👉 Pas de panique ! Supprime ce script et laisse tourner ton live : les VIPs seront ajoutés automatiquement quand ils parleront (grâce à la modification ci-dessous) !")
                return
            elif r.status != 200:
                print(f"❌ Erreur API Twitch : {r.status}")
                return
                
            vips = (await r.json()).get("data", [])
            
            if not vips:
                print("ℹ️ Twitch indique que tu n'as aucun VIP sur ta chaîne !")
                return
                
            # 4. Enregistrer dans la base de données
            print(f"💾 {len(vips)} VIPs trouvés ! Sauvegarde dans la base de données...")
            conn = sqlite3.connect(DB_PATH)
            for v in vips:
                t_id = v['user_id']
                u_name = v['user_login']
                # On crée le viewer s'il n'existe pas
                conn.execute("INSERT OR IGNORE INTO viewers (twitch_id, username) VALUES (?, ?)", (t_id, u_name))
                # On lui donne le grade VIP permanent
                conn.execute("UPDATE viewers SET is_vip = 1 WHERE twitch_id = ?", (t_id,))
            
            conn.commit()
            conn.close()
            print("✨ TERMINÉ ! Va sur ton interface Web, tous tes VIPs sont là !")

if __name__ == "__main__":
    asyncio.run(main())
