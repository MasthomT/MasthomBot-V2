import os
import sqlite3
import random
from dotenv import load_dotenv
from twitchio.ext import commands

from app.core.auth import refresh_twitch_token

# --- 1. CHARGEMENT DES PARAMÈTRES ---
load_dotenv()

# Configuration des chemins pour trouver la DB à la racine du projet
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Remonte de app/core/ vers la racine pour database.db
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(CURRENT_DIR)), "bot_database.db")

class MasthomBot(commands.Bot):
    def __init__(self):
        # 1. On récupère les identifiants actuels
        token = os.getenv('TWITCH_BOT_OAUTH_TOKEN')
        channel = os.getenv('TWITCH_USERNAME')

        # 2. Vérification de sécurité
        if not token or not channel:
            print("❌ [ERREUR CRITIQUE] TWITCH_BOT_OAUTH_TOKEN ou TWITCH_USERNAME est vide")
            # Optionnel : Tu pourrais tenter un refresh immédiat ici si le token est vide
        
        # 3. DEBUG (Avant refresh)
        print(f"🔑 [DEBUG] Token actuel (fin) : ...{token[-4:] if token else 'VIDE'}")

        # --- AJOUT DU REFRESH AUTOMATIQUE ---
        # On tente de rafraîchir le token de Félix AVANT de se connecter.
        # Si le refresh réussit, il renvoie le nouveau token, sinon il garde l'ancien.
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

    def get_db_config(self):
        """Récupère tous les réglages de l'Admin en temps réel."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            settings = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
            personality = conn.execute("SELECT * FROM personality WHERE id = 1").fetchone()
            conn.close()
            
            # Conversion en dictionnaires pour un accès plus facile
            s_dict = dict(settings) if settings else None
            p_dict = dict(personality) if personality else None
            return s_dict, p_dict
        except Exception as e:
            print(f"❌ [DB ERROR] Impossible de lire database.db : {e}")
            return None, None

    async def event_ready(self):
        print(f"🟢 [SUCCÈS] Félix est en ligne sur Twitch !")
        print(f"🐈 Nom du bot : {self.nick}")

    async def event_message(self, message):
        # --- SÉCURITÉ : Ignorer ses propres messages ---
        if message.author is None or message.author.name.lower() == self.nick.lower():
            return

        # --- LOG DE RÉCEPTION ---
        # Si tu ne vois pas cette ligne, le bot n'est pas sur le bon salon Twitch.
        print(f"📩 [MESSAGE] {message.author.name}: {message.content}")

        # 1. Lecture de la base de données
        settings, personality = self.get_db_config()
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
        """
        Construit le prompt final et appelle l'IA.
        """
        # On reprend les infos fraîches de la DB
        settings, personality = self.get_db_config()

        # Mapping des longueurs (on traduit les clés techniques en instructions claires)
        length_map = {
            "tres_courte": "Réponds en moins de 10 mots. Très sec.",
            "courte": "Fais une seule phrase courte.",
            "normale": "Fais 2 à 3 phrases maximum.",
            "detaillee": "Fais un paragraphe détaillé et complet."
        }
        instruction_longueur = length_map.get(settings.get('response_length'), "Sois concis.")

        # --- CONSTRUCTION DU PROMPT SYSTÈME ---
        # On injecte TOUS les champs de la base de données ici
        full_system_prompt = f"""
{personality.get('system_prompt')}

INFOS COMPLÉMENTAIRES (À respecter strictement) :
- Ton de voix : {settings.get('selected_tone')}
- Contrainte de longueur : {instruction_longueur}
- Contexte général : {personality.get('base_context')}
- Mots-clés autorisés : {personality.get('keywords')}

INFORMATIONS POUR RÉPONDRE AUX VIEWERS :
- Discord : {settings.get('discord_link')}
- YouTube : {settings.get('youtube_link')}
- Planning : {settings.get('planning')}
- Autres règles : {settings.get('other_rules')}

RÈGLES DE COMPORTEMENT :
- Ne sors jamais de ton personnage.
- Ne mentionne pas que tu es une IA ou un bot.
"""

        # --- LOGS DE VÉRIFICATION DANS LE TERMINAL ---
        print(f"🔥 [IA CONFIG] Tonalité : {settings.get('selected_tone')}")
        print(f"🔥 [IA CONFIG] Longueur : {settings.get('response_length')}")
        print(f"🔥 [IA PROMPT] Prompt envoyé : {personality.get('system_prompt')[:100]}...")

        try:
            # --- PLACEHOLDER POUR L'API (OpenAI/Groq/etc.) ---
            # C'est ici que tu dois brancher ton client IA :
            # response = await self.ton_client_ia.chat.completions.create(
            #     messages=[{"role": "system", "content": full_system_prompt}, ...]
            # )
            # return response.choices[0].message.content
            
            # Test en attendant ta connexion API réelle :
            return f"@{username}, [MODE {settings.get('selected_tone').upper()}] Je t'écoute, mais branche mon API pour que je parle vraiment !"

        except Exception as e:
            print(f"❌ [ERREUR IA] : {e}")
            return None

@routines.routine(minutes=1)
    async def announcement_check(self):
        # On ne traite les annonces que si le stream est en ligne
        # (Tu peux ajuster cette condition selon tes besoins)
        stream_data = await self.fetch_streams(user_logins=[self.initial_channels[0]])
        if not stream_data:
            return

        all_anns = repo.get_all() # repo doit être accessible ici
        now = datetime.now()

        for ann in all_anns:
            if ann['trigger_type'] == 'interval':
                last_sent = ann['last_sent']
                if last_sent:
                    last_sent = datetime.fromisoformat(last_sent)
                
                # Vérifier si l'intervalle est passé
                if not last_sent or now >= last_sent + timedelta(minutes=ann['interval_minutes']):
                    await self.send_formatted_announcement(ann)

    async def send_formatted_announcement(self, ann):
        # Remplacement des tags (Exemple simplifié)
        message = ann['message_template']
        
        # Récupération des données live pour les tags
        # Note: Tu peux enrichir ces données avec ton twitch_service
        viewers = 0 
        game = "Inconnu"
        
        chan = self.get_channel(self.initial_channels[0])
        if chan:
            # Remplacement des tags
            message = message.replace("{viewers}", str(viewers))
            message = message.replace("{game}", game)
            message = message.replace("{uptime}", "En cours")
            
            await chan.send(message)
            repo.update_last_sent(ann['id'])

# Lancement automatique pour test
if __name__ == "__main__":
    bot = MasthomBot()
    bot.run()
