import logging
import asyncio
from datetime import datetime
from fastapi import APIRouter, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.database import get_db_connection
from app.services.notification_service import notification_service

logger = logging.getLogger("masthbot.polls")
router = APIRouter(tags=["polls_faq"])
templates = Jinja2Templates(directory="app/templates")

# ==========================================================
# 🖥️ PAGE PRINCIPALE : SONDAGES & FAQ (ADMIN)
# ==========================================================

@router.get("/admin/polls_faq", response_class=HTMLResponse)
async def admin_polls_faq_page(request: Request):
    """
    Affiche l'interface fusionnée sur le Raspberry Pi.
    """
    try:
        async with get_db_connection() as conn:
            # 1. RÉCUPÉRATION DU SONDAGE ACTIF
            cursor = await conn.execute(
                "SELECT * FROM polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
            )
            active_poll = await cursor.fetchone()
            
            poll_data = None
            if active_poll:
                poll_data = dict(active_poll)
                cursor_votes = await conn.execute("""
                    SELECT pv.option_index, v.username 
                    FROM poll_votes pv
                    LEFT JOIN viewers v ON pv.twitch_id = v.twitch_id
                    WHERE pv.poll_id = $1
                """, (poll_data['id'],))
                votes_rows = await cursor_votes.fetchall()
                
                results = {"1": 0, "2": 0, "3": 0, "4": 0}
                voters = {"1": [], "2": [], "3": [], "4": []}
                total_votes = 0
                
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

            # Remplace TOUT le bloc de la partie "2. RÉCUPÉRATION DES QUESTIONS" par ceci :
            
            # 2. RÉCUPÉRATION DES QUESTIONS
            
            # -> Les questions en attente (sans réponse)
            cursor_pending = await conn.execute(
                "SELECT * FROM questions WHERE answer_text IS NULL OR answer_text = '' ORDER BY id DESC"
            )
            pending_rows = await cursor_pending.fetchall()
            pending = [dict(q) for q in pending_rows]
            
            # -> L'historique (les questions avec réponse)
            cursor_answered = await conn.execute(
                "SELECT * FROM questions WHERE answer_text IS NOT NULL AND answer_text != '' ORDER BY answered_at DESC LIMIT 20"
            )
            answered_rows = await cursor_answered.fetchall()
            answered = [dict(q) for q in answered_rows]

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
    except Exception as e:
        logger.error(f"❌ Erreur admin_polls_faq_page : {e}")
        return HTMLResponse(content=f"<h1>Erreur lors du chargement des sondages</h1><p>{e}</p>", status_code=500)

# ==========================================================
# 🗳️ ACTIONS : SONDAGES
# ==========================================================

@router.post("/admin/polls_faq/create")
async def create_poll(
    question: str = Form(...),
    option1: str = Form(...),
    option2: str = Form(...),
    option3: str = Form(""),
    option4: str = Form(""),
):
    async with get_db_connection() as conn:
        await conn.execute("UPDATE polls SET is_active = 0")
        await conn.execute(
            "INSERT INTO polls (question, option1, option2, option3, option4, is_active) VALUES ($1, $2, $3, $4, $5, 1)",
            (question, option1, option2, option3 or None, option4 or None),
        )
    return RedirectResponse(url="/admin/polls_faq?created=1", status_code=303)

@router.post("/admin/polls_faq/close")
async def close_poll():
    async with get_db_connection() as conn:
        await conn.execute("UPDATE polls SET is_active = 0")
    return RedirectResponse(url="/admin/polls_faq?closed=1", status_code=303)

# ==========================================================
# ❓ ACTIONS : QUESTIONS / FAQ
# ==========================================================

@router.post("/admin/polls_faq/questions/answer")
async def answer_question(
    background_tasks: BackgroundTasks,
    id: int = Form(...),
    answer: str = Form(...),
    is_public: int = Form(0),
):
    async with get_db_connection() as conn:
        # 1. On récupère le texte AVANT de mettre à jour
        c = await conn.execute("SELECT question_text FROM questions WHERE id = $1", (id,))
        q_row = await c.fetchone()
        question_text = q_row["question_text"] if q_row else "Question inconnue"
            
        # 2. UPDATE explicite avec vérification
        await conn.execute(
            """
            UPDATE questions
            SET answer_text = $1, is_public = $2, answered_at = NOW()
            WHERE id = $3
            """,
            (answer, is_public, id),
        )
        
    # Notification Discord
    if is_public and question_text:
        background_tasks.add_task(
            notification_service.send_faq_public_answer,
            question_text,
            answer,
        )
    
    # Redirection propre
    return RedirectResponse(url="/admin/polls_faq?success=1", status_code=303)

@router.post("/admin/polls_faq/questions/delete/{id}")
async def delete_question(id: int):
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM questions WHERE id = $1", (id,))
    return RedirectResponse(url="/admin/polls_faq?deleted=1", status_code=303)
