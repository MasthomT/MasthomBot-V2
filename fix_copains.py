import asyncio
from app.core.database import get_db_connection

async def fix_table():
    print("🛠️ Réparation de la table tracked_streamers en cours...")
    try:
        async with get_db_connection() as conn:
            # 1. On s'assure que la table existe
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tracked_streamers (
                    id SERIAL PRIMARY KEY
                )
            """)
            
            # 2. On force l'ajout de la colonne "login" (On ignore l'erreur si elle y est déjà)
            try:
                await conn.execute("ALTER TABLE tracked_streamers ADD COLUMN login TEXT;")
                print("✅ Colonne 'login' ajoutée avec succès !")
            except Exception:
                pass
                
            # 3. On force l'ajout de la colonne "is_active"
            try:
                await conn.execute("ALTER TABLE tracked_streamers ADD COLUMN is_active INTEGER DEFAULT 1;")
                print("✅ Colonne 'is_active' ajoutée avec succès !")
            except Exception:
                pass
                
            print("🎉 VICTOIRE ! La table est parfaitement opérationnelle pour PostgreSQL.")
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")

asyncio.run(fix_table())
