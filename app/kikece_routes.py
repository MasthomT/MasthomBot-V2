"""
kikece_routes.py — Routes FastAPI pour le jeu Kikecé
À importer dans ton main.py : from kikece_routes import router as kikece_router
Puis : app.include_router(kikece_router, prefix="/api/v1/kikece", tags=["kikece"])
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import datetime, date, timezone
import pytz

router = APIRouter()

# Fuseau horaire France (pour le reset à 2h du matin)
TZ_PARIS = pytz.timezone("Europe/Paris")


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_today_paris() -> date:
    """Retourne la date courante en heure de Paris."""
    return datetime.now(TZ_PARIS).date()


def get_db():
    """Dépendance DB — adapte à ton système existant (SessionLocal, etc.)"""
    from database import SessionLocal  # adapte l'import à ton projet
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas Pydantic ─────────────────────────────────────────────────────────

class DailyCharacterSet(BaseModel):
    name: str
    universe: str
    char_type: str          # "jeu vidéo" | "animé" | "série"
    image_url: str | None = None


class GameResultSubmit(BaseModel):
    twitch_id: str
    twitch_username: str
    questions_count: int
    penalties_count: int
    found: bool             # True = trouvé, False = abandonné


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/daily")
async def get_daily_character(db: Session = Depends(get_db)):
    """
    Retourne le personnage du jour et celui d'hier.
    Le personnage est identifié par la date Paris.
    """
    today = get_today_paris()
    yesterday = date.fromordinal(today.toordinal() - 1)

    today_row = db.execute(
        text("SELECT * FROM kikece_daily WHERE game_date = :d"),
        {"d": today}
    ).fetchone()

    yesterday_row = db.execute(
        text("SELECT name, universe, image_url FROM kikece_daily WHERE game_date = :d"),
        {"d": yesterday}
    ).fetchone()

    # Calcul du prochain reset (2h00 heure de Paris)
    now_paris = datetime.now(TZ_PARIS)
    next_reset = now_paris.replace(hour=2, minute=0, second=0, microsecond=0)
    if now_paris.hour >= 2:
        from datetime import timedelta
        next_reset += timedelta(days=1)
    next_reset_utc = next_reset.astimezone(timezone.utc).isoformat()

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
        "next_reset_utc": next_reset_utc,
    }


@router.post("/daily")
async def set_daily_character(payload: DailyCharacterSet, db: Session = Depends(get_db)):
    """
    Définit le personnage du jour (admin only — protège cet endpoint !).
    Upsert : si un perso existe déjà aujourd'hui, il est remplacé.
    """
    today = get_today_paris()
    db.execute(
        text("""
            INSERT INTO kikece_daily (game_date, name, universe, char_type, image_url)
            VALUES (:d, :name, :universe, :char_type, :image_url)
            ON CONFLICT (game_date) DO UPDATE
              SET name = EXCLUDED.name,
                  universe = EXCLUDED.universe,
                  char_type = EXCLUDED.char_type,
                  image_url = EXCLUDED.image_url
        """),
        {"d": today, "name": payload.name, "universe": payload.universe,
         "char_type": payload.char_type, "image_url": payload.image_url}
    )
    db.commit()
    return {"status": "ok", "game_date": str(today)}


@router.get("/leaderboard")
async def get_daily_leaderboard(db: Session = Depends(get_db)):
    """
    Classement du jour : les joueurs qui ont trouvé le personnage,
    triés par score total (questions + pénalités) croissant.
    Inclut aussi le nombre de joueurs total et le taux de réussite.
    """
    today = get_today_paris()

    rows = db.execute(
        text("""
            SELECT twitch_username,
                   questions_count,
                   penalties_count,
                   (questions_count + penalties_count) AS total_score,
                   found,
                   played_at
            FROM kikece_sessions
            WHERE game_date = :d
            ORDER BY found DESC, total_score ASC, played_at ASC
        """),
        {"d": today}
    ).fetchall()

    total_played = len(rows)
    total_found = sum(1 for r in rows if r["found"])

    leaderboard = [
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
    ]

    return {
        "date": str(today),
        "total_played": total_played,
        "total_found": total_found,
        "leaderboard": leaderboard,
    }


@router.get("/session/{twitch_id}")
async def get_user_session(twitch_id: str, db: Session = Depends(get_db)):
    """
    Vérifie si l'utilisateur a déjà joué aujourd'hui.
    Retourne sa session si elle existe.
    """
    today = get_today_paris()
    row = db.execute(
        text("""
            SELECT * FROM kikece_sessions
            WHERE twitch_id = :tid AND game_date = :d
        """),
        {"tid": twitch_id, "d": today}
    ).fetchone()

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
async def submit_session(payload: GameResultSubmit, db: Session = Depends(get_db)):
    """
    Enregistre le résultat d'une partie.
    Ignore si l'utilisateur a déjà joué aujourd'hui (sécurité côté serveur).
    """
    today = get_today_paris()

    existing = db.execute(
        text("SELECT id FROM kikece_sessions WHERE twitch_id = :tid AND game_date = :d"),
        {"tid": payload.twitch_id, "d": today}
    ).fetchone()

    if existing:
        raise HTTPException(status_code=409, detail="Déjà joué aujourd'hui.")

    db.execute(
        text("""
            INSERT INTO kikece_sessions
              (twitch_id, twitch_username, game_date, questions_count, penalties_count, found, played_at)
            VALUES (:tid, :uname, :d, :q, :p, :found, NOW())
        """),
        {
            "tid": payload.twitch_id,
            "uname": payload.twitch_username,
            "d": today,
            "q": payload.questions_count,
            "p": payload.penalties_count,
            "found": payload.found,
        }
    )
    db.commit()
    return {"status": "ok"}
