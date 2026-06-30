import os
import logging
import json
import dotenv
import aiohttp
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger("masthbot.notifications")

class NotificationService:
    def __init__(self):
        self.base_url = "https://discord.com/api/v10"

    def _get_fresh_bot_token(self):
        """Récupère le token à jour DIRECTEMENT depuis le fichier .env (évite le cache mémoire)"""
        env_vars = dotenv.dotenv_values(".env")
        raw_token = env_vars.get("DISCORD_TOKEN", "")
        if not raw_token:
            return ""
        # Nettoyage de sécurité
        return raw_token.split(' ')[0].split('#')[0].strip()

    async def send_discord_live_notification(self, channel_id, channel_name, title, game, custom_message=None):
        """Demande à FEL-X d'envoyer la carte de live et RETOURNE l'ID du message."""

        bot_token = self._get_fresh_bot_token()

        if not bot_token:
            logger.error("❌ [FEL-X] Impossible d'envoyer la notif : DISCORD_TOKEN introuvable dans le .env !")
            return None

        if not channel_id:
            logger.error(f"❌ [FEL-X] Impossible d'envoyer la notif pour {channel_name} : ID de salon manquant.")
            return None

        # URL de l'API Discord officielle
        url = f"{self.base_url}/channels/{channel_id}/messages"

        # En-têtes pour s'identifier en tant que FEL-X
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }

        # --- INTÉGRATION DE LA CATÉGORIE ---
        safe_game = game if game else "Just Chatting"
        
        if custom_message:
            msg_content = custom_message.replace("{CATEGORIE}", safe_game)
            msg_content = msg_content.replace("{game}", safe_game)
            msg_content = msg_content.replace("{lien}", f"https://twitch.tv/{channel_name}")
        else:
            msg_content = f"💜 **{channel_name}** est en direct, foncez lui donner de la force !"

        # Construction de l'Embed
        payload = {
            "content": msg_content,
            "embeds": [
                {
                    "title": title or "Stream en cours !",
                    "url": f"https://twitch.tv/{channel_name}",
                    "color": 9520895,
                    "author": {
                        "name": f"{channel_name} est en direct !",
                        "url": f"https://twitch.tv/{channel_name}"
                    },
                    "fields": [
                        {
                            "name": "🎮 Jeu",
                            "value": safe_game,
                            "inline": True
                        }
                    ],
                    "image": {
                        # Ajout d'un timestamp aléatoire pour forcer Discord à recharger la miniature
                        "url": f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{channel_name.lower()}-1280x720.jpg?t={os.urandom(4).hex()}"
                    }
                }
            ]
        }

        # Ordre d'envoi à Discord
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        message_id = data.get("id")
                        logger.info(f"✅ [FEL-X] Message posté pour {channel_name} ! (ID: {message_id})")
                        # TRÈS IMPORTANT : On retourne l'ID pour que live_monitor.py puisse le mémoriser
                        return str(message_id) 
                    else:
                        error_text = await resp.text()
                        logger.error(f"❌ [FEL-X] Discord a refusé le message ({resp.status}) : {error_text}")
                        return None
        except Exception as e:
            logger.error(f"❌ [FEL-X] Crash critique lors de la connexion à Discord : {e}")
            return None

    async def send_discord_image(self, channel_id, image_bytes, filename, content=""):
        """Envoie une image en pièce jointe sur un salon Discord (ex: photos Polaroïd)."""
        bot_token = self._get_fresh_bot_token()

        if not bot_token or not channel_id:
            logger.error("❌ [FEL-X] Impossible d'envoyer l'image : token ou channel ID manquant.")
            return None

        url = f"{self.base_url}/channels/{channel_id}/messages"
        headers = {"Authorization": f"Bot {bot_token}"}

        form = aiohttp.FormData()
        form.add_field("payload_json", json.dumps({"content": content}), content_type="application/json")
        form.add_field("files[0]", image_bytes, filename=filename, content_type="image/png")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=form) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        logger.info(f"✅ [FEL-X] Image envoyée sur le salon {channel_id} (ID: {data.get('id')}).")
                        return data.get("id")
                    else:
                        error_text = await resp.text()
                        logger.error(f"❌ [FEL-X] Discord a refusé l'image ({resp.status}) : {error_text}")
                        return None
        except Exception as e:
            logger.error(f"❌ [FEL-X] Crash critique lors de l'envoi de l'image : {e}")
            return None

    async def delete_discord_message(self, channel_id, message_id):
        """Supprime un message précis sur Discord (idéal pour nettoyer quand le live se termine)."""
        bot_token = self._get_fresh_bot_token()
        
        if not bot_token or not channel_id or not message_id:
            return False

        url = f"{self.base_url}/channels/{channel_id}/messages/{message_id}"
        headers = {"Authorization": f"Bot {bot_token}"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as resp:
                    if resp.status == 204:
                        logger.info(f"🗑️ [FEL-X] Carte de notification {message_id} supprimée car le live est terminé.")
                        return True
                    else:
                        logger.warning(f"⚠️ [FEL-X] Impossible de supprimer la carte {message_id} ({resp.status}).")
                        return False
        except Exception as e:
            logger.error(f"❌ [FEL-X] Crash lors de la suppression sur Discord : {e}")
            return False

    async def send_faq_public_answer(self, question_text, answer_text):
        """Publie la réponse de Félix sur le salon Discord dédié."""
        bot_token = self._get_fresh_bot_token()
        channel_id = settings.FAQ_CHANNEL_ID

        if not bot_token or not channel_id:
            logger.error("❌ [FAQ DISCORD] Token ou Channel ID manquant.")
            return

        url = f"{self.base_url}/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }

        # Construction de la carte "Bien décorée"
        payload = {
            "embeds": [
                {
                    "title": "🐾 Félix a répondu à une question !",
                    "color": 62965, # Le vert/cyan signature de FEL-X
                    "fields": [
                        {
                            "name": "❓ Question Anonyme",
                            "value": f"*{question_text}*",
                            "inline": False
                        },
                        {
                            "name": "💡 La réponse de Félix",
                            "value": answer_text,
                            "inline": False
                        }
                    ],
                    "footer": {
                        "text": "FAQ FEL-X",
                        "icon_url": "https://static-cdn.jtvnw.net/emoticons/v2/emotesv2_fb54848601664188a109a909403a3d5f/default/dark/3.0"
                    },
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    logger.info("✅ [FAQ DISCORD] Réponse publiée avec succès.")
                else:
                    logger.error(f"❌ [FAQ DISCORD] Erreur d'envoi : {resp.status}")

    async def send_special_stream_notification(self, channel_id, title, date, time):
        """Envoie une notification spécifique pour un Live Spécial."""
        bot_token = self._get_fresh_bot_token()

        if not bot_token or not channel_id:
            logger.error("❌ [FEL-X] Impossible d'envoyer la notif spéciale : token ou channel manquant.")
            return

        url = f"{self.base_url}/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }

        # Embed avec couleur ambre/or pour le côté "Spécial"
        payload = {
            "content": "🚨 **STREAM SPÉCIAL À VENIR !** 🚨",
            "embeds": [
                {
                    "title": f"📅 {title}",
                    "color": 16766720, 
                    "fields": [
                        {"name": "🗓️ Date", "value": date, "inline": True},
                        {"name": "⏰ Heure", "value": time, "inline": True}
                    ]
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status in (200, 201):
                    logger.info(f"✅ [FEL-X] Notif spéciale envoyée : {title}")
                else:
                    logger.error(f"❌ [FEL-X] Erreur Discord spéciale ({resp.status})")

notification_service = NotificationService()
