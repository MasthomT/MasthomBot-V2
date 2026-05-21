import asyncio
import os
import random
from dotenv import load_dotenv
from twitchio.ext import commands, routines
from datetime import datetime, timedelta

from app.core.auth import refresh_twitch_token
from app.core.database import get_db_connection

# --- 1. CHARGEMENT DES PARAMÈTRES ---
load_dotenv()

class MasthomBot(commands.Bot):
    def __init__(self):
        # 1. On récupère les identifiants actuels
        token = os.getenv('TWITCH_BOT_OAUTH_TOKEN')
        channel = os.getenv('TWITCH_USERNAME')

        # 2. Vérification de sécurité
        if not token or not channel:
            print("❌ [ERREUR CRITIQUE] TWITCH_BOT_OAUTH_TOKEN ou TWITCH_USERNAME est vide")
        
        # 3. DEBUG (Avant refresh)
        print(f"🔑 [DEBUG] Token actuel (fin) : ...{token[-4:] if token else 'VIDE'}")

        # --- AJOUT DU REFRESH AUTOMATIQUE ---
        new_token = asyncio.run(refresh_twitch_token('TWITCH_BOT_REFRESH_TOKEN', 'TWITCH_BOT_OAUTH_TOKEN'))
        if new_token:
            token = new_token
            print(f"🔄 [SYSTÈME] Token de Félix renouvelé avec succès.")
        # ------------------------------------

        print(f"👤 [DEBUG] Identité attendue : felixthebigblackcat")
        print(f"📡 [SYSTÈME] Félix tente de se connecter au salon : {channel}")

        super().__init__(
            token=token,
            prefix='!',
            initial_channels=[channel]
        )

    async def get_db_config(self):
        """Récupère tous les réglages de l'Admin en temps réel."""
        try:
            async with get_db_connection() as conn:
                c1 = await conn.execute("SELECT * FROM settings WHERE id = 1")
                settings = await c1.fetchone()
                
                c2 = await conn.execute("SELECT * FROM personality WHERE id = 1")
                personality = await c2.fetchone()

            s_dict = dict(settings) if settings else {}
            p_dict = dict(personality) if personality else {}
            return s_dict, p_dict
        except Exception as e:
            print(f"❌ [DB ERROR] Impossible de lire PostgreSQL : {e}")
            return {}, {}

    async def event_ready(self):
        print(f"🟢 [SUCCÈS] Félix est en ligne sur Twitch !")
        print(f"🐈 Nom du bot : {self.nick}")
        # Démarrage de la routine d'annonces
        self.announcement_check.start()

    async def event_message(self, message):
        # --- SÉCURITÉ : Ignorer ses propres messages ---
        if message.author is None or message.author.name.lower() == self.nick.lower():
            return

        # --- LOG DE RÉCEPTION ---
        print(f"📩 [MESSAGE] {message.author.name}: {message.content}")

        # 👇 CORRECTION DU BUG D'INDENTATION ICI 👇
        twitch_id = str(message.author.id)
        username = message.author.name
        content = message.content

        # 1. Compteur d'emotes exclusives de la chaîne ("mastho2")
        emotes_in_message = 0
        mots = content.split()
        for mot in mots:
            if mot.startswith("mastho2"):
                emotes_in_message += 1

        try:
            # 2. Mise à jour de la base de données (PostgreSQL Asynchrone)
            async with get_db_connection() as db:
                
                # --- A. TABLE 'viewers' (STATISTIQUES GLOBALES) ---
                await db.execute("""
                    INSERT INTO viewers (twitch_id, username, messages, emotes_count, streak_days, last_active_date)
                    VALUES ($1, $2, 1, $3, 1, CURRENT_DATE)
                    ON CONFLICT(twitch_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        messages = viewers.messages + 1,
                        emotes_count = viewers.emotes_count + $4,
                        streak_days = CASE
                            WHEN viewers.last_active_date = CURRENT_DATE - INTERVAL '1 day' THEN viewers.streak_days + 1
                            WHEN viewers.last_active_date < CURRENT_DATE - INTERVAL '1 day' THEN 1
                            ELSE viewers.streak_days
                        END,
                        last_active_date = CURRENT_DATE
                """, (twitch_id, username, emotes_in_message, emotes_in_message))

                # --- B. TABLE 'viewer_daily_stats' (STATISTIQUES DE SESSION) ---
                await db.execute("""
                    INSERT INTO viewer_daily_stats (twitch_id, day, messages)
                    VALUES ($1, CURRENT_DATE, 1)
                    ON CONFLICT(twitch_id, day) DO UPDATE SET
                        messages = viewer_daily_stats.messages + 1
                """, (twitch_id,))
                
        except Exception as e:
            print(f"❌ [DB ERROR] Erreur lors de l'enregistrement des stats de {username}: {e}")

        # 1. Lecture de la base de données
        settings, personality = await self.get_db_config()
        if not settings or not personality:
            print("⚠️ [SKIP] Erreur de lecture des réglages (Base de données vide ?)")
            return

        # 2. Vérification des interrupteurs Admin
        if settings.get('ai_enabled') != 1:
            print("🚫 [LOG] IA désactivée dans l'administration.")
            return
        
        if settings.get('enable_twitch') != 1:
            print("🚫 [LOG] Félix a reçu l'ordre de ne pas répondre sur Twitch.")
            return

        # 3. Logique de décision (Mention ou Probabilité)
        is_mentioned = self.nick.lower() in message.content.lower()
        chance = random.randint(1, 100)
        taux = personality.get('intervention_rate', 10)

        if is_mentioned or chance <= taux:
            print(f"🤖 [ACTION] Félix a décidé de répondre (Chance: {chance}/{taux})")
            
            # 4. Génération de la réponse via l'IA
            response = await self.generate_ai_response(message.content, message.author.name)
            
            if response:
                await message.channel.send(response)
                print(f"📤 [TWITCH] Réponse envoyée !")
        else:
            print(f"💤 [SKIP] Félix ignore ce message (Probabilité : {chance} > {taux})")

    async def generate_ai_response(self, user_message, username):
        """Construit le prompt final et appelle l'IA."""
        settings, personality = await self.get_db_config()

        length_map = {
            "tres_courte": "Réponds en moins de 10 mots. Très sec.",
            "courte": "Fais une seule phrase courte.",
            "normale": "Fais 2 à 3 phrases maximum.",
            "detaillee": "Fais un paragraphe détaillé et complet."
        }
        instruction_longueur = length_map.get(settings.get('response_length', 'normale'), "Sois concis.")

        print(f"🔥 [IA CONFIG] Tonalité : {settings.get('selected_tone')}")

        try:
            return f"@{username}, [MODE {str(settings.get('selected_tone', 'neutre')).upper()}] Je t'écoute, mais branche mon API pour que je parle vraiment !"
        except Exception as e:
            print(f"❌ [ERREUR IA] : {e}")
            return None

    @routines.routine(minutes=1)
    async def announcement_check(self):
        stream_data = await self.fetch_streams(user_logins=[self.initial_channels[0]])
        if not stream_data:
            return

        try:
            now = datetime.now()
            async with get_db_connection() as conn:
                c = await conn.execute("SELECT * FROM announcements WHERE trigger_type = 'interval' AND is_enabled = 1")
                all_anns = await c.fetchall()

                for ann in all_anns:
                    last_sent = ann['last_triggered'] if 'last_triggered' in ann.keys() else None
                    if last_sent and isinstance(last_sent, str):
                        last_sent = datetime.fromisoformat(last_sent.replace(' ', 'T'))

                    interval = ann['interval_minutes']
                    if not last_sent or now >= last_sent + timedelta(minutes=interval):
                        await self.send_formatted_announcement(dict(ann), conn)
        except Exception as e:
            print(f"❌ [ROUTINE ERROR] {e}")

    async def send_formatted_announcement(self, ann, conn):
        message = ann['message_template']
        chan = self.get_channel(self.initial_channels[0])
        if chan:
            message = message.replace("{viewers}", "0")
            message = message.replace("{game}", "En Live")
            message = message.replace("{uptime}", "En cours")
            
            await chan.send(message)
            # Mise à jour dans PostgreSQL
            await conn.execute("UPDATE announcements SET last_triggered = $1 WHERE id = $2", (datetime.now(), ann['id']))

# Lancement automatique pour test
if __name__ == "__main__":
    bot = MasthomBot()
    bot.run()
