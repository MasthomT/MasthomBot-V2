import sqlite3

db_path = "/home/masthom/BOT_V2/bot_database.db"

def fix():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print("🛠️ Reconstruction chirurgicale de la base de données...")

    # 1. MODÉRATION & MOTS BANNIS
    cursor.execute('CREATE TABLE IF NOT EXISTS moderation_settings (id INTEGER PRIMARY KEY, caps_lock_enabled BOOLEAN DEFAULT 0, links_allowed BOOLEAN DEFAULT 1, banned_words TEXT DEFAULT "")')
    cursor.execute("INSERT OR IGNORE INTO moderation_settings (id) VALUES (1)")
    cursor.execute('CREATE TABLE IF NOT EXISTS banned_words (id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT UNIQUE NOT NULL)')

    # 2. SONDAGES (Avec la colonne is_active réclamée par les logs)
    cursor.execute('CREATE TABLE IF NOT EXISTS polls (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, options TEXT NOT NULL, status TEXT DEFAULT "active", is_active BOOLEAN DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    try: cursor.execute("ALTER TABLE polls ADD COLUMN is_active BOOLEAN DEFAULT 1")
    except: pass

    # 3. TROPHÉES (Table de liste + Table des gains des viewers)
    cursor.execute('CREATE TABLE IF NOT EXISTS trophy_list (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, description TEXT, icon TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS viewer_trophies (twitch_id TEXT, trophy_id INTEGER, awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(twitch_id, trophy_id))')

    # 4. STATS & ÉVÉNEMENTS (Avec event_type réclamé par les logs)
    cursor.execute('CREATE TABLE IF NOT EXISTS stream_events (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, event_type TEXT, user TEXT, details TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    try: cursor.execute("ALTER TABLE stream_events ADD COLUMN event_type TEXT")
    except: pass

    # 5. VIP & COLONNES VIEWERS
    try: cursor.execute("ALTER TABLE viewers ADD COLUMN is_vip BOOLEAN DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE viewers ADD COLUMN vip_expiry TIMESTAMP")
    except: pass
    try: cursor.execute("ALTER TABLE viewers ADD COLUMN roast_level INTEGER DEFAULT 0")
    except: pass

    # 6. ANNONCES
    cursor.execute('CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, message TEXT NOT NULL, interval INTEGER DEFAULT 15, is_active BOOLEAN DEFAULT 1)')

    conn.commit()
    conn.close()
    print("✅ Réparation terminée ! Toutes les tables et colonnes sont là.")

if __name__ == "__main__":
    fix()

