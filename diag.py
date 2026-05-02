import sqlite3
import os

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

# La liste absolue de TOUT ce que ta table "viewers" est censée contenir
COLONNES_ATTENDUES = [
    # Base Twitch
    "twitch_id", "username", "is_vip",
    # Activité & Temps
    "messages", "messages_session", "watchtime", "watchtime_session", "streak_days",
    "emotes_global", "commands_global",
    # Monnaie & Soutien
    "points", "points_session", "gifts_count", "gifts_session", "bits_count", 
    "sub_months", "rewards_claimed",
    # Jeux & Podiums
    "first_count", "deuz_count", "troiz_count", "gamble_won", 
    "bombs_won", "bombs_lost", "words_guessed",
    # IA & Custom
    "roast_level", "ai_prompts"
]

TABLES_ATTENDUES = [
    "viewers", "trophy_list", "viewer_trophies", "stream_events"
]

def faire_le_bilan():
    print("==================================================")
    print("🔍 DIAGNOSTIC DU SYSTÈME FÉLIX - BASE DE DONNÉES")
    print("==================================================\n")

    if not os.path.exists(DB_PATH):
        print("❌ ERREUR CRITIQUE : Le fichier bot_database.db est introuvable !")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. VÉRIFICATION DES TABLES
        print("📁 1. VÉRIFICATION DES TABLES :")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables_existantes = [row[0] for row in cursor.fetchall()]
        
        tables_manquantes = []
        for table in TABLES_ATTENDUES:
            if table in tables_existantes:
                print(f"  ✅ Table trouvée : {table}")
            else:
                print(f"  ❌ TABLE MANQUANTE : {table}")
                tables_manquantes.append(table)

        print("\n" + "-"*40 + "\n")

        # 2. VÉRIFICATION DES COLONNES (Table Viewers)
        if "viewers" in tables_existantes:
            print("📊 2. VÉRIFICATION DES COLONNES (Table 'viewers') :")
            cursor.execute("PRAGMA table_info(viewers);")
            colonnes_existantes = [row[1] for row in cursor.fetchall()]
            
            colonnes_manquantes = []
            colonnes_ok = 0
            
            for col in COLONNES_ATTENDUES:
                if col in colonnes_existantes:
                    colonnes_ok += 1
                else:
                    colonnes_manquantes.append(col)
                    print(f"  ❌ COLONNE MANQUANTE : {col}")
            
            if len(colonnes_manquantes) == 0:
                print(f"  ✅ TOUTES LES COLONNES SONT PRÉSENTES ({colonnes_ok}/{len(COLONNES_ATTENDUES)})")
                print("  👉 Ton Moteur de Trophées ne plantera pas !")
            else:
                print(f"\n⚠️ ATTENTION : Il te manque {len(colonnes_manquantes)} colonne(s) !")
                print("👉 Tu dois lancer le script `setup_exhaustive_db.py` pour les ajouter.")
        else:
            print("❌ Impossible de vérifier les colonnes car la table 'viewers' n'existe pas.")

        print("\n==================================================")
        if len(tables_manquantes) == 0 and len(colonnes_manquantes) == 0:
            print("✨ RÉSULTAT : 100% PARFAIT ! TOUT EST EN PLACE ! ✨")
        else:
            print("🛠️ RÉSULTAT : Des éléments manquent. Répare la base avant de lancer le bot.")
        print("==================================================")

    except Exception as e:
        print(f"❌ Erreur lors du diagnostic : {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    faire_le_bilan()
