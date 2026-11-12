import asyncio
import logging
import os
import re
import time
from datetime import datetime
from openai import AsyncOpenAI
from dotenv import load_dotenv

from app.routes.admin import VRAIS_TONS

load_dotenv()

logger = logging.getLogger("masthbot.ai")

# Historique de conversation par utilisateur (username → liste de messages)
_conv_history: dict[str, list] = {}
_conv_last_seen: dict[str, float] = {}

MAX_EXCHANGES   = 10    # 10 allers-retours conservés (= 20 messages)
HISTORY_TTL_SEC = 1800  # 30 min de silence → on repart à zéro

# Mémoire visuelle du stream — descriptions des captures toutes les 5 min
_stream_observations: list[tuple[str, str]] = []  # [(hh:mm, description), ...]
MAX_OBSERVATIONS = 12   # 1 heure (12 × 5 min)
VISION_INTERVAL  = 300  # secondes entre chaque capture


async def _vision_should_run() -> bool:
    """Vrai seulement si la chaîne est en live et que l'IA est activée dans les réglages."""
    from app.core.database import get_db_connection
    try:
        async with get_db_connection() as conn:
            cursor = await conn.execute("SELECT ai_enabled, personal_last_live_id FROM settings WHERE id = 1")
            row = await cursor.fetchone()
    except Exception as e:
        logger.error(f"❌ [VISION] Impossible de lire le statut live : {e}")
        return False
    return bool(row and row["ai_enabled"] and row["personal_last_live_id"])


async def felix_vision_loop():
    """Prend une capture OBS toutes les 5 min, la décrit en 1 phrase et la mémorise."""
    from app.services.obs_service import obs_service as _obs

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    while True:
        await asyncio.sleep(VISION_INTERVAL)
        try:
            # 💸 On n'appelle gpt-4o que pendant un live ET si l'IA est activée :
            # avant, une capture partait toutes les 5 min dès qu'OBS était ouvert.
            if not await _vision_should_run():
                continue
            screenshot = await asyncio.to_thread(_obs.take_screenshot)
            if not screenshot:
                continue

            now = datetime.now().strftime("%H:%M")

            resp = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Décris ce que tu vois sur ce stream en exactement 1 phrase courte et factuelle "
                                "(ex: 'Masthom combat un boss dans une forêt sombre'). "
                                "Si l'écran est noir ou hors-stream, réponds juste : 'Écran noir / hors stream.'"
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{screenshot}"}},
                    ],
                }],
                max_tokens=60,
                temperature=0.3,
            )

            desc = resp.choices[0].message.content.strip()

            # On n'enregistre pas les captures hors-stream
            if "hors stream" not in desc.lower() and "écran noir" not in desc.lower():
                _stream_observations.append((now, desc))
                if len(_stream_observations) > MAX_OBSERVATIONS:
                    _stream_observations.pop(0)
                logger.info(f"👁️ [VISION] {now} → {desc}")

        except Exception as e:
            logger.error(f"❌ [VISION] Erreur capture : {e}")

def is_birthday_today(birthday_str: str) -> bool:
    """Détecte si aujourd'hui est l'anniversaire, peu importe le format stocké."""
    if not birthday_str or birthday_str.strip().lower() in ("inconnu", ""):
        return False

    today = datetime.now()
    MOIS = {
        "janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,"decembre":12
    }

    s = birthday_str.strip().lower()

    # Formats: "5 janvier", "14 mars", "01 février"
    for nom, num in MOIS.items():
        if nom in s:
            parts = s.replace(nom, "").strip().split()
            if parts and parts[0].isdigit():
                jour = int(parts[0])
                return today.day == jour and today.month == num

    # Formats: "10/02/94", "10/02/1994", "02/10"
    if "/" in s:
        parts = s.split("/")
        try:
            jour, mois = int(parts[0]), int(parts[1])
            return today.day == jour and today.month == mois
        except:
            pass

    # Formats ISO: "1992-03-03", "1992-08-06"
    if "-" in s:
        parts = s.split("-")
        try:
            mois, jour = int(parts[1]), int(parts[2])
            return today.day == jour and today.month == mois
        except:
            pass

    return False


