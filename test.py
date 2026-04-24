import asyncio
import os
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv("/home/masthom/BOT_V2/.env")

async def send_felix_announcement():
    print("🐾 Félix prépare ses dossiers secrets (version texte)...")

    token = os.getenv("DISCORD_TOKEN")
    # On utilise le salon des annonces pour le grand public
    channel_id = os.getenv("ANNONCE_CHANNEL_ID")

    if not token or not channel_id:
        print("❌ Erreur : DISCORD_TOKEN ou ANNONCE_CHANNEL_ID manquant dans le .env")
        return

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }

    # Le message de Félix en texte brut (Markdown Discord)
    message_content = (
        "🐾 **LES DOSSIERS SONT OUVERTS : FÉLIX BALANCE TOUT !** 🕵️‍♂️\n\n"
        "Miaou @everyone ! Vous pensiez que les secrets du stream resteraient bien cachés ? C'est mal me connaître.\n\n"
        "J'ai décidé d'ouvrir la **F.A.CUL**, et croyez-moi, j'en ai des choses à dire sur Masthom et sur vos petites habitudes dans le chat.\n\n"
        "❓ **C'EST QUOI LE CONCEPT ?**\n"
        "Ici, on ne parle pas de 'problèmes techniques'. On veut du croustillant !\n"
        "• Une question indiscrète sur le passé de Masthom ? 🎤\n"
        "• Envie de savoir ce qu'il se passe vraiment en coulisses ? 🎬\n"
        "• Une curiosité sur un membre de la commu ou sur moi-même ? 🐾\n\n"
        "• Une petite question que tu as toujours voulu poser ? ⚡\n\n"
        "👉 **Pose ta question ici :** https://fel-x.vercel.app/ dans la section F.A.Q\n\n"
        "🤫 **SECRET DÉFENSE :**\n"
        "Toutes les questions publiées sont **100% ANONYMES**. Personne ne saura que c'est toi qui as posé cette question un peu gênante... sauf moi, mais je ne dirai rien. Promis. 🤐\n\n"
        "🐾 *Signé Félix • Votre humble Maître à toutes et tous.*"
    )

    payload = {
        "content": message_content
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status == 200:
                print("✅ L'annonce a été publiée en texte simple ! Félix a fait son job. 🐾")
            else:
                text = await resp.text()
                print(f"❌ Erreur Discord ({resp.status}) : {text}")

if __name__ == "__main__":
    asyncio.run(send_felix_announcement())
