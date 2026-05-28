import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def execute():
    print("🚀 ON PASSE EN FORCE BRUTE !")
    
    # On importe le service qu'on vient tout juste de réparer
    from app.services.notification_service import notification_service
    
    channel_id = None
    msg = None
    try:
        from app.core.database import get_db_connection
        async with get_db_connection() as conn:
            # On tente de récupérer la configuration
            cursor = await conn.execute("SELECT * FROM settings LIMIT 1")
            settings = await cursor.fetchone()
            if settings:
                if not isinstance(settings, dict):
                    settings = dict(settings)
                channel_id = settings.get("discord_channel_id") or settings.get("discord_announce_channel") or settings.get("discord_room_id")
                msg = settings.get("discord_notify_message")
    except Exception as e:
        print("⚠️ Bypass de la base de données...")

    # Si la base est verrouillée, on te demande l'ID en direct
    if not channel_id:
        print("\n👉 Clic droit sur ton salon Discord d'annonce -> Copier l'ID du salon")
        channel_id = input("Colle l'ID ici : ").strip()
        
    if not msg:
        msg = "@everyone 🔴 masthom_ est en live sur {game} ! Venez vite ici : {lien}"

    # Le script te demande le jeu actuel
    game = input("\n🎮 Tape le jeu auquel tu joues là maintenant (ex: Just Chatting) : ").strip()
    
    print("\n🔥 ENVOI DE LA NOTIFICATION...")
    await notification_service.send_discord_live_notification(
        channel_id=channel_id,
        channel_name="masthom_",
        title="🔴 Stream en cours !",
        game=game,
        custom_message=msg
    )
    print("✅✅✅ C'EST PARTI ! BON LIVE PUTAIN !")

if __name__ == "__main__":
    asyncio.run(execute())