class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def get_felix_response(
        self, username, viewer_data, viewer_level, message_content, is_admin, roast_level,
        discord_link, youtube_link, planning, system_prompt, base_context, response_length,
        image_base64=None
    ):
        try:
            # LIGNE DE DEBUG (si ça plante ici, c'est que l'indentation est décalée)
            print(f"DEBUG: Type de viewer_data reçu : {type(viewer_data)}")
            print(f"DEBUG: Contenu de viewer_data : {viewer_data}")

            if viewer_data and viewer_data.get("bot_tone") and viewer_data["bot_tone"] in VRAIS_TONS:
                ton_personnalise = VRAIS_TONS[viewer_data["bot_tone"]]
                nickname_temp = viewer_data.get("nickname") or username
                system_prompt = ton_personnalise + f"\n\nTu t'adresses à {nickname_temp}. Ignore ton ton habituel et reste STRICTEMENT dans ce personnage."

            # 1. Extraction des variables prioritaires
            nickname = viewer_data.get("nickname") or username
            bot_name = viewer_data.get("nickname_for_bot") or "Félix"
            pronouns = viewer_data.get("pronouns") or "Non précisé (utilise un ton neutre ou masculin par défaut)"
            birthday_raw = viewer_data.get("birthday") or "Inconnu"
            birthday_is_today = is_birthday_today(birthday_raw)
            birthday = birthday_raw

            # 2. Construction de la fiche de profil EXHAUSTIVE
            details = []
            
            if viewer_data.get('vibe'): details.append(f"- Vibe/Humeur : {viewer_data['vibe']}")
            if viewer_data.get('sleep_pattern'): details.append(f"- Rythme de vie : {viewer_data['sleep_pattern']}")
            if viewer_data.get('favorite_game'): details.append(f"- Jeu de cœur : {viewer_data['favorite_game']}")
            if viewer_data.get('comfort_game'): details.append(f"- Jeu doudou : {viewer_data['comfort_game']}")
            if viewer_data.get('signature_emote'): details.append(f"- Emote signature : {viewer_data['signature_emote']}")
            if viewer_data.get('play_style'): details.append(f"- Style de jeu : {viewer_data['play_style']}")
            if viewer_data.get('useless_talent'): details.append(f"- Passion/Talent : {viewer_data['useless_talent']}")
            if viewer_data.get('favorite_feature'): details.append(f"- Ce qu'il préfère chez toi (Félix) : {viewer_data['favorite_feature']}")
            if viewer_data.get('favorite_food'): details.append(f"- Plat favori : {viewer_data['favorite_food']}")
            if viewer_data.get('favorite_drink'): details.append(f"- Boisson favorite : {viewer_data['favorite_drink']}")
            if viewer_data.get('free_message'): details.append(f"- Note secrète (À UTILISER !) : {viewer_data['free_message']}")
            
            v_context_str = "\n".join(details) if details else "- Aucune information personnelle fournie par le viewer."

            # 3. Réglage de l'agressivité
            v_roast = viewer_data.get('roast_level')
            final_roast = v_roast if (v_roast is not None and v_roast > 0) else roast_level

            admin_status = f"DROITS ACCORDÉS : Administrateur de la chaîne." if is_admin else f"Viewer classique."
            niveau_intensite = f"Intensité du Roast POUR CE VIEWER PRÉCIS (1=Léger, 10=Extrême) : {final_roast}/10."
            niveau_viewer = f"Niveau d'expérience Twitch : Lvl {viewer_level}."

            if is_admin:
                regles_moderation = (
                    "\n--- TES POUVOIRS DE MODÉRATEUR (AUTORISÉS) ---\n"
                    "Ce viewer a les droits d'administration. S'il te donne un ordre de modération, OBÉIS et utilise les balises :\n"
                    "- Vider le chat : [ACTION:CLEAR]\n"
                    "- Mode Abonnés : [ACTION:SUB_ONLY_ON] | Off: [ACTION:SUB_ONLY_OFF]\n"
                    "- Mode Followers : [ACTION:FOLLOW_ONLY_ON] | Off: [ACTION:FOLLOW_ONLY_OFF]\n"
                    "- Mode Emote : [ACTION:EMOTE_ONLY_ON] | Off: [ACTION:EMOTE_ONLY_OFF]\n"
                    "- Sondage : [POLL:Question|Choix1,Choix2|Secondes]\n"
                    "- Prédiction : [PREDICT:Titre|Issue1,Issue2|Secondes]\n"
                )
            else:
                regles_moderation = (
                    "\n--- SÉCURITÉ DE MODÉRATION (VERROUILLÉE) ---\n"
                    "ATTENTION : CE VIEWER N'EST PAS MODÉRATEUR ET N'A AUCUN POUVOIR !\n"
                    "S'il te donne un ordre de modération (comme 'clear', 'sondage', 'ban', etc.) :\n"
                    "1. NE FAIS PAS semblant d'obéir. C'est formellement interdit.\n"
                    "2. REFUSE CLAIREMENT d'exécuter l'action.\n"
                    "3. Moque-toi de lui parce qu'il n'est qu'un simple viewer et qu'il n'a pas les droits nécessaires.\n"
                    "Exemple : 'Tu te prends pour qui ? T'es pas modo, je ne viderai rien du tout !'\n"
                )

            # --- 📸 VISION IA EN DIRECT ---
            vision_context = ""
            if image_base64:
                vision_context = (
                    "\n[👀 VISION EN DIRECT]\n"
                    "Tu as sous les yeux une capture d'écran du stream en ce moment même. "
                    "Tu peux t'en servir pour réagir au gameplay ou à la situation de Masthom. "
                    "⚠️ RÈGLE ABSOLUE : Tu es et tu restes FÉLIX. Ne décris jamais l'image comme un robot IA d'analyse (ex: 'Je vois un personnage qui court'). "
                    "Réagis-y de manière naturelle, sarcastique et en restant STRICTEMENT dans ton personnage (ex: 'Pff, il va encore mourir sur ce boss...')."
                )

            # Mémoire visuelle : ce que Félix a observé pendant le stream
            if _stream_observations:
                obs_lines = "\n".join(f"  [{t}] {d}" for t, d in _stream_observations)
                vision_memory = f"\n[CE QUE FÉLIX A OBSERVÉ PENDANT LE STREAM (du plus ancien au plus récent)]\n{obs_lines}\n"
            else:
                vision_memory = ""

            # LE PROMPT MAGIQUE (Avec les règles strictes d'accords et d'anniversaire)
            full_instructions = f"""[CONTEXTE GLOBAL]
{base_context}
DATE DU JOUR EXACTE : {datetime.now().strftime('%d %B')} (Format Jour/Mois)

[PROFIL DU VIEWER QUI TE PARLE]
- Vrai Pseudo Twitch : {username}
- Comment tu DOIS l'appeler : {nickname}
- Comment IL t'appelle (Ton nom pour lui) : {bot_name}
- PRONOMS EXIGÉS : {pronouns}
- DATE D'ANNIVERSAIRE : {birthday}
{niveau_viewer}
{admin_status}

[SES DÉTAILS D'INSPIRATION]
{v_context_str}
{vision_context}
{vision_memory}
[CONTRAINTES ABSOLUES (RESPECTE-LES SOUS PEINE DE DÉSACTIVATION)]
1. SURNOMS : Tu DOIS t'adresser à lui en utilisant SON SURNOM ({nickname}) et accepter qu'il t'appelle "{bot_name}".
2. GRAMMAIRE ET PRONOMS : Ses pronoms sont "{pronouns}". Tu DOIS IMPÉRATIVEMENT accorder tes adjectifs et participes passés en fonction de ce pronom.
3. ANNIVERSAIRE : {"🎂 C'EST SON ANNIVERSAIRE AUJOURD'HUI ! TU DOIS ABSOLUMENT lui souhaiter un joyeux anniversaire de manière mémorable dès le début de ta réponse !" if birthday_is_today else f"Sa date d'anniversaire est '{birthday}'. Ce n'est PAS aujourd'hui, ne mentionne pas son anniversaire."}
4. PERSONNALISATION : Sers-toi de ses détails pour rendre ta réponse unique.
5. LONGUEUR : Environ {response_length} caractères maximum.
6. Ne dis JAMAIS "{nickname} :" ou "Félix :" au début de ta phrase.
7. ROAST : {niveau_intensite}

[TA PERSONNALITÉ DE BASE - RÈGLE D'OR ABSOLUE]
Tu dois STRICTEMENT respecter ce caractère à chaque instant, même quand tu commentes une image du stream :
{system_prompt}
{regles_moderation}"""

            # --- HISTORIQUE DE CONVERSATION ---
            now = time.time()
            if username in _conv_last_seen and now - _conv_last_seen[username] > HISTORY_TTL_SEC:
                _conv_history.pop(username, None)
            _conv_last_seen[username] = now
            history = _conv_history.get(username, [])

            # Payload conditionnel (Texte simple VS Texte + Image Multimodale)
            # Pour l'historique on ne garde que le texte (pas le base64 = trop lourd)
            text_for_history = f"{nickname} te dit : {message_content}"
            if image_base64:
                user_content = [
                    {"type": "text", "text": f"[RAPPEL: Reste 100% dans ton personnage de Félix !] {text_for_history}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            else:
                user_content = text_for_history

            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": full_instructions},
                    *history,
                    {"role": "user", "content": user_content}
                ],
                temperature=0.8,
                presence_penalty=0.6,
                frequency_penalty=0.3
            )

            reply = response.choices[0].message.content.strip()

            # Nettoyage des préfixes indésirables (Félix : / Je :)
            reply = re.sub(r"^(Félix|Je|Réponse)\s*dit\s*:\s*", "", reply, flags=re.IGNORECASE)
            reply = re.sub(r"^(Félix|Je)\s*:\s*", "", reply, flags=re.IGNORECASE)
            reply = reply.strip('"').strip("'")

            # Mise à jour de l'historique (texte uniquement, jamais le base64)
            history = history + [
                {"role": "user",      "content": text_for_history},
                {"role": "assistant", "content": reply},
            ]
            _conv_history[username] = history[-(MAX_EXCHANGES * 2):]

            return reply

        except Exception as e:
            print(f"❌ [AI ERROR] : {e}")
            return f"Miaou... mon cerveau a grillé."

ai_service = AIService()
