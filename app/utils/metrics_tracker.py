import json
import logging
from datetime import datetime
from collections import Counter
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.metrics")

# Tampon mémoire pour la minute en cours
message_count = 0
emote_counter = Counter()

def log_new_message(message_text: str):
    """Compte le message et extrait les mots en majuscules (émotes suspectées)."""
    global message_count, emote_counter
    message_count += 1
    
    words = message_text.split()
    for w in words:
        if (w.isupper() and len(w) > 2) or w.lower() in ['gg', 'lul', 'kappa', 'pog']:
            emote_counter[w] += 1

async def init_metrics_db():
    """Crée la table de métriques dans PostgreSQL si elle n'existe pas."""
    try:
        async with get_db_connection() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_metrics (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    message_count INTEGER NOT NULL,
                    emotes_json TEXT NOT NULL
                )
            ''')
    except Exception as e:
        logger.error(f"❌ Erreur DB (Metrics Init) : {e}")

async def save_minute_metrics():
    """Fige les données de la minute écoulée en BDD."""
    global message_count, emote_counter
    
    if message_count == 0:
        return
        
    now = datetime.now()
    emotes_json = json.dumps(dict(emote_counter.most_common(10)))
    
    # On sauvegarde le nombre actuel pour éviter qu'il change pendant l'écriture
    current_count = message_count
    
    try:
        async with get_db_connection() as conn:
            await conn.execute(
                "INSERT INTO chat_metrics (timestamp, message_count, emotes_json) VALUES ($1, $2, $3)",
                (now, current_count, emotes_json)
            )
            
        # Reset uniquement si la sauvegarde a réussi
        message_count = 0
        emote_counter.clear()
    except Exception as e:
        logger.error(f"❌ Erreur DB (Metrics Save) : {e}")
