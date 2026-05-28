import sqlite3
import asyncio
import asyncpg
import os

# --- CONFIGURATION ---
# Mets le nom de l'ancien fichier SQLite que tu veux vérifier (celui qui a les vieilles données)
SQLITE_FILE = "bot_database.db"

# Ta connexion PostgreSQL
POSTGRES_URL = "postgresql://thomas:Thomas.c1992@localhost/masthbot_db"

# Les tables principales de Félix
TABLES = [
    "viewers",
    "viewer_trophies",
    "viewer_daily_stats",
    "viewer_exp_log",
    "questions",
    "polls",
    "poll_votes",
    "settings"
]

async def compare_databases():
    print(f"🔍 Comparaison des bases de données...")
    print(f"📂 SQLite (Ancienne) : {SQLITE_FILE}")
    print(f"🐘 PostgreSQL (Nouvelle) : masthbot_db\n")

    # 1. Connexion SQLite
    if not os.path.exists(SQLITE_FILE):
        print(f"❌ Le fichier SQLite '{SQLITE_FILE}' est introuvable. Vérifie le chemin.")
        return
        
    sqlite_conn = sqlite3.connect(SQLITE_FILE)
    sqlite_cursor = sqlite_conn.cursor()

    # 2. Connexion PostgreSQL
    try:
        pg_conn = await asyncpg.connect(POSTGRES_URL)
    except Exception as e:
        print(f"❌ Erreur de connexion à PostgreSQL: {e}")
        return

    # 3. Affichage du tableau
    print(f"{'TABLE':<20} | {'SQLITE':<10} | {'POSTGRES':<10} | {'STATUT'}")
    print("-" * 55)

    for table in TABLES:
        # Check SQLite
        try:
            sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cursor.fetchone()[0]
        except sqlite3.OperationalError:
            sqlite_count = "Inconnue"

        # Check PostgreSQL
        try:
            pg_count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
        except asyncpg.exceptions.UndefinedTableError:
            pg_count = "Inconnue"

        # Comparaison
        if sqlite_count == pg_count:
            status = "✅ PARFAIT"
        elif isinstance(sqlite_count, int) and isinstance(pg_count, int) and pg_count > sqlite_count:
            status = "📈 OK (Nouvelles données)"
        else:
            status = "⚠️ ATTENTION (Manque des données ?)"

        print(f"{table:<20} | {str(sqlite_count):<10} | {str(pg_count):<10} | {status}")

    # Fermeture
    sqlite_conn.close()
    await pg_conn.close()
    print("\n🏁 Vérification terminée !")

if __name__ == "__main__":
    asyncio.run(compare_databases())
