import asyncio
import sqlite3
import os
from app.core.database import get_db_connection

SQLITE_PATH = "/home/thomas/masthom/BOT_V2/bot_database.db"

async def migration_annonces():
    print("🔍 [ASPIRATEUR] Recherche des anciennes annonces...")

    if not os.path.exists(SQLITE_PATH):
        print(f"❌ [ERREUR] Impossible de trouver l'ancienne base SQLite ici : {SQLITE_PATH}")
        return

    # 1. Extraction depuis SQLite
    annonces_extraites = []
    try:
        conn_sqlite = sqlite3.connect(SQLITE_PATH)
        conn_sqlite.row_factory = sqlite3.Row
        
        # On essaie d'abord la nouvelle nomenclature, puis l'ancienne
        try:
            cursor = conn_sqlite.execute("SELECT * FROM announcements")
        except sqlite3.OperationalError:
            cursor = conn_sqlite.execute("SELECT * FROM auto_announcements")
            
        rows = cursor.fetchall()
        for r in rows:
            annonces_extraites.append(dict(r))
            
        conn_sqlite.close()
        print(f"📋 [SQLITE] {len(annonces_extraites)} annonces trouvées !")
        
    except Exception as e:
        print(f"❌ [ERREUR SQLITE] Impossible de lire les annonces : {e}")
        return

    if not annonces_extraites:
        print("⚠️ [INFO] L'ancienne table semble vide. Rien à migrer.")
        return

    # 2. Injection dans PostgreSQL
    print("🚀 [POSTGRESQL] Injection des annonces dans le nouveau moteur...")
    try:
        async with get_db_connection() as conn_pg:
            # Sécurité : on s'assure que la table pg est bien créée avec toutes ses colonnes
            await conn_pg.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    label TEXT NOT NULL,
                    message_template TEXT NOT NULL,
                    trigger_type TEXT DEFAULT 'interval',
                    interval_minutes INTEGER DEFAULT 30,
                    group_name TEXT,
                    last_triggered TIMESTAMP,
                    is_enabled INTEGER DEFAULT 1
                )
            """)
            
            succes_count = 0
            for ann in annonces_extraites:
                label = ann.get('label', 'Annonce importée')
                msg = ann.get('message_template', '')
                trigger = ann.get('trigger_type', 'interval')
                interval = ann.get('interval_minutes', 30)
                group = ann.get('group_name', '')
                is_enabled = ann.get('is_enabled', 1)

                if not msg:
                    continue # On ignore les annonces vides

                await conn_pg.execute("""
                    INSERT INTO announcements (label, message_template, trigger_type, interval_minutes, group_name, is_enabled)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, (label, msg, trigger, interval, group, is_enabled))
                
                succes_count += 1
                
        print(f"🎉 [VICTOIRE] {succes_count} annonces ont été téléportées avec succès dans PostgreSQL !")
        
    except Exception as e:
        print(f"❌ [ERREUR POSTGRESQL] Échec de l'injection : {e}")

if __name__ == "__main__":
    asyncio.run(migration_annonces())
