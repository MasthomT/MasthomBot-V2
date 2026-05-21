import logging
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.games")

async def record_bomb_result(twitch_id: str, username: str, won: bool):
    """
    Enregistre le résultat du jeu de la bombe.
    À appeler à la fin d'une partie.
    """
    column_to_update = "bombs_won" if won else "bombs_lost"
    
    try:
        async with get_db_connection() as conn:
            # PostgreSQL permet d'insérer ou mettre à jour en 1 seule requête magique !
            await conn.execute(f"""
                INSERT INTO viewers (twitch_id, username, {column_to_update})
                VALUES ($1, $2, 1)
                ON CONFLICT(twitch_id) DO UPDATE 
                SET {column_to_update} = COALESCE(viewers.{column_to_update}, 0) + 1,
                    username = EXCLUDED.username
            """, (str(twitch_id), username))
            
        resultat = "survécu à" if won else "explosé sur"
        logger.info(f"💣 [JEU] {username} a {resultat} la bombe !")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'enregistrement de la bombe : {e}")
