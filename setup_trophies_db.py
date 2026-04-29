import sqlite3

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def installer_moteur_trophees():
    print("🚀 Installation du Moteur Universel de Trophées...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Le Catalogue des Trophées
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trophies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                stat_type TEXT NOT NULL,      -- Ex: 'messages_sent', 'bomb_win', 'reward_hydration'
                target_value INTEGER NOT NULL,-- Ex: 1000, 10, 5
                icon TEXT                     -- Ex: '💣', '💧', '💬'
            )
        """)

        # 2. Le Traqueur Universel (Compteurs infinis)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS viewer_stats (
                twitch_id TEXT NOT NULL,
                stat_type TEXT NOT NULL,
                stat_value INTEGER DEFAULT 0,
                PRIMARY KEY (twitch_id, stat_type)
            )
        """)

        # 3. L'Armoire à Trophées (Ce que les viewers ont débloqué)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS viewer_trophies (
                twitch_id TEXT NOT NULL,
                trophy_id INTEGER NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (twitch_id, trophy_id),
                FOREIGN KEY (trophy_id) REFERENCES trophies(id)
            )
        """)

        # --- EXEMPLES D'INJECTION (Pour tester le système) ---
        trophees_exemples = [
            ("Bavard", "Envoyer 100 messages dans le chat", "messages_sent", 100, "💬"),
            ("Démineur Expert", "Désamorcer 10 bombes", "bomb_win", 10, "✂️"),
            ("Kamikaze", "Exploser 5 fois à la bombe", "bomb_loss", 5, "💥"),
            ("Soif de vaincre", "Acheter la récompense Hydratation 3 fois", "reward_hydration", 3, "💧"),
            ("Mécène", "Donner 1000 Bits au total", "bits_count", 1000, "💎")
        ]
        
        cursor.executemany("""
            INSERT OR IGNORE INTO trophies (name, description, stat_type, target_value, icon)
            VALUES (?, ?, ?, ?, ?)
        """, trophees_exemples)

        conn.commit()
        print("✨ Les tables 'trophies', 'viewer_stats' et 'viewer_trophies' sont prêtes !")
    except Exception as e:
        print(f"❌ Erreur SQL : {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    installer_moteur_trophees()
