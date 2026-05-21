import asyncio
import aiohttp
import os
import dotenv
import sys

# Importation de ta connexion BDD
try:
    from app.core.database import get_db_connection
except ImportError:
    print("❌ Impossible d'importer get_db_connection. Es-tu à la racine du projet ?")
    sys.exit(1)

async def run_diagnostics():
    print("\n" + "="*50)
    print("🩺 DIAGNOSTIC GÉNÉRAL - MASTHBOT V2 🩺")
    print("="*50 + "\n")

    # ---------------------------------------------------------
    # 1. VARIABLES D'ENVIRONNEMENT
    # ---------------------------------------------------------
    print("📁 [1/5] VÉRIFICATION DU FICHIER .env")
    env_vars = dotenv.dotenv_values(".env")
    critical_keys = ["TWITCH_CLIENT_ID", "TWITCH_OAUTH_TOKEN", "TWITCH_BOT_OAUTH_TOKEN", "TWITCH_USERNAME", "TWITCH_CHANNEL"]
    
    env_ok = True
    for key in critical_keys:
        val = env_vars.get(key)
        if not val:
            print(f"  ❌ Manquant : {key}")
            env_ok = False
        else:
            print(f"  ✅ {key} : OK (commence par {val[:5]}...)")
    
    if env_ok: print("  🟢 Fichier .env parfait.\n")
    else: print("  🔴 Problème dans le fichier .env.\n")


    # ---------------------------------------------------------
    # 2. BASE DE DONNÉES POSTGRESQL
    # ---------------------------------------------------------
    print("🗄️ [2/5] VÉRIFICATION DE LA BASE POSTGRESQL")
    db_ok = False
    try:
        async with get_db_connection() as conn:
            print("  ✅ Connexion au serveur PostgreSQL réussie.")
            db_ok = True
            
            # Vérification des tables critiques
            tables_to_check = [
                "viewers", "tracked_streamers", "settings", 
                "announcements", "polls", "questions", "moderation_settings"
            ]
            print("  🔍 Vérification des tables :")
            for table in tables_to_check:
                try:
                    await conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
                    print(f"    ✅ Table '{table}' : OK")
                except Exception as e:
                    print(f"    ❌ Table '{table}' : MANQUANTE ou ERREUR ({e})")
            
            # Récupération des infos Discord pour le test suivant
            try:
                c = await conn.execute("SELECT notif_live_channel_id, streamers_channel_id FROM settings WHERE id=1")
                settings = await c.fetchone()
                settings = dict(settings) if settings else {}
            except:
                settings = {}

    except Exception as e:
        print(f"  ❌ Échec de la connexion à PostgreSQL : {e}")
    print("")


    # ---------------------------------------------------------
    # 3. OVERLAY NODE.JS (OBS)
    # ---------------------------------------------------------
    print("📺 [3/5] VÉRIFICATION DE L'OVERLAY NODE.JS (Port 3005)")
    try:
        async with aiohttp.ClientSession() as session:
            # On tente une requête GET basique sur le serveur local
            async with session.get("http://127.0.0.1:3005", timeout=2) as resp:
                print(f"  ✅ Overlay Node.js en ligne (Status: {resp.status})")
    except asyncio.TimeoutError:
        print("  ❌ Overlay Node.js : Timeout (Le serveur ne répond pas)")
    except aiohttp.ClientConnectorError:
        print("  ❌ Overlay Node.js : Hors Ligne (Processus Node non lancé ou erreur de port)")
    except Exception as e:
        print(f"  ❌ Overlay Node.js : Erreur inconnue ({e})")
    print("")


    # ---------------------------------------------------------
    # 4. API TWITCH
    # ---------------------------------------------------------
    print("🟣 [4/5] VÉRIFICATION DE L'API TWITCH")
    token = env_vars.get("TWITCH_OAUTH_TOKEN", "").replace("oauth:", "").strip()
    if token:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"OAuth {token}"}
                async with session.get("https://id.twitch.tv/oauth2/validate", headers=headers, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"  ✅ Token Twitch valide pour l'utilisateur : {data.get('login')}")
                        print(f"  ✅ Scopes autorisés : {len(data.get('scopes', []))}")
                    else:
                        print(f"  ❌ Token Twitch invalide ou expiré (Code {resp.status})")
        except Exception as e:
            print(f"  ❌ Erreur de connexion à Twitch : {e}")
    else:
        print("  ❌ Pas de token Twitch à tester.")
    print("")


    # ---------------------------------------------------------
    # 5. PARAMÈTRES DISCORD
    # ---------------------------------------------------------
    print("🎮 [5/5] VÉRIFICATION DES RÉGLAGES DISCORD")
    if db_ok and settings:
        notif_perso = settings.get("notif_live_channel_id")
        notif_potes = settings.get("streamers_channel_id")
        
        if notif_perso: print(f"  ✅ ID Salon Discord (Live Perso) : {notif_perso}")
        else: print("  ❌ ID Salon Discord (Live Perso) : MANQUANT dans les paramètres web")
            
        if notif_potes: print(f"  ✅ ID Salon Discord (Live Partenaires) : {notif_potes}")
        else: print("  ❌ ID Salon Discord (Live Partenaires) : MANQUANT dans les paramètres web")
    else:
        print("  ⚠️ Impossible de vérifier Discord (Base de données inaccessible ou table settings vide).")
    print("\n" + "="*50)
    print("🏁 FIN DU DIAGNOSTIC 🏁")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
