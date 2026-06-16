import logging
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.premium")

class PremiumService:
    """Service dédié à la gestion des actions interactives Premium."""

    async def get_all_actions(self):
        try:
            async with get_db_connection() as conn:
                cursor = await conn.execute("SELECT * FROM premium_actions ORDER BY id ASC")
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération de toutes les actions : {e}")
            return []

    async def get_active_actions(self):
        try:
            async with get_db_connection() as conn:
                cursor = await conn.execute("SELECT * FROM premium_actions WHERE is_active = 1 ORDER BY id ASC")
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des actions actives : {e}")
            return []

    async def toggle_action_status(self, action_id: int, is_active: int):
        try:
            async with get_db_connection() as conn:
                await conn.execute(
                    "UPDATE premium_actions SET is_active = $1 WHERE id = $2", 
                    (is_active, action_id)
                )
                logger.info(f"🔄 Statut de l'action #{action_id} passé à {is_active}.")
                return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de la mise à jour de l'action #{action_id} : {e}")
            return False

    async def add_action(self, name: str, icon: str, action_type: str, action_value: str):
        """
        Ajoute une nouvelle action Premium dans la base de données.
        Elle sera active par défaut (is_active = 1).
        """
        try:
            async with get_db_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO premium_actions (name, icon, action_type, action_value, is_active) 
                    VALUES ($1, $2, $3, $4, 1)
                    """,
                    (name, icon, action_type, action_value)
                )
                logger.info(f"✅ Nouvelle action ajoutée : {name} ({action_type})")
                return True
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'ajout de l'action : {e}")
            return False

premium_service = PremiumService()
