import httpx

# Remplace ceci par le vrai token de ton bot Discord
DISCORD_BOT_TOKEN = "MTM5NDIzMjMwMjAzMjI1NzEwNg.GYbH7g.-hDgIpm8BzaDMwNRfFdFG9sDMDHXNIwgKqC3NI"

# La liste statique de tes salons
CHANNELS_LIST = [
    {"id": "1304093006080512020", "name": "LIVE", "category": "Général"},
    {"id": "1137106993681809429", "name": "ANNONCES", "category": "Général"},
    {"id": "1137293575026126898", "name": "PLANNING", "category": "Général"},
    {"id": "1509463035952107550", "name": "ACTU_INSTANT_GAMING", "category": "Général"},
    {"id": "1215004532518555740", "name": "YOUTUBE", "category": "Réseaux"},
    {"id": "1207234887547883600", "name": "TIKTOK", "category": "Réseaux"},
    {"id": "1380174943710609409", "name": "CLIP_TWITCH", "category": "Réseaux"},
    {"id": "1395327476208635944", "name": "GIVEAWAY", "category": "Communauté"},
    {"id": "1173967725220077658", "name": "SUGGESTIONS", "category": "Communauté"},
    {"id": "1497148005919232202", "name": "FAQ", "category": "Communauté"},
    {"id": "1137022680793612399", "name": "PRESENTATION", "category": "Membres"},
    {"id": "1173959172430250074", "name": "TROMBINOSCOPE", "category": "Membres"},
    {"id": "1173959652728389703", "name": "ANNIVERSAIRE", "category": "Membres"},
    {"id": "1137102419344490516", "name": "DISCUSSION", "category": "Discussions"},
    {"id": "1173958522417983518", "name": "NOS_BESTIOLES", "category": "Discussions"},
    {"id": "1265968711513145364", "name": "ANIME_MANGA", "category": "Discussions"},
    {"id": "1173969549775867944", "name": "VOS_CREATION", "category": "Discussions"},
    {"id": "1438248903404159117", "name": "MEDIATHEQUE", "category": "Discussions"},
    {"id": "1173958759928823809", "name": "MUSIQUES", "category": "Discussions"},
    {"id": "1173994028153454613", "name": "NSFW", "category": "Discussions"},
    {"id": "1401142489951371264", "name": "CODAGE", "category": "Discussions"},
    {"id": "1173960591648505908", "name": "JEUX_DIVERS", "category": "Jeux"},
    {"id": "1174249235928072202", "name": "BLABLA_STREAMERS", "category": "Streamers"},
    {"id": "1174249310246948875", "name": "ENTRAIDE", "category": "Streamers"},
    {"id": "1175022639908126770", "name": "PUB", "category": "Streamers"},
    {"id": "1435674301490659458", "name": "COPAINS_EN_LIVE", "category": "Streamers"}
]

async def send_message_to_discord(channel_id: str, message: str) -> dict:
    """
    Envoie un message texte sur un salon Discord précis.
    """
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"content": message}

    # Utilisation d'un client HTTP asynchrone pour ne pas bloquer le serveur web
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return {"status": "success", "message": "Message envoyé avec succès !"}
    else:
        return {"status": "error", "message": f"Erreur Discord: {response.text}"}
