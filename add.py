import sqlite3

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def upgrade():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE viewers ADD COLUMN last_web_login TIMESTAMP")
        print("✅ SUCCÈS : Colonne 'last_web_login' ajoutée à la base de données !")
    except Exception as e:
        print(f"⚠️ La colonne existe probablement déjà : {e}")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    upgrade()
