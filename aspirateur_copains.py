import asyncio
import sqlite3
import os
from app.core.database import get_db_connection

SQLITE_PATH = "/home/thomas/masthom/BOT_V2/bot_database.db"

async def migration_flemme():
    print("🔍 [ASPIRATEUR] Démarrage du pompage de données...")
    
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ [ERREUR] Impossible de trouver l'ancienne base SQLite ici : {SQLITE_PATH}")
        return

    # 1. Extraction depuis SQLite
    copains_extraits = []
    try:
        conn_sqlite = sqlite3.connect(SQLITE_PATH)
        conn_sqlite.row_factory = sqlite3.Row
        
        # On récupère tout le contenu de l'ancienne table
        cursor = conn_sqlite.execute("SELECT * FROM tracked_streamers")
        rows = cursor.fetchall()
        
        for r in rows:
            d = dict(r)
            # Détection intelligente du pseudo selon le nom de l'ancienne colonne
            pseudo = d.get('login') or d.get('username') or d.get('name') or d.get('streamer')
            if not pseudo and len(r) > 1:
                pseudo = r[1]  # Fallback sur la deuxième colonne si tout échoue
                
            if pseudo:
                is_active = d.get('is_active', 1)
                copains_extraits.append((str(pseudo).lower().strip(), is_active))
                
        conn_sqlite.close()
        print(f"📋 [SQLITE] {len(copains_extraits)} copains aspirés avec succès !")
        
    except Exception as e:
        print(f"❌ [ERREUR SQLITE] Impossible de lire l'ancienne table : {e}")
        return

    if not copains_extraits:
        print("⚠️ [INFO] L'ancienne table SQLite semble vide. Rien à migrer.")
        return

    # 2. Injection de force dans PostgreSQL
    print("🚀 [POSTGRESQL] Injection des copains dans la nouvelle base...")
    try:
        async with get_db_connection() as conn_pg:
            # On s'assure d'abord qu'il y a une contrainte d'unicité pour éviter les doublons
            try:
                await conn_pg.execute("ALTER TABLE tracked_streamers ADD CONSTRAINT unique_login UNIQUE (login);")
            except Exception:
                pass # Déjà existante ou impossible, pas grave
                
            succes_count = 0
            for pseudo, is_active in copains_extraits:
                # Le ON CONFLICT évite les crashs si tu as déjà rajouté un pote manuellement
                await conn_pg.execute("""
                    INSERT INTO tracked_streamers (login, is_active)
                    VALUES ($1, $2)
                    ON CONFLICT (login) DO UPDATE SET is_active = EXCLUDED.is_active
                """, (pseudo, is_active))
                succes_count += 1
                
        print(f"🎉 [VICTOIRE] {succes_count} copains ont été téléportés dans PostgreSQL !")
        
    except Exception as e:
        print(f"❌ [ERREUR POSTGRESQL] Échec de l'injection : {e}")

if __name__ == "__main__":
    asyncio.run(migration_flemme())
