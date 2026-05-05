import sqlite3

# Chemin vers ta base de données
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def activer_wal():
    try:
        print("🔧 Connexion à la base de données...")
        conn = sqlite3.connect(DB_PATH)
        
        # On active le mode WAL
        conn.execute("PRAGMA journal_mode=WAL;")
        
        # On augmente le délai d'attente interne de la base de données
        conn.execute("PRAGMA busy_timeout=5000;")
        
        print("✅ Mode WAL activé avec succès ! Ton bot est maintenant beaucoup plus rapide et résistant.")
    except Exception as e:
        print(f"❌ Erreur : {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    activer_wal()
