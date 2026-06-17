"""
app/services/kikece_scheduler.py
Choisit automatiquement le personnage Kikecé du jour à 2h00 (heure de Paris)
via OpenAI GPT-4o, et l'enregistre en base.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from app.core.config import settings
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.kikece")
TZ = ZoneInfo("Europe/Paris")

PROMPT = """Tu dois choisir UN personnage fictif pour un jeu de devinette quotidien sur Twitch.

Critères :
- Alterne aléatoirement entre jeux vidéo, animés et séries TV
- Mélange personnages très connus et légèrement niche (pas ultra-obscurs)
- Le personnage doit avoir des caractéristiques visuelles distinctives (couleur, tenue)
- Évite les personnages trop génériques ou ambigus

Réponds UNIQUEMENT avec ce JSON sur une seule ligne, sans markdown, sans explication :
{"name":"Nom exact du personnage","universe":"Titre exact de l'oeuvre","char_type":"jeu vidéo|animé|série"}"""


async def pick_daily_character() -> dict | None:
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": PROMPT}],
            temperature=1.1,
            max_tokens=80,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        char = json.loads(raw)
        # Validation minimale
        if not all(k in char for k in ("name", "universe", "char_type")):
            raise ValueError(f"JSON incomplet : {char}")
        return char
    except Exception as e:
        logger.error(f"❌ [KIKECE] Erreur choix personnage OpenAI : {e}")
        return None


async def save_daily_character(char: dict) -> bool:
    try:
        today = datetime.now(TZ).date()
        async with get_db_connection() as db:
            await db.execute("""
                INSERT INTO kikece_daily (game_date, name, universe, char_type, image_url)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (game_date) DO UPDATE
                  SET name = EXCLUDED.name,
                      universe = EXCLUDED.universe,
                      char_type = EXCLUDED.char_type,
                      image_url = EXCLUDED.image_url
            """, today, char["name"], char["universe"], char["char_type"], None)
        logger.info(f"✅ [KIKECE] Personnage du jour : {char['name']} ({char['universe']}, {char['char_type']})")
        return True
    except Exception as e:
        logger.error(f"❌ [KIKECE] Erreur enregistrement : {e}")
        return False


def seconds_until_next_2am() -> float:
    now = datetime.now(TZ)
    next_reset = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if now.hour >= 2:
        next_reset += timedelta(days=1)
    return max((next_reset - now).total_seconds(), 0)


async def kikece_scheduler_routine():
    logger.info("🎭 [KIKECE] Planificateur démarré.")

    # Au démarrage : si aucun personnage aujourd'hui, en choisir un immédiatement
    today = datetime.now(TZ).date()
    async with get_db_connection() as db:
        await db.execute("SELECT id FROM kikece_daily WHERE game_date = ?", today)
        existing = await db.fetchone()

    if not existing:
        logger.info("🎭 [KIKECE] Aucun personnage pour aujourd'hui, sélection immédiate...")
        char = await pick_daily_character()
        if char:
            await save_daily_character(char)
        else:
            logger.error("❌ [KIKECE] Échec de la sélection initiale.")

    # Boucle infinie : attend 2h00, choisit, recommence
    while True:
        wait = seconds_until_next_2am()
        h, m = divmod(int(wait // 60), 60)
        logger.info(f"🎭 [KIKECE] Prochain personnage dans {h}h{m:02d}min.")
        await asyncio.sleep(wait)

        char = await pick_daily_character()
        if char:
            await save_daily_character(char)
        else:
            logger.error("❌ [KIKECE] Échec sélection automatique, réessai dans 10 min.")
            await asyncio.sleep(600)
