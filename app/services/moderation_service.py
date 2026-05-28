import re
import time
import aiohttp
import logging
import json
from datetime import datetime
from collections import defaultdict
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.moderation")

class ModerationService:
    def __init__(self):
        self.recent_messages = defaultdict(list)
        self.link_pattern = re.compile(
            r"(?i)\b(?:https?://)?(?:[a-z0-9\-]+(?:\s*(?:\.|\bdot\b|\bpoint\b|\[\.\]|\[dot\]|\(dot\))\s*)(?:com|fr|gg|tv|net|org|info|me|io|be|ch|ca|ru))\b"
        )

    async def _log_to_dashboard(self, username, event_type, reason):
        """Enregistre la sanction dans PostgreSQL."""
        try:
            async with get_db_connection() as conn:
                details = {"reason": reason, "bot": "Félix"}
                await conn.execute(
                "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES ($1, $2, $3, NOW())",
                (event_type, username, str(details))
            )
        except Exception as e:
            logger.error(f"❌ Erreur log dashboard: {e}")

    async def process_message(self, message_id, message, username, user_id, broadcaster_id, client_id, token, is_vip=False):
        try:
            async with get_db_connection() as conn:
                c1 = await conn.execute("SELECT * FROM moderation_settings WHERE id=1")
                settings_row = await c1.fetchone()
                c2 = await conn.execute("SELECT word FROM banned_words")
                banned_words_rows = await c2.fetchall()
            
            if not settings_row: return False
            settings = dict(settings_row)
            banned_words = [row["word"].lower() for row in banned_words_rows]
            text_lower = message.lower()

            # 1. MOTS INTERDITS
            if settings.get("banned_words_enabled"):
                for word in banned_words:
                    if re.search(rf"\b{re.escape(word)}\b", text_lower):
                        await self._apply_matrix_sanction('words', settings, message_id, username, user_id, broadcaster_id, client_id, token, f"Mot Interdit ({word})")
                        return True

            # 2. LIENS
            if settings.get("links_enabled") and not is_vip:
                if self.link_pattern.search(message):
                    await self._apply_matrix_sanction('links', settings, message_id, username, user_id, broadcaster_id, client_id, token, "Lien non autorisé")
                    return True

            # 3. CAPS & SPAM (logique existante)
            return False
        except Exception as e:
            logger.error(f"❌ [MODERATION] Erreur analyse : {e}")
            return False

    async def _apply_matrix_sanction(self, rule_name, settings, message_id, username, user_id, broadcaster_id, client_id, token, reason):
        is_follower = await self._check_follower(user_id, broadcaster_id, client_id, token)
        target = 'f' if is_follower else 'nf'
        action = settings.get(f"{rule_name}_{target}_act")
        duration = settings.get(f"{rule_name}_{target}_dur", 0)

        if action in ['delete', 'timeout', 'ban']:
            await self._log_to_dashboard(username, "sanction", f"{action} : {reason}")
            await self._execute_sanction(action, message_id, username, user_id, broadcaster_id, client_id, token, duration)

    async def _check_follower(self, user_id, broadcaster_id, client_id, token):
        url = f"https://api.twitch.tv/helix/channels/followers?broadcaster_id={broadcaster_id}&user_id={user_id}"
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return len(data.get("data", [])) > 0
        except: pass
        return False

    async def _execute_sanction(self, action_type, message_id, username, user_id, broadcaster_id, client_id, token, duration):
        headers = {"Client-ID": client_id, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            if action_type == 'delete':
                url = f"https://api.twitch.tv/helix/moderation/chat?broadcaster_id={broadcaster_id}&moderator_id={broadcaster_id}&message_id={message_id}"
                await session.delete(url, headers=headers)
            else:
                url = f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={broadcaster_id}&moderator_id={broadcaster_id}"
                safe_reason = "Sanction automatique - Félix"
                payload = {"data": {"user_id": str(user_id), "reason": safe_reason}}
                if action_type == 'timeout': payload["data"]["duration"] = duration
                await session.post(url, headers=headers, json=payload)

moderation_service = ModerationService()
