import asyncio
import asyncpg
import dotenv

async def fix_vips():
    print("🛠️ Récupération des clés dans le .env...")
    env_vars = dotenv.dotenv_values(".env")
    db_url = env_vars.get("DATABASE_URL")
    
    if not db_url:
        print("❌ Erreur : DATABASE_URL introuvable dans le .env")
        return

    print("🔌 Connexion directe à PostgreSQL...")
    conn = await asyncpg.connect(db_url)
    
    try:
        # 1. On s'assure que la colonne existe
        await conn.execute("ALTER TABLE viewers ADD COLUMN IF NOT EXISTS vip_expiry TIMESTAMP;")
        
        # 2. On transfère les données
        await conn.execute("""
            UPDATE viewers 
            SET vip_expiry = vip_expiry_date::timestamp 
            WHERE vip_expiry IS NULL AND vip_expiry_date IS NOT NULL
        """)
        print("✅ VICTOIRE ! La base de données des VIP est unifiée et réparée.")
    except Exception as e:
        print(f"⚠️ Erreur lors de la requête : {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_vips())
