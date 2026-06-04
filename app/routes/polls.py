import logging
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.database import get_db_connection
from app.services.notification_service import notification_service

# L'import vital pour envoyer les messages sur le salon SONDAGE
from app.services.discord_service import send_message_to_discord 

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

            # 2. RÉCUPÉRATION DE L'HISTORIQUE DES SONDAGES (CE QUI TE MANQUAIT)
            cursor_past = await conn.execute(
                "SELECT * FROM polls WHERE is_active = 0 ORDER BY id DESC LIMIT 10"
            )
            past_polls_raw = await cursor_past.fetchall()
            past_polls = []

            for p in past_polls_raw:
                p_data = dict(p)
                # On recompte les votes pour chaque ancien sondage pour les afficher
                c_votes = await conn.execute("SELECT option_index FROM poll_votes WHERE poll_id = $1", (p_data['id'],))
                p_votes = await c_votes.fetchall()
                
                res = {"1": 0, "2": 0, "3": 0, "4": 0}
                tot = 0
                for v in p_votes:
                    idx = str(v['option_index'])
                    if idx in res:
                        res[idx] += 1
                        tot += 1
                
                p_data['results'] = res
                p_data['total_votes'] = tot
                past_polls.append(p_data)

            # 3. RÉCUPÉRATION DES QUESTIONS FAQ

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
                "past_polls": past_polls, # <-- C'est ça qui remplit l'historique de la page !
                "pending_questions": pending,
                "answered_questions": answered
            }
        )
    except Exception as e:
        logger.error(f"❌ Erreur admin_polls_faq_page : {e}")
        return HTMLResponse(content=f"<h1>Erreur lors du chargement des sondages</h1><p>{e}</p>", status_code=500)

# ==========================================================
# 🗳️ ACTIONS : SONDAGES (CRÉATION ET CLÔTURE)
# ==========================================================

@router.post("/admin/polls_faq/create")
async def create_poll(
    question: str = Form(...),
    option1: str = Form(...),
    option2: str = Form(...),
    option3: str = Form(""),
    option4: str = Form(""),
):
    """Crée un sondage ET lance une annonce sur Discord"""
    async with get_db_connection() as conn:
        # On passe l'ancien sondage en historique
        await conn.execute("UPDATE polls SET is_active = 0")
        
        # On insère le nouveau
        await conn.execute(
            "INSERT INTO polls (question, option1, option2, option3, option4, is_active) VALUES ($1, $2, $3, $4, $5, 1)",
            (question, option1, option2, option3 or None, option4 or None),
        )

    # Préparation du message Discord
    discord_msg = f"📢 **NOUVEAU SONDAGE EN DIRECT !**\n\n**Question :** {question}\n\n"
    discord_msg += f"1️⃣ {option1}\n"
    discord_msg += f"2️⃣ {option2}\n"
    if option3: discord_msg += f"3️⃣ {option3}\n"
    if option4: discord_msg += f"4️⃣ {option4}\n"
    discord_msg += "\n👉 *Votez directement sur votre profil: https://fel-x.icu !*"

    # Envoi Discord
    try:
        await send_message_to_discord("1509812594662183035", discord_msg)
    except Exception as e:
        logger.error(f"❌ Erreur Discord : {e}")

    return RedirectResponse(url="/admin/polls_faq?created=1", status_code=303)


