"""
app/services/games_scheduler.py
Choisit automatiquement, chaque jour à 2h00 (heure de Paris), l'élément du jour
pour chacun des 4 jeux : Kikecé (personnage), Oukecé (lieu), Kekecé (objet),
Kikadi (citation détournée).
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from app.core.config import settings
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.games")
TZ = ZoneInfo("Europe/Paris")

PROMPTS = {
    "kikece": """Tu dois choisir UN personnage fictif pour un jeu de devinette quotidien sur Twitch.
Critères : mix jeux vidéo / animés / séries, mélange connu et un peu niche, caractéristiques visuelles distinctives.
Réponds UNIQUEMENT avec ce JSON sur une seule ligne, sans markdown :
{"name":"Nom exact","universe":"Titre exact de l'oeuvre","category":"jeu vidéo|animé|série","extra":null}""",

    "oukece": """Tu dois choisir UN lieu fictif TRÈS CÉLÈBRE de la pop-culture (ville, planète, bâtiment, région) pour un jeu de devinette quotidien sur Twitch.
Critères STRICTS : le lieu doit être instantanément reconnaissable par un large public (équivalent de Poudlard, Gotham City, Hyrule, Tatooine, Konoha). INTERDICTION de choisir un lieu obscur, mineur ou que seuls les fans hardcore connaîtraient. Mix jeux vidéo / animés / séries / films. Le lieu doit avoir une identité visuelle/géographique très distinctive (climat, architecture, population).
Réponds UNIQUEMENT avec ce JSON sur une seule ligne, sans markdown :
{"name":"Nom exact du lieu","universe":"Titre exact de l'oeuvre","category":"jeu vidéo|animé|série|film","extra":null}""",

    "kekece": """Tu dois choisir UN objet ou arme TRÈS CÉLÈBRE de la pop-culture pour un jeu de devinette quotidien sur Twitch.
Critères STRICTS : l'objet doit être instantanément reconnaissable par un large public (équivalent de l'Anneau Unique, la Master Sword, le Death Note, un Batarang, le Bouclier de Captain America). INTERDICTION de choisir un objet obscur, mineur ou que seuls les fans hardcore connaîtraient. Mix jeux vidéo / animés / séries / films. L'objet doit avoir un matériau et une taille caractéristiques.
Réponds UNIQUEMENT avec ce JSON sur une seule ligne, sans markdown :
{"name":"Nom exact de l'objet","universe":"Titre exact de l'oeuvre","category":"jeu vidéo|animé|série|film","extra":null}""",

    "kikadi": """Tu dois choisir UNE réplique culte de la pop-culture (jeu vidéo, film, animé, série) et la réécrire dans un style complètement différent (vieux françois, langage ultra-soutenu, ou style corporate/email pro).
La citation détournée doit rester compréhensible mais cacher suffisamment l'originale pour qu'on doive deviner.
Réponds UNIQUEMENT avec ce JSON sur une seule ligne, sans markdown :
{"name":"Nom du personnage qui dit la réplique originale","universe":"Titre exact de l'oeuvre","category":"jeu vidéo|animé|série|film","extra":"La réplique originale exacte|||La réplique détournée réécrite"}""",
}

GAME_LABELS = {
    "kikece": "personnage",
    "oukece": "lieu",
    "kekece": "objet",
    "kikadi": "citation",
}


async def pick_daily_item(game_type: str) -> dict | None:
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": PROMPTS[game_type]}],
            temperature=1.1,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        item = json.loads(raw)
        if not all(k in item for k in ("name", "universe", "category")):
            raise ValueError(f"JSON incomplet : {item}")
        return item
    except Exception as e:
        logger.error(f"❌ [GAMES] Erreur choix {game_type} : {e}")
        return None


async def save_daily_item(game_type: str, item: dict) -> bool:
    try:
        today = datetime.now(TZ).date()
        extra = item.get("extra")
        async with get_db_connection() as db:
            await db.execute("""
                INSERT INTO games_daily (game_type, game_date, name, universe, category, extra, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (game_type, game_date) DO UPDATE
                  SET name = EXCLUDED.name,
                      universe = EXCLUDED.universe,
                      category = EXCLUDED.category,
                      extra = EXCLUDED.extra,
                      image_url = EXCLUDED.image_url
            """, game_type, today, item["name"], item["universe"], item["category"], extra, None)
        logger.info(f"✅ [GAMES] {GAME_LABELS[game_type]} du jour ({game_type}) : {item['name']} ({item['universe']})")
        return True
    except Exception as e:
        logger.error(f"❌ [GAMES] Erreur enregistrement {game_type} : {e}")
        return False


def seconds_until_next_2am() -> float:
    now = datetime.now(TZ)
    next_reset = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if now.hour >= 2:
        next_reset += timedelta(days=1)
    return max((next_reset - now).total_seconds(), 0)


async def ensure_today_items():
    """Vérifie que tous les jeux ont un élément pour aujourd'hui, en choisit si manquant."""
    today = datetime.now(TZ).date()
    for game_type in PROMPTS.keys():
        async with get_db_connection() as db:
            await db.execute(
                "SELECT id FROM games_daily WHERE game_type = ? AND game_date = ?",
                game_type, today
            )
            existing = await db.fetchone()
        if not existing:
            logger.info(f"🎲 [GAMES] Aucun {GAME_LABELS[game_type]} pour aujourd'hui ({game_type}), sélection...")
            item = await pick_daily_item(game_type)
            if item:
                await save_daily_item(game_type, item)
            else:
                logger.error(f"❌ [GAMES] Échec sélection initiale pour {game_type}.")


async def games_scheduler_routine():
    logger.info("🎮 [GAMES SCHEDULER] Démarrage du planificateur multi-jeux.")
    await ensure_today_items()

    while True:
        wait = seconds_until_next_2am()
        h, m = divmod(int(wait // 60), 60)
        logger.info(f"🎮 [GAMES] Prochain renouvellement dans {h}h{m:02d}min.")
        await asyncio.sleep(wait)

        for game_type in PROMPTS.keys():
            item = await pick_daily_item(game_type)
            if item:
                await save_daily_item(game_type, item)
            else:
                logger.error(f"❌ [GAMES] Échec sélection {game_type}, sera retenté au prochain cycle.")
            await asyncio.sleep(2)
