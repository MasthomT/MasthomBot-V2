import sqlite3

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def activer_mode_wal():
    print("🚀 Optimisation de la base de données en cours...")
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 1. Active le mode WAL (Write-Ahead Logging)
        # Permet d'écrire et lire en même temps sans bloquer le fichier
        cursor = conn.execute("PRAGMA journal_mode=WAL;")
        mode = cursor.fetchone()[0]
        
        # 2. Optimise la vitesse de synchronisation
        conn.execute("PRAGMA synchronous=NORMAL;")
        
        # 3. Augmente le temps d'attente maximum par défaut en cas de bouchon (30 secondes)
        conn.execute("PRAGMA busy_timeout=30000;")
        
        conn.commit()
        conn.close()
        
        if mode.upper() == "WAL":
            print("✨ SUCCÈS ! La base de données est maintenant en mode 'WAL'.")
            print("👉 Fini les erreurs 'database is locked', ton bot peut écrire en simultané !")
        else:
            print(f"⚠️ Échec. Le mode actuel est : {mode}")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'optimisation : {e}")

if __name__ == "__main__":
    activer_mode_wal()
