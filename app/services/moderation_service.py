import re
import time
import aiohttp
import sqlite3
import logging
import json
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("masthbot.moderation")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

class ModerationService:
    def __init__(self):
        self.recent_messages = defaultdict(list)
        # Regex améliorée pour détecter les points déguisés (dot, point, (dot), [dot], etc.)
        # Elle cherche un nom de domaine + un séparateur suspect + un TLD connu
        self.link_pattern = re.compile(
            r"(?i)\b(?:https?://)?(?:[a-z0-9\-]+(?:\s*(?:\.|\bdot\b|\bpoint\b|\[\.\]|\[dot\]|\(dot\))\s*)(?:com|fr|gg|tv|net|org|info|me|io|be|ch|ca|ru))\b"
        )

    def _get_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _log_to_dashboard(self, username, event_type, reason):
        """Enregistre la sanction pour qu'elle apparaisse dans le dashboard."""
        try:
            conn = self._get_db()
            details = {"reason": reason, "bot": "Félix"}
            conn.execute(
                "INSERT INTO stream_events (event_type, username, details, timestamp) VALUES (?, ?, ?, ?)",
                (event_type, username, json.dumps(details), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ Erreur log dashboard: {e}")

    async def process_message(self, message_id, message, username, user_id, broadcaster_id, client_id, token, is_vip=False):
        try:
            conn = self._get_db()
            settings_row = conn.execute("SELECT * FROM moderation_settings WHERE id=1").fetchone()
            banned_words_rows = conn.execute("SELECT word FROM banned_words").fetchall()
            conn.close()
            
            if not settings_row: return False

            # Conversion du Row SQLite en Dictionnaire pour utiliser .get() sans crash
            settings = dict(settings_row)

            banned_words = [row["word"].lower() for row in banned_words_rows]
            text_lower = message.lower()

            # 1. MOTS INTERDITS
            if settings.get("banned_words_enabled"):
                for word in banned_words:
                    if re.search(rf"\b{re.escape(word)}\b", text_lower):
                        await self._apply_matrix_sanction('words', settings, message_id, username, user_id, broadcaster_id, client_id, token, f"Mot Interdit ({word})")
                        return True

            # 2. LIENS NON AUTORISÉS (Détection Anti-Bypass active)
            if settings.get("links_enabled") and not is_vip:
                if self.link_pattern.search(message):
                    await self._apply_matrix_sanction('links', settings, message_id, username, user_id, broadcaster_id, client_id, token, "Lien non autorisé (tentative de bypass détectée)")
                    return True

            # 3. ABUS DE MAJUSCULES
            if settings.get("caps_enabled"):
                caps_min = settings.get("caps_min_length", 10)
                caps_pct = settings.get("caps_percent", 70) / 100.0
                
                alphas = [c for c in message if c.isalpha()]
                if len(alphas) >= caps_min:
                    caps = [c for c in alphas if c.isupper()]
                    if (len(caps) / len(alphas)) >= caps_pct:
                        await self._apply_matrix_sanction('caps', settings, message_id, username, user_id, broadcaster_id, client_id, token, "Abus de Majuscules")
                        return True

            # 4. SPAM (Personnalisé)
            if settings.get("spam_enabled"):
                spam_time = settings.get("spam_timeframe", 30)
                spam_lim = settings.get("spam_limit", 4)
                
                now = time.time()
                history = self.recent_messages[username]
                history = [msg for msg in history if now - msg['time'] < spam_time]
                
                history.append({'time': now, 'text': message})
                self.recent_messages[username] = history
                
                identical_count = sum(1 for msg in history if msg['text'].lower() == text_lower)
                
                if identical_count >= spam_lim:
                    await self._apply_matrix_sanction('spam', settings, message_id, username, user_id, broadcaster_id, client_id, token, "Spam de message")
                    return True

            return False

        except Exception as e:
            logger.error(f"❌ [MODERATION] Erreur analyse : {e}")
            return False

    async def _apply_matrix_sanction(self, rule_name, settings, message_id, username, user_id, broadcaster_id, client_id, token, reason):
        is_follower = await self._check_follower(user_id, broadcaster_id, client_id, token)
        target = 'f' if is_follower else 'nf'
        action = settings.get(f"{rule_name}_{target}_act")
        duration = settings.get(f"{rule_name}_{target}_dur", 0)

        # On définit le texte de la sanction pour TON historique
        if action == 'delete':
            full_reason = f"Suppression : {reason}"
        elif action == 'timeout':
            full_reason = f"Timeout ({duration}s) : {reason}"
        elif action == 'ban':
            duration = 0
            full_reason = f"Ban Définitif : {reason}"
        else: return

        # ON ENREGISTRE DANS L'HISTORIQUE ICI (Avec le gros mot s'il y en a un)
        self._log_to_dashboard(username, "sanction", full_reason)
        
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
                
                # 🛑 LE FIX EST ICI : On donne une raison "neutre" à l'API Twitch pour éviter qu'elle bloque le ban !
                safe_reason = "Violation des règles du chat (Sanction automatique - Félix)"
                
                payload = {"data": {"user_id": str(user_id), "reason": safe_reason}}
                if action_type == 'timeout': payload["data"]["duration"] = duration
                
                resp = await session.post(url, headers=headers, json=payload)
                
                # Petit log de sécurité pour vérifier que Twitch a bien accepté
                if resp.status >= 400:
                    err = await resp.text()
                    logger.error(f"❌ [MODERATION] Échec de la sanction Twitch sur {username} ({resp.status}): {err}")

moderation_service = ModerationService()
