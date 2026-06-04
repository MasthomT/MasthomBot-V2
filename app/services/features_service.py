import aiohttp
import logging
from datetime import datetime
from app.core.config import settings
from urllib.parse import quote

# ==========================================
# 🤫 JEU DU MOT SECRET
# ==========================================
_secret_state = {"word": "", "setter": ""}

async def handle_set_word(username: str, user_input: str) -> str:
    """Définit le mot secret (réservé aux modos/vip)."""
    if not user_input:
        return f"@{username}, tu dois préciser un mot ! Exemple: !setword ananas"
    
    _secret_state["word"] = user_input.lower().strip()
    _secret_state["setter"] = username
    return f"🤫 Le mot secret a été défini par @{username} ! À vous de le deviner avec !guess <mot>..."

async def handle_guess_word(username: str, user_input: str) -> str:
    """Vérifie si le joueur a trouvé le mot secret."""
    if not _secret_state["word"]:
        return f"@{username}, aucun mot secret n'est défini pour le moment !"
    if not user_input:
        return ""

    guess = user_input.lower().strip()
    if guess == _secret_state["word"]:
        _secret_state["word"] = ""  # On réinitialise la partie
        return f"🎉 BINGO ! @{username} a trouvé le mot secret ! Félicitations !"
    
    return "" # On ne retourne rien si c'est faux pour ne pas spammer le chat

# ==========================================
# 🌍 SYSTÈME DE TRADUCTION (Google Translate API)
# ==========================================
# Dictionnaire des commandes et de leur code langue associé
LANGUAGES = {
    # Allemand
    "al": "de", "ge": "de", "ger": "de",
    # Anglais
    "an": "en", "ang": "en", "en": "en", "eng": "en",
    # Arabe
    "ar": "ar", "ara": "ar",
    # Chinois
    "ch": "zh-CN", "chi": "zh-CN",
    # Espagnol
    "esp": "es", "es": "es",
    # Français
    "fr": "fr", "fra": "fr",
    # Italien
    "it": "it", "ita": "it",
    # Japonais
    "ja": "ja", "jap": "ja",
    # Russe
    "ru": "ru"
}

async def handle_translation(target_cmd: str, username: str, user_input: str) -> str:
    """Traduit le texte dans la langue demandée via Google Translate."""
    # 1. Vérification : si l'utilisateur n'a rien écrit à traduire
    if not user_input:
        return f"@{username}, que dois-je traduire ? Exemple: !{target_cmd} Bonjour le chat"
        
    # 2. Récupération du code de la langue
    lang_code = LANGUAGES.get(target_cmd, "en")
    
    # 3. Préparation de l'URL pour l'API Google
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang_code}&dt=t&q={quote(user_input)}"
    
    # 4. Appel à l'API et formatage du résultat
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # On rassemble les morceaux de la phrase traduite
                    translated_text = "".join([sentence[0] for sentence in data[0]])
                    
                    # 👉 Le nouveau format exact que tu as demandé
                    return f"🌍 Traduction ({target_cmd.upper()}) {username} : {translated_text}"
    except Exception as e:
        return f"❌ {username}, erreur lors de la traduction (Problème de connexion)."
        
    return f"❌ {username}, service de traduction indisponible."

logger = logging.getLogger("masthbot.features")

async def translate_with_deepl(text: str, target_lang: str = "FR", source_lang: str = "EN") -> str:
    """Traduit un texte via l'API DeepL avec la méthode d'authentification moderne."""
    if not text:
        return ""
    
    api_key = getattr(settings, "DEEPL_API_KEY", "")
    if not api_key:
        logger.warning("⚠️ Clé DeepL manquante, le texte ne sera pas traduit.")
        return text

    # Détection automatique de l'API (Gratuite ou Pro)
    url = "https://api-free.deepl.com/v2/translate"
    if not api_key.endswith(":fx"):
        url = "https://api.deepl.com/v2/translate"

    # Authentification via les Headers (Standard recommandé par DeepL)
    headers = {
        "Authorization": f"DeepL-Auth-Key {api_key}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Paramètres de traduction
    data = {
        "text": text,
        "target_lang": target_lang
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    return res["translations"][0]["text"]
                else:
                    # Affichage précis de l'erreur dans les logs pour comprendre le blocage
                    error_msg = await resp.text()
                    logger.error(f"❌ DeepL a refusé la traduction (Code {resp.status}) : {error_msg}")
                    return text
    except Exception as e:
        logger.error(f"❌ Erreur de connexion aux serveurs DeepL : {e}")
        
    return text

async def handle_game_info(game_name: str, client_id: str, token: str) -> str:
    """Recherche un jeu sur IGDB, traduit les infos et les formate."""
    if not game_name or game_name.lower() in ["just chatting", "discussion"]:
        return "❌ Aucun jeu précis n'est en cours."

    igdb_url = "https://api.igdb.com/v4/games"
    # Requête identique à ton script C#
    query = f'fields name, genres.name, summary, involved_companies.company.name, release_dates.date, websites.url; search "{game_name}"; where version_parent = null & name = "{game_name}"; limit 1;'
    
    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(igdb_url, headers=headers, data=query) as resp:
                if resp.status != 200:
                    return f"❌ Impossible de joindre IGDB (Erreur {resp.status})"
                
                data = await resp.json()
                if not data:
                    return f"❌ Aucun jeu trouvé sous le nom '{game_name}'."
                
                game = data[0]
                
                # 1. Extraction des données brutes
                raw_name = game.get("name", game_name)
                raw_summary = game.get("summary", "Aucun résumé disponible.")
                
                dev = "Inconnu"
                if "involved_companies" in game:
                    dev = game["involved_companies"][0].get("company", {}).get("name", "Inconnu")
                    
                genres = "Inconnus"
                if "genres" in game:
                    genres = ", ".join([g.get("name", "") for g in game["genres"]])
                    
                release_date = "Inconnue"
                if "release_dates" in game:
                    ts = game["release_dates"][0].get("date")
                    if ts:
                        release_date = datetime.fromtimestamp(ts).strftime("%d/%m/%Y")

                steam_url = ""
                if "websites" in game:
                    for w in game["websites"]:
                        if "store.steampowered.com" in w.get("url", ""):
                            steam_url = f" | 🌐 Steam: {w['url']}"
                            break

                # 2. Traductions simultanées (gain de temps considérable)
                t_name = await translate_with_deepl(raw_name)
                t_summary = await translate_with_deepl(raw_summary)
                t_dev = await translate_with_deepl(dev)
                t_genres = await translate_with_deepl(genres)

                # 3. Formatage et contrôle de la longueur
                # On coupe le résumé pour s'assurer que le tout tienne sous les 500 caractères Twitch
                short_summary = t_summary[:180] + "..." if len(t_summary) > 180 else t_summary

                details = (
                    f"🎮 {t_name} | "
                    f"👨‍💻 {t_dev} | "
                    f"📅 {release_date} | "
                    f"🔖 {t_genres} | "
                    f"ℹ️ {short_summary}"
                    f"{steam_url}"
                )
                return details

    except Exception as e:
        logger.error(f"❌ Erreur lors de la recherche du jeu : {e}")
        return "❌ Une erreur est survenue lors de la recherche IGDB."
