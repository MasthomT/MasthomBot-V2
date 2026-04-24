import asyncio
import aiohttp
import os
from dotenv import load_dotenv

# 1. On charge ton fichier de configuration actuel
load_dotenv("/home/masthom/BOT_V2/.env")

# 2. Récupération des accès officiels du bot
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
# On utilise le salon configuré dans ton .env pour les annonces
CHANNEL_ID = os.getenv("ANNONCE_CHANNEL_ID") 

MESSAGE = """
🌟 **LE SITE FEL-X EST DE RETOUR !** 🌟

@everyone, Félix a fini sa sieste technique et la plateforme est à nouveau pleinement opérationnelle. C’est le moment d’aller checker votre progression et de configurer votre expérience sur la chaîne !

🔗 **Accès direct :** https://fel-x.vercel.app/

---

### 📋 **CE QUE VOUS POUVEZ FAIRE SUR LE SITE :**

📊 **STATISTIQUES GLOBALES**
Consultez l'activité de la communauté en temps réel : volume total d'EXP généré, nombre de messages traités et le prestigieux **Top 5** des plus gros piliers de la chaîne.

👤 **VOTRE PROFIL PERSONNEL**
Suivez votre évolution avec précision :
* **Niveau & Rang** : Visualisez votre niveau actuel et votre position exacte dans le classement.
* **Jauge d'EXP** : Surveillez votre barre de progression pour savoir quand vous passerez au niveau suivant.
* **Historique détaillé** : Retrouvez toutes vos interactions (Messages, Subs, Bits, Raids) et vos statistiques de session en cours.

🤖 **VOTRE RELATION AVEC FÉLIX**
C'est ici que tout se joue pour l'IA ! Remplissez votre **Fiche Contexte** pour que Félix vous reconnaisse :
* Choisissez votre **surnom**, définissez votre **Vibe**, et réglez votre **Roast Level** (si vous osez).
* Indiquez vos jeux préférés, votre talent inutile ou même votre boisson favorite pour des discussions 100% personnalisées.

🏆 **LEADERBOARD COMPLET**
Le classement intégral est disponible ! Comparez vos points et votre temps de présence avec le reste de la communauté pour décrocher la première place.

🗳️ **SONDAGES EN DIRECT**
Participez aux décisions du stream directement depuis votre mobile ou votre PC grâce au widget de vote intégré à votre profil lors des lives.

---

🐾 *Foncez mettre à jour vos infos pour que Félix sache enfin à qui il a affaire !*

👉 **Rendez-vous sur :** https://fel-x.vercel.app/
"""

async def send_as_felix():
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Erreur : DISCORD_TOKEN ou ANNONCE_CHANNEL_ID introuvable dans le .env !")
        return

    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "content": MESSAGE
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 200:
                print(f"✅ Succès ! Félix vient de poster l'annonce dans le salon {CHANNEL_ID}.")
            elif resp.status == 403:
                print("❌ Erreur 403 : Le bot n'a pas la permission d'écrire dans ce salon.")
            else:
                text = await resp.text()
                print(f"❌ Erreur {resp.status} : {text}")

if __name__ == "__main__":
    asyncio.run(send_as_felix())

