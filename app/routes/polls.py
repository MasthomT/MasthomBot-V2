import sqlite3
import logging
import asyncio
from datetime import datetime
from fastapi import APIRouter, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.notification_service import notification_service

logger = logging.getLogger("masthbot.polls")
router = APIRouter(tags=["polls_faq"])
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================================
# 🖥️ PAGE PRINCIPALE : SONDAGES & FAQ (ADMIN)
# ==========================================================

@router.get("/admin/polls_faq", response_class=HTMLResponse)
async def admin_polls_faq_page(request: Request):
    """
    Affiche l'interface fusionnée sur le Raspberry Pi.
    """
    conn = get_db()
    try:
        # 1. RÉCUPÉRATION DU SONDAGE ACTIF
        active_poll = conn.execute(
            "SELECT * FROM polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        
        poll_data = None
        if active_poll:
            poll_data = dict(active_poll)
            votes_rows = conn.execute("""
                SELECT pv.option_index, v.username 
                FROM poll_votes pv
                LEFT JOIN viewers v ON pv.twitch_id = v.twitch_id
                WHERE pv.poll_id = ?
            """, (poll_data['id'],)).fetchall()
            
            results = {"1": 0, "2": 0, "3": 0, "4": 0}
            voters = {"1": [], "2": [], "3": [], "4": []}
            total_votes = 0
            
            # ✅ BOUCLE DE COMPTAGE (Ligne qui posait l'IndentationError)
            for v in votes_rows:
                idx = str(v['option_index'])
                if idx in results:
                    results[idx] += 1
                    voters[idx].append(v['username'] or "Inconnu")
                    total_votes += 1
            
            poll_data.update({
                "results": results, 
                "voters": voters, 
                "total_votes": total_votes
            })

        # 2. RÉCUPÉRATION DES QUESTIONS
        pending = [dict(q) for q in conn.execute(
            "SELECT * FROM questions WHERE answer_text IS NULL ORDER BY created_at DESC"
        ).fetchall()]
        
        answered = [dict(q) for q in conn.execute(
            "SELECT * FROM questions WHERE answer_text IS NOT NULL ORDER BY answered_at DESC LIMIT 20"
        ).fetchall()]

        return templates.TemplateResponse(
            request=request,
            name="admin/polls_faq.html", 
            context={
                "request": request, 
                "active_poll": poll_data, 
                "pending_questions": pending,
                "answered_questions": answered
            }
        )
    finally:
        conn.close()

# ==========================================================
# 🗳️ ACTIONS : SONDAGES
# ==========================================================

@router.post("/admin/polls_faq/create")
async def create_poll(
    question: str = Form(...), 
    option1: str = Form(...), 
    option2: str = Form(...), 
    option3: str = Form(""), 
    option4: str = Form("")
):
    conn = get_db()
    try:
        conn.execute("UPDATE polls SET is_active = 0")
        conn.execute("""
            INSERT INTO polls (question, option1, option2, option3, option4, is_active) 
            VALUES (?, ?, ?, ?, ?, 1)
        """, (question, option1, option2, option3, option4))
        conn.commit()
        return RedirectResponse(url="/admin/polls_faq?created=1", status_code=303)
    finally:
        conn.close()

@router.post("/admin/polls_faq/close")
async def close_poll():
    conn = get_db()
    try:
        conn.execute("UPDATE polls SET is_active = 0")
        conn.commit()
        return RedirectResponse(url="/admin/polls_faq?closed=1", status_code=303)
    finally:
        conn.close()

# ==========================================================
# ❓ ACTIONS : QUESTIONS / FAQ
# ==========================================================

@router.post("/admin/polls_faq/questions/answer")
async def answer_question(
    background_tasks: BackgroundTasks,
    id: int = Form(...), 
    answer: str = Form(...), 
    is_public: int = Form(0)
):
    """
    Enregistre la réponse et publie sur Discord si coché.
    """
    conn = get_db()
    try:
        q_row = conn.execute("SELECT question_text FROM questions WHERE id = ?", (id,)).fetchone()
        
        conn.execute("""
            UPDATE questions 
            SET answer_text = ?, is_public = ?, answered_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (answer, is_public, id))
        conn.commit()

        # ✅ SI PUBLIC : Publication Discord en tâche de fond (Anonyme)
        if is_public and q_row:
            background_tasks.add_task(
                notification_service.send_faq_public_answer,
                q_row['question_text'], 
                answer
            )

        return RedirectResponse(url="/admin/polls_faq?success=1", status_code=303)
    finally:
        conn.close()

@router.post("/admin/polls_faq/questions/delete/{id}")
async def delete_question(id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM questions WHERE id = ?", (id,))
        conn.commit()
        return RedirectResponse(url="/admin/polls_faq?deleted=1", status_code=303)
    finally:
        conn.close()
