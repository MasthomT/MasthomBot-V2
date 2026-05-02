import sqlite3

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def reparer_table_trophees():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # On tente d'ajouter la colonne
        cursor.execute("ALTER TABLE trophy_list ADD COLUMN description TEXT")
        conn.commit()
        print("✅ La colonne 'description' a été ajoutée à la table trophy_list !")
    except sqlite3.OperationalError:
        print("ℹ️ Tout va bien : la colonne 'description' existe déjà dans la base de données.")
    finally:
        conn.close()

if __name__ == "__main__":
    reparer_table_trophees()
