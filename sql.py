import sqlite3

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def blinder_base_de_donnees():
    print("🚀 Ajout des colonnes exhaustives (Chat, IA, Jeux, Sessions)...")
    
    # La liste absolue de TOUTES les stats de ton menu HTML
    colonnes = [
        ("points_session", "INTEGER DEFAULT 0"),
        ("watchtime_session", "INTEGER DEFAULT 0"),
        ("streak_days", "INTEGER DEFAULT 0"),
        ("messages_session", "INTEGER DEFAULT 0"),
        ("emotes_global", "INTEGER DEFAULT 0"),
        ("commands_global", "INTEGER DEFAULT 0"),
        ("gifts_session", "INTEGER DEFAULT 0"),
        ("gamble_won", "INTEGER DEFAULT 0"),
        ("ai_prompts", "INTEGER DEFAULT 0"),
        ("bombs_won", "INTEGER DEFAULT 0"),
        ("bombs_lost", "INTEGER DEFAULT 0"),
        ("rewards_claimed", "INTEGER DEFAULT 0")
    ]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    compteur = 0
    for nom_col, type_col in colonnes:
        try:
            cursor.execute(f"ALTER TABLE viewers ADD COLUMN {nom_col} {type_col}")
            print(f"✅ Nouvelle stat ajoutée : {nom_col}")
            compteur += 1
        except sqlite3.OperationalError:
            pass # La colonne existe déjà, on ignore silencieusement
            
    conn.commit()
    conn.close()
    print(f"✨ Base de données blindée ! ({compteur} colonnes créées)")

if __name__ == "__main__":
    blinder_base_de_donnees()
