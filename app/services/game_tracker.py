import sqlite3
import logging

DB_PATH = "bot_database.db"
logger = logging.getLogger("masthbot.games")

def record_bomb_result(twitch_id: str, username: str, won: bool):
    """
    Enregistre le résultat du jeu de la bombe.
    À appeler à la fin d'une partie.
    """
    column_to_update = "bombs_won" if won else "bombs_lost"
    
    try:
        conn = sqlite3.connect(DB_PATH)
        # On utilise COALESCE pour gérer le cas où la valeur serait NULL
        conn.execute(f"""
            UPDATE viewers 
            SET {column_to_update} = COALESCE({column_to_update}, 0) + 1 
            WHERE twitch_id = ?
        """, (twitch_id,))
        
        # Si la ligne n'a pas été modifiée (le viewer n'existe pas encore), on l'insère
        if conn.total_changes == 0:
            conn.execute(f"""
                INSERT INTO viewers (twitch_id, username, {column_to_update})
                VALUES (?, ?, 1)
            """, (twitch_id, username))
            
        conn.commit()
        conn.close()
        
        resultat = "survécu à" if won else "explosé sur"
        logger.info(f"💣 [JEU] {username} a {resultat} la bombe !")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'enregistrement de la bombe : {e}")
