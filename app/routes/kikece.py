from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from app.core.database import get_db_connection

router = APIRouter(prefix="/api/v1/kikece", tags=["kikece"])

TZ = ZoneInfo("Europe/Paris")


def today_paris() -> date:
    return datetime.now(TZ).date()


def next_reset_utc() -> str:
    now = datetime.now(TZ)
    reset = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if now.hour >= 2:
        reset += timedelta(days=1)
    return reset.astimezone(ZoneInfo("UTC")).isoformat()


class DailyCharacterSet(BaseModel):
    name: str
    universe: str
    char_type: str
    image_url: str | None = None


class GameResultSubmit(BaseModel):
    twitch_id: str
    twitch_username: str
    questions_count: int
    penalties_count: int
    found: bool


async def init_kikece_tables():
    async with get_db_connection() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kikece_daily (
                id          SERIAL PRIMARY KEY,
                game_date   DATE NOT NULL UNIQUE,
                name        TEXT NOT NULL,
                universe    TEXT NOT NULL,
                char_type   TEXT NOT NULL DEFAULT 'jeu video',
                image_url   TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kikece_sessions (
                id               SERIAL PRIMARY KEY,
                twitch_id        TEXT NOT NULL,
                twitch_username  TEXT NOT NULL,
                game_date        DATE NOT NULL,
                questions_count  INTEGER NOT NULL DEFAULT 0,
                penalties_count  INTEGER NOT NULL DEFAULT 0,
                found            BOOLEAN NOT NULL DEFAULT FALSE,
                played_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (twitch_id, game_date)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_kikece_sessions_date ON kikece_sessions (game_date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_kikece_sessions_twitch_date ON kikece_sessions (twitch_id, game_date)")


@router.get("/daily")
async def get_daily():
    today = today_paris()
    yesterday = today - timedelta(days=1)

    async with get_db_connection() as db:
        await db.execute("SELECT * FROM kikece_daily WHERE game_date = ?", today)
        today_row = await db.fetchone()

        await db.execute("SELECT name, universe, image_url FROM kikece_daily WHERE game_date = ?", yesterday)
        yesterday_row = await db.fetchone()

    return {
        "today": {
            "game_date": str(today),
            "name": today_row["name"] if today_row else None,
            "universe": today_row["universe"] if today_row else None,
            "char_type": today_row["char_type"] if today_row else None,
            "image_url": today_row["image_url"] if today_row else None,
            "is_set": today_row is not None,
        },
        "yesterday": {
            "name": yesterday_row["name"] if yesterday_row else None,
            "universe": yesterday_row["universe"] if yesterday_row else None,
            "image_url": yesterday_row["image_url"] if yesterday_row else None,
        },
        "next_reset_utc": next_reset_utc(),
    }


@router.post("/daily")
async def set_daily(payload: DailyCharacterSet):
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute("""
            INSERT INTO kikece_daily (game_date, name, universe, char_type, image_url)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (game_date) DO UPDATE
              SET name = EXCLUDED.name,
                  universe = EXCLUDED.universe,
                  char_type = EXCLUDED.char_type,
                  image_url = EXCLUDED.image_url
        """, today, payload.name, payload.universe, payload.char_type, payload.image_url)
    return {"status": "ok", "game_date": str(today)}


@router.get("/leaderboard")
async def get_leaderboard():
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute("""
            SELECT twitch_username, questions_count, penalties_count, found, played_at
            FROM kikece_sessions
            WHERE game_date = ?
            ORDER BY found DESC, (questions_count + penalties_count) ASC, played_at ASC
        """, today)
        rows = await db.fetchall()

    total_played = len(rows)
    total_found = sum(1 for r in rows if r["found"])

    return {
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


@router.get("/session/{twitch_id}")
async def get_session(twitch_id: str):
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute(
            "SELECT * FROM kikece_sessions WHERE twitch_id = ? AND game_date = ?",
            twitch_id, today
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


@router.post("/session")
async def submit_session(payload: GameResultSubmit):
    today = today_paris()
    async with get_db_connection() as db:
        await db.execute(
            "SELECT id FROM kikece_sessions WHERE twitch_id = ? AND game_date = ?",
            payload.twitch_id, today
        )
        existing = await db.fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Deja joue aujourd'hui.")
        await db.execute("""
            INSERT INTO kikece_sessions
              (twitch_id, twitch_username, game_date, questions_count, penalties_count, found)
            VALUES (?, ?, ?, ?, ?, ?)
        """, payload.twitch_id, payload.twitch_username, today,
            payload.questions_count, payload.penalties_count, payload.found)
    return {"status": "ok"}

class FelixMessage(BaseModel):
    messages: list
    system: str


@router.post("/felix")
async def felix_proxy(payload: FelixMessage):
    import httpx
    from app.core.config import settings
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "max_tokens": 80,
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
