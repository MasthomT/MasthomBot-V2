import re
import time
import aiohttp
import logging
import json
from datetime import datetime
from collections import defaultdict
from app.core.database import get_db_connection
from app.core.config import settings
from app.services.discord_service import send_message_to_discord

logger = logging.getLogger("masthbot.moderation")

# Récompenses de points de chaîne où poster un lien est ATTENDU (pas une infraction) — mais
# seulement si le lien correspond bien à la plateforme prévue pour cette récompense précise.
# Un lien d'une autre plateforme dans le message de redemption reste sanctionné normalement.
REWARD_LINK_RULES = {
    "6b4dc3d4-537b-4faa-a1cf-409de3e26224": ("twitch.tv",),          # On matte le clip de...
    "07ba86ad-1c62-4056-99ab-23d37a2ac231": ("twitch.tv",),          # Replay
    "093cceb1-3c5e-4e8e-bc16-7f27ff6a2d2b": ("tiktok.com",),         # TikTok Replay
}

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

    async def _log_to_discord_channel(self, username, action, reason):
        channel_id = settings.MODERATION_LOG_CHANNEL_ID
        if not channel_id:
            return
        action_label = {"delete": "Suppression", "timeout": "Timeout", "ban": "Bannissement"}.get(action, action)
        try:
            await send_message_to_discord(
                channel_id,
                f"🟣 **[TWITCH]** `{action_label}` — **{username}**\n↳ Raison : {reason}"
            )
        except Exception as e:
            logger.error(f"❌ [MODERATION] Échec envoi log salon modération : {e}")

    async def process_message(self, message_id, message, username, user_id, broadcaster_id, client_id, token, is_vip=False, reward_id=None):
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
            from app.services.twitch_service import _permitted_users
            if settings.get("links_enabled") and not is_vip and username.lower() not in _permitted_users:
                if self.link_pattern.search(message):
                    # Récompense de points de chaîne qui ATTEND un lien (ex: "TikTok Replay") :
                    # pas de sanction si le lien correspond bien à la plateforme prévue pour
                    # cette récompense précise — sinon (ex: lien YouTube dans "TikTok Replay"),
                    # on retombe sur la modération normale ci-dessous.
                    allowed_domains = REWARD_LINK_RULES.get(reward_id) if reward_id else None
                    if allowed_domains and any(d in text_lower for d in allowed_domains):
                        return False

                    # Whiteliste les clips Twitch (récompenses de chaîne)
                    is_twitch_clip = bool(re.search(
                        r'(clips\.twitch\.tv|twitch\.tv/\S+/clip/|twitch\.tv/clip/)',
                        message, re.IGNORECASE
                    ))
                    if not is_twitch_clip:
                        _permitted_users.discard(username.lower())
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
            await self._log_to_discord_channel(username, action, reason)
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
        except Exception as e:
            logger.error(f"❌ [MODERATION] Échec vérification follower pour user_id={user_id} : {e}")
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
