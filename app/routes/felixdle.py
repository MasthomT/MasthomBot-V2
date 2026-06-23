"""
app/routes/felixdle.py — Backend du jeu Felixdle (Wordle aux couleurs de FEL-X).

Le mot du jour n'est JAMAIS exposé tant que la partie n'est pas terminée :
toute l'évaluation des essais (lettre bien placée / mal placée / absente) se
fait côté serveur, comme un vrai Wordle. L'ancienne version (page autonome
avec le mot codé en clair dans le JS) était trivialement trichable via
l'inspecteur du navigateur — corrigé ici par construction.
"""

import asyncio
import json
import logging
import random
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.security import require_admin
from app.core.rate_limit import limiter

logger = logging.getLogger("masthbot.felixdle")

TZ = ZoneInfo("Europe/Paris")
MAX_GUESSES = 6

public_router = APIRouter(prefix="/api/v1/felixdle", tags=["felixdle"])
admin_router = APIRouter(prefix="/admin/api/felixdle", tags=["admin_felixdle"], dependencies=[Depends(require_admin)])


def today_paris() -> date:
    return datetime.now(TZ).date()


def next_reset_utc() -> str:
    now = datetime.now(TZ)
    reset = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if now.hour >= 2:
        reset += timedelta(days=1)
    return reset.astimezone(ZoneInfo("UTC")).isoformat()


def normalize_word(word: str) -> str:
    return word.strip().upper()


def evaluate_guess(guess: str, word: str) -> list[str]:
    """Reproduit exactement la logique evaluate() du frontend, côté serveur."""
    length = len(word)
    result = ["bad"] * length
    word_letters = list(word)
    guess_letters = list(guess)
    used = [False] * length

    for i in range(length):
        if guess_letters[i] == word_letters[i]:
            result[i] = "good"
            used[i] = True

    for i in range(length):
        if result[i] == "good":
            continue
        for j in range(length):
            if not used[j] and word_letters[j] == guess_letters[i]:
                result[i] = "close"
                used[j] = True
                break

    return result


