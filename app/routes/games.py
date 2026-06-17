"""
app/routes/games.py — Routes FastAPI génériques pour tous les jeux quotidiens
(Kikecé, Oukecé, Kekecé, Kikadi)

Remplace app/routes/kikece.py. Le proxy Felix (/felix) reste partagé.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import json

from app.core.database import get_db_connection
from app.core.config import settings

router = APIRouter(prefix="/api/v1/games", tags=["games"])

TZ = ZoneInfo("Europe/Paris")

VALID_GAMES = {"kikece", "oukece", "kekece", "kikadi"}


def check_game_type(game_type: str):
    if game_type not in VALID_GAMES:
        raise HTTPException(status_code=404, detail=f"Jeu inconnu : {game_type}")


def today_paris() -> date:
    return datetime.now(TZ).date()


def next_reset_utc() -> str:
    now = datetime.now(TZ)
    reset = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if now.hour >= 2:
        reset += timedelta(days=1)
    return reset.astimezone(ZoneInfo("UTC")).isoformat()


# ── Schemas ──────────────────────────────────────────────────────────────────

class DailyItemSet(BaseModel):
    name: str
    universe: str
    category: str
    extra: str | None = None
    image_url: str | None = None


class GameResultSubmit(BaseModel):
    twitch_id: str
    twitch_username: str
    questions_count: int
    penalties_count: int
    found: bool


class FelixMessage(BaseModel):
    messages: list
    system: str
    max_tokens: int | None = 80


# ── Init tables ───────────────────────────────────────────────────────────────

async def init_games_tables():
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS games_daily (
                id          SERIAL PRIMARY KEY,
                game_type   TEXT NOT NULL,
                game_date   DATE NOT NULL,
                name        TEXT NOT NULL,
                universe    TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT '',
                extra       TEXT,
                image_url   TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (game_type, game_date)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS games_sessions (
                id               SERIAL PRIMARY KEY,
                game_type        TEXT NOT NULL,
                twitch_id        TEXT NOT NULL,
                twitch_username  TEXT NOT NULL,
                game_date        DATE NOT NULL,
                questions_count  INTEGER NOT NULL DEFAULT 0,
                penalties_count  INTEGER NOT NULL DEFAULT 0,
                found            BOOLEAN NOT NULL DEFAULT FALSE,
                played_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (game_type, twitch_id, game_date)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_games_daily_type_date ON games_daily (game_type, game_date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_games_sessions_type_date ON games_sessions (game_type, game_date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_games_sessions_type_twitch_date ON games_sessions (game_type, twitch_id, game_date)")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{game_type}/daily")
async def get_daily(game_type: str):
    check_game_type(game_type)
    today = today_paris()
    yesterday = today - timedelta(days=1)

    async with get_db_connection() as db:
        await db.execute(
            "SELECT * FROM games_daily WHERE game_type = ? AND game_date = ?",
            game_type, today
        )
        today_row = await db.fetchone()

        await db.execute(
            "SELECT name, universe, category, extra, image_url FROM games_daily WHERE game_type = ? AND game_date = ?",
            game_type, yesterday
        )
        yesterday_row = await db.fetchone()

    return {
        "game_type": game_type,
        "today": {
            "game_date": str(today),
            "name": today_row["name"] if today_row else None,
            "universe": today_row["universe"] if today_row else None,
            "category": today_row["category"] if today_row else None,
            "extra": today_row["extra"] if today_row else None,
            "image_url": today_row["image_url"] if today_row else None,
            "is_set": today_row is not None,
        },
        "yesterday": {
            "name": yesterday_row["name"] if yesterday_row else None,
            "universe": yesterday_row["universe"] if yesterday_row else None,
            "category": yesterday_row["category"] if yesterday_row else None,
            "image_url": yesterday_row["image_url"] if yesterday_row else None,
        },
        "next_reset_utc": next_reset_utc(),
    }


@router.post("/{game_type}/daily")
async def set_daily(game_type: str, payload: DailyItemSet):
    check_game_type(game_type)
    today = today_paris()
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
        """, game_type, today, payload.name, payload.universe, payload.category, payload.extra, payload.image_url)
    return {"status": "ok", "game_type": game_type, "game_date": str(today)}


@router.get("/{game_type}/leaderboard")
async def get_leaderboard(game_type: str):
    check_game_type(game_type)
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute("""
            SELECT twitch_username, questions_count, penalties_count, found, played_at
            FROM games_sessions
            WHERE game_type = ? AND game_date = ?
            ORDER BY found DESC, (questions_count + penalties_count) ASC, played_at ASC
        """, game_type, today)
        rows = await db.fetchall()

    total_played = len(rows)
    total_found = sum(1 for r in rows if r["found"])

    return {
        "game_type": game_type,
        "date": str(today),
        "total_played": total_played,
        "total_found": total_found,
        "leaderboard": [
            {
                "rank": i + 1,
                "username": r["twitch_username"],
                "questions": r["questions_count"],
                "penalties": r["penalties_count"],
                "total": r["questions_count"] + r["penalties_count"],
                "found": r["found"],
                "played_at": r["played_at"].isoformat() if r["played_at"] else None,
            }
            for i, r in enumerate(rows)
        ],
    }


@router.get("/{game_type}/session/{twitch_id}")
async def get_session(game_type: str, twitch_id: str):
    check_game_type(game_type)
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute(
            "SELECT * FROM games_sessions WHERE game_type = ? AND twitch_id = ? AND game_date = ?",
            game_type, twitch_id, today
        )
        row = await db.fetchone()

    if not row:
        return {"has_played": False}
    return {
        "has_played": True,
        "found": row["found"],
        "questions": row["questions_count"],
        "penalties": row["penalties_count"],
        "total": row["questions_count"] + row["penalties_count"],
        "played_at": row["played_at"].isoformat() if row["played_at"] else None,
    }


@router.post("/{game_type}/session")
async def submit_session(game_type: str, payload: GameResultSubmit):
    check_game_type(game_type)
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute(
            "SELECT id FROM games_sessions WHERE game_type = ? AND twitch_id = ? AND game_date = ?",
            game_type, payload.twitch_id, today
        )
        existing = await db.fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Déjà joué aujourd'hui.")
        await db.execute("""
            INSERT INTO games_sessions
              (game_type, twitch_id, twitch_username, game_date, questions_count, penalties_count, found)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, game_type, payload.twitch_id, payload.twitch_username, today,
            payload.questions_count, payload.penalties_count, payload.found)
    return {"status": "ok"}


@router.get("/{game_type}/history")
async def get_history(game_type: str, limit: int = 10):
    check_game_type(game_type)
    async with get_db_connection() as db:
        await db.execute("""
            SELECT game_date, name, universe, category, image_url
            FROM games_daily
            WHERE game_type = ? AND game_date < ?
            ORDER BY game_date DESC
            LIMIT ?
        """, game_type, today_paris(), limit)
        rows = await db.fetchall()

    return {
        "game_type": game_type,
        "history": [
            {
                "game_date": str(r["game_date"]),
                "name": r["name"],
                "universe": r["universe"],
                "category": r["category"],
                "image_url": r["image_url"],
            }
            for r in rows
        ]
    }


# ── Proxy Felix (partagé par tous les jeux) ──────────────────────────────────

@router.post("/felix")
async def felix_proxy(payload: FelixMessage):
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "max_tokens": payload.max_tokens or 80,
                "messages": [
                    {"role": "system", "content": payload.system},
                    *payload.messages
                ],
                "temperature": 0.8,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return {"reply": data["choices"][0]["message"]["content"].strip()}
