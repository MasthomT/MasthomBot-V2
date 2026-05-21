import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.database import get_db_connection

router = APIRouter(tags=["polls"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/admin/polls", response_class=HTMLResponse)
async def admin_polls(request: Request):
    async with get_db_connection() as conn:
        # Récupérer le sondage actif
        c1 = await conn.execute("SELECT * FROM polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        active_poll = await c1.fetchone()
        poll_data = None
        
        if active_poll:
            poll_data = dict(active_poll)
            # Calculer les résultats
            c2 = await conn.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id = ? GROUP BY option_index", (poll_data['id'],))
            votes = await c2.fetchall()
            results = {1: 0, 2: 0, 3: 0, 4: 0}
            total_votes = 0
            for v in votes:
                results[v['option_index']] = v['count']
                total_votes += v['count']
                
            poll_data['results'] = results
            poll_data['total_votes'] = total_votes

        # Historique des anciens sondages
        c3 = await conn.execute("SELECT * FROM polls WHERE is_active = 0 ORDER BY id DESC LIMIT 5")
        recent_polls_raw = await c3.fetchall()
        recent_polls = [dict(r) for r in recent_polls_raw]
        
    return templates.TemplateResponse(request=request, name="admin/polls.html", context={
        "request": request, 
        "active_poll": poll_data, 
        "recent_polls": recent_polls
    })

@router.post("/admin/polls/create")
async def create_poll(
    request: Request, 
    question: str = Form(...), 
    option1: str = Form(...), 
    option2: str = Form(...), 
    option3: str = Form(""), 
    option4: str = Form("")
):
    async with get_db_connection() as conn:
        # On clôture automatiquement les anciens sondages
        await conn.execute("UPDATE polls SET is_active = 0")
        # On insère le nouveau
        await conn.execute(
            "INSERT INTO polls (question, option1, option2, option3, option4, is_active) VALUES (?, ?, ?, ?, ?, 1)", 
            (question, option1, option2, option3, option4)
        )
    return RedirectResponse(url="/admin/polls?created=1", status_code=303)

@router.post("/admin/polls/close")
async def close_poll(request: Request):
    async with get_db_connection() as conn:
        await conn.execute("UPDATE polls SET is_active = 0")
    return RedirectResponse(url="/admin/polls?closed=1", status_code=303)