async def init_felixdle_tables() -> None:
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS felixdle_words (
                id          SERIAL PRIMARY KEY,
                word        TEXT NOT NULL UNIQUE,
                is_active   BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS felixdle_daily (
                id          SERIAL PRIMARY KEY,
                game_date   DATE NOT NULL UNIQUE,
                word        TEXT NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS felixdle_sessions (
                id              SERIAL PRIMARY KEY,
                twitch_id       TEXT NOT NULL,
                twitch_username TEXT NOT NULL,
                game_date       DATE NOT NULL,
                guesses         TEXT NOT NULL DEFAULT '[]',
                won             BOOLEAN NOT NULL DEFAULT FALSE,
                finished        BOOLEAN NOT NULL DEFAULT FALSE,
                played_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (twitch_id, game_date)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_felixdle_sessions_date ON felixdle_sessions (game_date)")

        # Pool de mots de départ (réutilisée seulement si la table est vide, pour ne jamais
        # écraser une liste que l'admin aurait déjà personnalisée).
        await db.execute("SELECT id FROM felixdle_words LIMIT 1")
        existing = await db.fetchone()
        if not existing:
            starter_words = [
                "FELIX", "STREAM", "TWITCH", "CLIPS", "MANETTE", "TROPHEE", "VICTOIRE",
                "DEFAITE", "JOUEUR", "ARENE", "QUETE", "COMBO", "RESPAWN", "RAGE", "HYPE",
                "CLUTCH", "SQUAD", "RANKED", "DONJON", "BOSS", "NIVEAU", "CHATEUR",
            ]
            for w in starter_words:
                await db.execute(
                    "INSERT INTO felixdle_words (word) VALUES (?) ON CONFLICT (word) DO NOTHING",
                    normalize_word(w)
                )


async def pick_daily_word() -> str | None:
    """Choisit un mot au hasard dans le pool, en évitant les 30 derniers jours utilisés."""
    async with get_db_connection() as db:
        await db.execute(
            "SELECT word FROM felixdle_daily ORDER BY game_date DESC LIMIT 30"
        )
        recent_rows = await db.fetchall()
        recent_words = {r["word"] for r in recent_rows}

        await db.execute("SELECT word FROM felixdle_words WHERE is_active = TRUE")
        pool_rows = await db.fetchall()
        pool = [r["word"] for r in pool_rows]

    available = [w for w in pool if w not in recent_words]
    if not available:
        available = pool  # pool trop petit pour éviter les doublons : on accepte un repeat plutôt que rien

    if not available:
        return None
    return random.choice(available)


async def ensure_today_word() -> None:
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute("SELECT id FROM felixdle_daily WHERE game_date = ?", today)
        existing = await db.fetchone()
        if existing:
            return

    word = await pick_daily_word()
    if not word:
        logger.error("❌ [FELIXDLE] Aucun mot disponible dans le pool, impossible de générer le mot du jour.")
        return

    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO felixdle_daily (game_date, word) VALUES (?, ?) ON CONFLICT (game_date) DO NOTHING",
            today, word
        )
    logger.info(f"🔤 [FELIXDLE] Mot du jour défini ({today}) : {word}")


def seconds_until_next_2am() -> float:
    now = datetime.now(TZ)
    next_reset = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if now.hour >= 2:
        next_reset += timedelta(days=1)
    return max((next_reset - now).total_seconds(), 0)


async def felixdle_scheduler_routine():
    logger.info("🔤 [FELIXDLE SCHEDULER] Démarrage.")
    await ensure_today_word()
    while True:
        wait = seconds_until_next_2am()
        await asyncio.sleep(wait)
        await ensure_today_word()


# ── Schemas ──────────────────────────────────────────────────────────────────

class GuessPayload(BaseModel):
    twitch_id: str
    twitch_username: str
    guess: str


class WordSetPayload(BaseModel):
    word: str


class WordPoolAddPayload(BaseModel):
    word: str


# ── API publique ─────────────────────────────────────────────────────────────

@public_router.get("/daily")
async def get_daily():
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute("SELECT word FROM felixdle_daily WHERE game_date = ?", today)
        row = await db.fetchone()

    return {
        "game_date": str(today),
        "is_set": row is not None,
        "word_length": len(row["word"]) if row else None,
        "max_guesses": MAX_GUESSES,
        "next_reset_utc": next_reset_utc(),
    }


@public_router.get("/session/{twitch_id}")
async def get_session(twitch_id: str):
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute(
            "SELECT * FROM felixdle_sessions WHERE twitch_id = ? AND game_date = ?",
            twitch_id, today
        )
        session = await db.fetchone()
        if not session:
            return {"has_played": False, "guesses": [], "finished": False, "won": False}

        await db.execute("SELECT word FROM felixdle_daily WHERE game_date = ?", today)
        daily = await db.fetchone()
        word = daily["word"] if daily else None

    guesses = json.loads(session["guesses"])
    evaluations = [evaluate_guess(g, word) for g in guesses] if word else []

    return {
        "has_played": True,
        "guesses": guesses,
        "evaluations": evaluations,
        "finished": session["finished"],
        "won": session["won"],
        "word": word if session["finished"] else None,
    }


@public_router.post("/guess")
@limiter.limit("30/minute")
async def submit_guess(request: Request, payload: GuessPayload):
    today = today_paris()
    guess = normalize_word(payload.guess)

    async with get_db_connection() as db:
        await db.execute("SELECT word FROM felixdle_daily WHERE game_date = ?", today)
        daily = await db.fetchone()
        if not daily:
            raise HTTPException(status_code=400, detail="Aucun mot défini pour aujourd'hui.")
        word = daily["word"]

        if len(guess) != len(word):
            raise HTTPException(status_code=400, detail=f"Le mot fait {len(word)} lettres.")

        await db.execute(
            "SELECT * FROM felixdle_sessions WHERE twitch_id = ? AND game_date = ?",
            payload.twitch_id, today
        )
        session = await db.fetchone()

        if session and session["finished"]:
            raise HTTPException(status_code=409, detail="Partie déjà terminée pour aujourd'hui.")

        guesses = json.loads(session["guesses"]) if session else []
        if len(guesses) >= MAX_GUESSES:
            raise HTTPException(status_code=409, detail="Plus d'essais disponibles.")

        result = evaluate_guess(guess, word)
        won = guess == word
        guesses.append(guess)
        finished = won or len(guesses) >= MAX_GUESSES

        if session:
            await db.execute(
                "UPDATE felixdle_sessions SET guesses = ?, won = ?, finished = ? WHERE twitch_id = ? AND game_date = ?",
                json.dumps(guesses), won, finished, payload.twitch_id, today
            )
        else:
            await db.execute(
                "INSERT INTO felixdle_sessions (twitch_id, twitch_username, game_date, guesses, won, finished) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                payload.twitch_id, payload.twitch_username, today, json.dumps(guesses), won, finished
            )

    return {
        "result": result,
        "won": won,
        "finished": finished,
        "attempts_left": MAX_GUESSES - len(guesses),
        "word": word if finished else None,
    }


@public_router.get("/leaderboard")
async def get_leaderboard():
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute("""
            SELECT twitch_username, guesses, won, played_at
            FROM felixdle_sessions
            WHERE game_date = ? AND finished = TRUE
            ORDER BY won DESC, played_at ASC
        """, today)
        rows = await db.fetchall()

    leaderboard = []
    for i, r in enumerate(rows):
        guesses = json.loads(r["guesses"])
        leaderboard.append({
            "rank": i + 1,
            "username": r["twitch_username"],
            "attempts": len(guesses),
            "won": r["won"],
            "played_at": r["played_at"].isoformat() if r["played_at"] else None,
        })

    return {
        "date": str(today),
        "total_played": len(rows),
        "total_won": sum(1 for r in rows if r["won"]),
        "leaderboard": leaderboard,
    }


@public_router.get("/history")
async def get_history(limit: int = 10):
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute(
            "SELECT game_date, word FROM felixdle_daily WHERE game_date < ? ORDER BY game_date DESC LIMIT ?",
            today, limit
        )
        rows = await db.fetchall()

    return {"history": [{"game_date": str(r["game_date"]), "word": r["word"]} for r in rows]}


# ── Administration ───────────────────────────────────────────────────────────

@admin_router.get("/daily")
async def admin_get_daily():
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute("SELECT word FROM felixdle_daily WHERE game_date = ?", today)
        row = await db.fetchone()
    return {"game_date": str(today), "word": row["word"] if row else None, "is_set": row is not None}


@admin_router.post("/daily")
async def admin_set_daily(payload: WordSetPayload):
    word = normalize_word(payload.word)
    if not word.isalpha():
        raise HTTPException(status_code=400, detail="Le mot ne doit contenir que des lettres.")
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO felixdle_daily (game_date, word) VALUES (?, ?) "
            "ON CONFLICT (game_date) DO UPDATE SET word = EXCLUDED.word",
            today, word
        )
    return {"status": "ok", "word": word}


@admin_router.get("/words")
async def admin_list_words():
    async with get_db_connection() as db:
        await db.execute("SELECT * FROM felixdle_words ORDER BY word ASC")
        rows = await db.fetchall()
    return {"words": [dict(r) for r in rows]}


@admin_router.post("/words")
async def admin_add_word(payload: WordPoolAddPayload):
    word = normalize_word(payload.word)
    if not word.isalpha():
        raise HTTPException(status_code=400, detail="Le mot ne doit contenir que des lettres.")
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO felixdle_words (word) VALUES (?) ON CONFLICT (word) DO NOTHING",
            word
        )
    return {"status": "ok"}


@admin_router.delete("/words/{word_id}")
async def admin_delete_word(word_id: int):
    async with get_db_connection() as db:
        await db.execute("DELETE FROM felixdle_words WHERE id = ?", word_id)
    return {"status": "ok"}


@admin_router.post("/words/{word_id}/toggle")
async def admin_toggle_word(word_id: int):
    async with get_db_connection() as db:
        await db.execute("UPDATE felixdle_words SET is_active = NOT is_active WHERE id = ?", word_id)
    return {"status": "ok"}
