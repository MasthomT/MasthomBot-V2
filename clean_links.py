import asyncio
from app.core.database import get_db_connection

async def update_links():
    print("🧹 Nettoyage des liens Vercel dans la base de données...")
    try:
        async with get_db_connection() as conn:
            await conn.execute("""
                UPDATE auto_announcements 
                SET message = REPLACE(message, 'https://fel-x.vercel.app', 'https://fel-x.netlify.app')
            """)
            await conn.execute("""
                UPDATE announcements 
                SET message = REPLACE(message, 'https://fel-x.vercel.app', 'https://fel-x.netlify.app')
            """)
            await conn.execute("""
                UPDATE questions 
                SET answer_text = REPLACE(answer_text, 'https://fel-x.vercel.app', 'https://fel-x.netlify.app')
            """)
        print("✅ Tous les liens ont été mis à jour vers https://fel-x.netlify.app !")
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    asyncio.run(update_links())
