import asyncio
import aiohttp
import os
from dotenv import load_dotenv

async def verifier_token():
    print("="*50)
    print("🔍 SCANNER DE TOKEN TWITCH (MODE DÉTECTIVE)")
    print("="*50)
    
    # Le paramètre override=True force Python à ignorer le cache 
    # et à lire la vraie valeur actuelle du fichier .env
    load_dotenv(override=True)
    token = os.getenv('TWITCH_ACCESS_TOKEN')
    
    if not token:
        print("❌ ERREUR : Aucun TWITCH_ACCESS_TOKEN trouvé dans le .env")
        return

    # Nettoyage (.strip() enlève aussi les espaces invisibles à la fin)
    clean_token = token.replace('oauth:', '').replace("'", "").replace('"', '').strip()

    # --- TEST DE VÉRIFICATION VISUELLE ---
    debut = clean_token[:5]
    fin = clean_token[-3:]
    print(f"👀 Token lu par Python : {debut}...{fin}")
    print(f"📏 Longueur du token   : {len(clean_token)} caractères")
    print("-" * 50)
    # -------------------------------------

    headers = {
        'Authorization': f'OAuth {clean_token}'
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://id.twitch.tv/oauth2/validate', headers=headers) as resp:
                data = await resp.json()
                
                if resp.status == 200:
                    print("✅ RÉPONSE : Le Token est VALIDE et reconnu par Twitch !")
                    scopes = data.get('scopes', [])
                    if 'channel:read:subscriptions' in scopes:
                        print("🟢 PARFAIT : La permission des abonnés est bien présente.")
                    else:
                        print("🔴 PROBLÈME : Il manque la permission 'channel:read:subscriptions' !")
                else:
                    print(f"❌ RÉPONSE : Le Token est INVALIDE (Code {resp.status})")
                    print("💡 DÉDUCTION : Regarde la ligne 'Token lu par Python' ci-dessus.")
                    print("Si ce ne sont pas les premières lettres du NOUVEAU token que tu as généré,")
                    print("alors vérifie qu'il n'y a pas de doublon dans ton .env et qu'il est bien sauvegardé !")

        except Exception as e:
            print(f"❌ Erreur de connexion : {e}")

if __name__ == "__main__":
    asyncio.run(verifier_token())