@router.post("/admin/polls_faq/close")
async def close_poll():
    """Clôture le sondage et expédie les résultats calculés sur Discord."""
    async with get_db_connection() as conn:
        # On cherche le sondage actuellement ouvert
        cursor = await conn.execute("SELECT * FROM polls WHERE is_active = 1 LIMIT 1")
        active_poll = await cursor.fetchone()

        if active_poll:
            active_poll_dict = dict(active_poll)
            
            # On calcule les résultats finaux
            cursor_votes = await conn.execute("SELECT option_index FROM poll_votes WHERE poll_id = $1", (active_poll_dict['id'],))
            votes = await cursor_votes.fetchall()

            results = {"1": 0, "2": 0, "3": 0, "4": 0}
            total_votes = 0
            for v in votes:
                idx = str(v['option_index'])
                if idx in results:
                    results[idx] += 1
                    total_votes += 1

            # On le ferme (is_active = 0)
            await conn.execute("UPDATE polls SET is_active = 0 WHERE id = $1", (active_poll_dict['id'],))

            # On prépare le message Discord des résultats
            discord_msg = f"📊 **SONDAGE TERMINÉ**\n\n**Question :** {active_poll_dict['question']}\n\n"

            for i in range(1, 5):
                opt_key = f'option{i}'
                if active_poll_dict.get(opt_key):
                    count = results.get(str(i), 0)
                    pct = int(round((count / total_votes) * 100)) if total_votes > 0 else 0
                    discord_msg += f"🔹 **{active_poll_dict[opt_key]}** : {pct}% ({count} votes)\n"

            discord_msg += f"\n👥 **Total des participants :** {total_votes} votes"

            # Envoi via le service Discord
            try:
                await send_message_to_discord("1509812594662183035", discord_msg)
            except Exception as e:
                logger.error(f"❌ Erreur d'envoi Discord pour le sondage : {e}")
        else:
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
        c = await conn.execute("SELECT question_text FROM questions WHERE id = $1", (id,))
        q_row = await c.fetchone()
        question_text = q_row["question_text"] if q_row else "Question inconnue"

        await conn.execute(
            """
            UPDATE questions
            SET answer_text = $1, is_public = $2, answered_at = NOW()
            WHERE id = $3
            """,
            (answer, is_public, id),
        )

    if is_public and question_text:
        background_tasks.add_task(
            notification_service.send_faq_public_answer,
            question_text,
            answer,
        )

    return RedirectResponse(url="/admin/polls_faq?success=1", status_code=303)

@router.post("/admin/polls_faq/questions/delete/{id}")
async def delete_question(id: int):
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM questions WHERE id = $1", (id,))
    return RedirectResponse(url="/admin/polls_faq?deleted=1", status_code=303)

# ==========================================================
# 📡 API POUR LE RAFRAÎCHISSEMENT EN DIRECT (JAVASCRIPT)
# ==========================================================

@router.get("/api/v1/questions/pending")
async def api_get_pending_questions():
    """Renvoie les questions en attente pour actualiser le HTML sans recharger la page."""
    try:
        async with get_db_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM questions WHERE answer_text IS NULL OR answer_text = '' ORDER BY id DESC"
            )
            rows = await cursor.fetchall()
            return [dict(q) for q in rows]
    except Exception as e:
        logger.error(f"Erreur API questions : {e}")
        return []

@router.get("/api/v1/poll/active")
async def api_get_active_poll():
    """Renvoie l'état du sondage actif pour faire bouger les barres en direct."""
    try:
        async with get_db_connection() as conn:
            cursor = await conn.execute("SELECT * FROM polls WHERE is_active = 1 LIMIT 1")
            active_poll = await cursor.fetchone()

            if not active_poll:
                return {"active": False}
                
            poll_data = dict(active_poll)
            
            # On récupère les votes en temps réel
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

            return {
                "active": True,
                "question": poll_data["question"],
                "options": {
                    "1": poll_data["option1"],
                    "2": poll_data["option2"],
                    "3": poll_data["option3"],
                    "4": poll_data["option4"]
                },
                "results": results,
                "voters": voters,
                "total_votes": total_votes
            }
    except Exception as e:
        logger.error(f"Erreur API sondage actif : {e}")
        return {"active": False}

@router.post("/admin/polls_faq/delete/{poll_id}")
async def delete_poll(poll_id: int):
    """Supprime définitivement un sondage de l'historique et ses votes associés."""
    async with get_db_connection() as conn:
        # On nettoie d'abord les votes liés à ce sondage
        await conn.execute("DELETE FROM poll_votes WHERE poll_id = $1", (poll_id,))
        # On supprime ensuite le sondage lui-même
        await conn.execute("DELETE FROM polls WHERE id = $1", (poll_id,))
        
    return RedirectResponse(url="/admin/polls_faq?deleted=1", status_code=303)
