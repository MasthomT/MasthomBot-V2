import sqlite3
import os

DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def init_questions():
    print("🛠️ Création de la table des questions...")
    conn = sqlite3.connect(DB_PATH)
    
    # Table qui stocke les questions des viewers
    conn.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twitch_id TEXT,
            username TEXT,
            question_text TEXT NOT NULL,
            answer_text TEXT,
            is_public INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            answered_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ SUCCÈS : Base de données prête pour le système de Questions/Réponses !")

if __name__ == "__main__":
    init_questions()
