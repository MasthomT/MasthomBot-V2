import sqlite3

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def mettre_a_jour_schema():
    print("🚀 Vérification et mise à jour de la base de données...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Liste des colonnes de trophées à garantir
        colonnes_a_ajouter = [
            ("sub_months", "INTEGER DEFAULT 0"),
            ("gifts_count", "INTEGER DEFAULT 0"),
            ("bits_count", "INTEGER DEFAULT 0")
        ]
        
        for nom_col, type_col in colonnes_a_ajouter:
            try:
                cursor.execute(f"ALTER TABLE viewers ADD COLUMN {nom_col} {type_col}")
                print(f"✅ Colonne '{nom_col}' ajoutée avec succès !")
            except sqlite3.OperationalError:
                print(f"ℹ️ La colonne '{nom_col}' existe déjà. Tout est parfait.")
                
        conn.commit()
        print("✨ La base de données est prête pour EventSub !")
        
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour : {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    mettre_a_jour_schema()
