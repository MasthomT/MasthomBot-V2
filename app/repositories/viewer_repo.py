import aiosqlite
import logging
from typing import Optional, List
from app.models.viewer import ViewerCreate, ViewerUpdate, ViewerResponse
from app.core.database import get_db_connection, queue_write
logger = logging.getLogger("masthbot.repo")

# ==========================================================
# ⚙️ MOTEUR D'INJECTION DE NIVEAU
# ==========================================================
def _inject_level(viewer_dict):
    """Fonction centrale : Calcule et greffe le niveau nativement partout."""
    if not viewer_dict: 
        return None
    xp = viewer_dict.get('points', 0)
    viewer_dict['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
    return viewer_dict
# ==========================================================

async def init_tables() -> None:
    """S'assure que les tables d'historique existent au démarrage."""
    try:
        async with get_db_connection() as db:
            
            # --- 🚀 LES 3 LIGNES MAGIQUES ANTI "DATABASE IS LOCKED" ---
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.execute("PRAGMA busy_timeout=20000;") # Force SQLite à patienter 20s au lieu de planter

            # Table principale (Totaux)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS viewers (
                    twitch_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    nickname TEXT,
                    messages INTEGER DEFAULT 0,
                    watchtime INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table Journalière (Agrégation automatique)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS viewer_daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    twitch_id TEXT,
                    day DATE DEFAULT (date('now', 'localtime')),
                    messages INTEGER DEFAULT 0,
                    watchtime INTEGER DEFAULT 0,
                    points_gained INTEGER DEFAULT 0,
                    UNIQUE(twitch_id, day)
                )
            ''')

            # Table des Événements (Logs précis : Subs, Raids, etc.)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS viewer_exp_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    twitch_id TEXT,
                    event_type TEXT,
                    amount INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur init_tables : {e}")

async def ensure_viewer(twitch_id: str, username: str) -> None:
    """Enregistre le viewer s'il n'existe pas encore (pour débloquer l'EXP)."""
    try:
        async with get_db_connection() as db:
            # Code robuste combinant les deux versions (Insertion ou Mise à jour intelligente)
            await db.execute("""
                INSERT INTO viewers (twitch_id, username, points, messages, watchtime) 
                VALUES (?, ?, 0, 0, 0)
                ON CONFLICT(twitch_id) DO UPDATE SET 
                    username = excluded.username,
                    last_seen = CURRENT_TIMESTAMP
            """, (twitch_id, username))
            await db.commit()
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur ensure_viewer : {e}")

async def get_viewer(twitch_id: str) -> Optional[ViewerResponse]:
    """Récupère un viewer et le convertit au format Pydantic."""
    try:
        async with get_db_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    data = _inject_level(dict(row))
                    try: 
                        return ViewerResponse(**data)
                    except Exception as e: 
                        logger.error(f"Erreur Pydantic get_viewer: {e}")
                        return data
                return None
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur get_viewer : {e}")
        return None

async def get_viewer_by_name(username: str) -> Optional[ViewerResponse]:
    """Récupère un viewer via son pseudo (utilisé par l'IA Félix)."""
    try:
        async with get_db_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM viewers WHERE LOWER(username) = LOWER(?)", (username,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    data = _inject_level(dict(row))
                    try: 
                        return ViewerResponse(**data)
                    except Exception as e: 
                        logger.error(f"Erreur Pydantic get_viewer_by_name: {e}")
                        return data
                return None
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur get_viewer_by_name : {e}")
        return None

async def get_all_viewers():
    """Récupère tous les viewers pour le dashboard et l'API JSON."""
    try:
        async with get_db_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM viewers ORDER BY points DESC, watchtime DESC") as cursor:
                rows = await cursor.fetchall()
                return [_inject_level(dict(row)) for row in rows]
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur get_all_viewers : {e}")
        return []

async def create_viewer(viewer: ViewerCreate) -> Optional[ViewerResponse]:
    """Crée manuellement un viewer depuis l'API JSON."""
    try:
        async with get_db_connection() as db:
            msgs = getattr(viewer, "messages", getattr(viewer, "message_count", 0))
            await db.execute("""
                INSERT INTO viewers (
                    twitch_id, username, nickname, watchtime, messages, points
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                viewer.twitch_id, viewer.username, viewer.nickname, 
                viewer.watchtime, msgs, viewer.points
            ))
            await db.commit()
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur create_viewer : {e}")
    return await get_viewer(viewer.twitch_id)

async def update_viewer_stats(username: str, messages_add: int = 0, watchtime_add: int = 0, points_add: int = 0) -> bool:
    """Moteur central d'EXP : Lecture classique, mais ÉCRITURE via le Single Writer (Mission A)."""
    try:
        # On lit l'ID en direct car on en a besoin tout de suite
        async with get_db_connection() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT twitch_id FROM viewers WHERE LOWER(username) = ?", (username.lower(),))
            row = await cursor.fetchone()

        if row:
            t_id = row['twitch_id']
            # 1. Mise à jour globale envoyée à la file d'attente
            await queue_write("""
                UPDATE viewers 
                SET messages = messages + ?, watchtime = watchtime + ?, points = points + ?, last_seen = CURRENT_TIMESTAMP
                WHERE twitch_id = ?
            """, (messages_add, watchtime_add, points_add, t_id))

            # 2. Agrégation journalière envoyée à la file d'attente
            await queue_write("""
                INSERT INTO viewer_daily_stats (twitch_id, day, messages, watchtime, points_gained)
                VALUES (?, date('now', 'localtime'), ?, ?, ?)
                ON CONFLICT(twitch_id, day) DO UPDATE SET
                    messages = messages + excluded.messages,
                    watchtime = watchtime + excluded.watchtime,
                    points_gained = points_gained + excluded.points_gained
            """, (t_id, messages_add, watchtime_add, points_add))

            return True
        return False
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur update_viewer_stats : {e}")
        return False

async def add_experience(twitch_id: str, username: str, amount: int, event_type: str = "event", details: str = "") -> None:
    """Moteur de distribution d'EXP : Utilise exclusivement la file d'attente (Single Writer)."""
    try:
        # 1. Mise à jour ou création du viewer via la file d'attente
        await queue_write("""
            INSERT INTO viewers (twitch_id, username, points) VALUES (?, ?, ?)
            ON CONFLICT(twitch_id) DO UPDATE SET 
                points = points + excluded.points, 
                username = excluded.username
        """, (twitch_id, username, amount))

        # 2. Enregistrement dans l'historique via la file d'attente
        await queue_write("""
            INSERT INTO viewer_exp_log (twitch_id, event_type, amount, details)
            VALUES (?, ?, ?, ?)
        """, (twitch_id, event_type, amount, details))
        
        logger.info(f"📈 [EXP EN FILE] {username} (+{amount}) via {event_type}")
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur add_experience : {e}")

async def update_viewer(twitch_id: str, update_data: ViewerUpdate) -> Optional[ViewerResponse]:
    """Mise à jour via modèle Pydantic (Frontend / API)."""
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict: return await get_viewer(twitch_id)
        
    safe_dict = {}
    for k, v in update_dict.items():
        if k == "message_count": safe_dict["messages"] = v # Rétrocompatibilité
        elif k in ["is_vip", "vip_expiry_date", "roast_level"]: continue
        else: safe_dict[k] = v

    if not safe_dict: return await get_viewer(twitch_id)

    set_clause = ", ".join([f"{key} = ?" for key in safe_dict.keys()])
    values = list(safe_dict.values())
    values.append(twitch_id)

    try:
        async with get_db_connection() as db:
            await db.execute(f"UPDATE viewers SET {set_clause} WHERE twitch_id = ?", values)
            await db.commit()
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur update_viewer Pydantic : {e}")
            
    return await get_viewer(twitch_id)

async def update_viewer_profile(twitch_id: str, **kwargs):
    """Mise à jour directe via paramètres (Contexte IA)."""
    if not kwargs: return

    set_clauses = []
    values = []
    for key, value in kwargs.items():
        set_clauses.append(f"{key} = ?")
        values.append(value)
        
    values.append(twitch_id)
    query = f"UPDATE viewers SET {', '.join(set_clauses)} WHERE twitch_id = ?"
    
    try:
        async with get_db_connection() as db:
            await db.execute(query, tuple(values))
            await db.commit()
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur update_viewer_profile : {e}")

async def increment_stats(twitch_id: str, watchtime_add: int = 0, messages_add: int = 0) -> None:
    """Ancienne fonction de fallback de watchtime/messages."""
    try:
        async with get_db_connection() as db:
            await db.execute("""
                UPDATE viewers
                SET watchtime = watchtime + ?,
                    messages = messages + ?
                WHERE twitch_id = ?
            """, (watchtime_add, messages_add, twitch_id))
            await db.commit()
    except Exception as e:
        logger.error(f"❌ [DB ERROR] Erreur increment_stats : {e}")
