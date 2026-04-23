import sqlite3
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["polls"])
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/admin/polls", response_class=HTMLResponse)
async def admin_polls(request: Request):
    conn = get_db()
    
    # Récupérer le sondage actif
    active_poll = conn.execute("SELECT * FROM polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
    poll_data = None
    
    if active_poll:
        poll_data = dict(active_poll)
        
        # Calculer les résultats avec les pseudos des votants (Jointure SQL)
        votes_data = conn.execute("""
            SELECT pv.option_index, v.username 
            FROM poll_votes pv
            LEFT JOIN viewers v ON pv.twitch_id = v.twitch_id
            WHERE pv.poll_id = ?
        """, (poll_data['id'],)).fetchall()
        
        results = {1: 0, 2: 0, 3: 0, 4: 0}
        voters = {1: [], 2: [], 3: [], 4: []}
        total_votes = 0
        
        for v in votes_data:
            opt_idx = v['option_index']
            uname = v['username'] or "Inconnu"
            if opt_idx in results:
                results[opt_idx] += 1
                voters[opt_idx].append(uname)
                total_votes += 1
            
        poll_data['results'] = results
        poll_data['voters'] = voters
        poll_data['total_votes'] = total_votes

    # Historique des anciens sondages
    recent_polls = conn.execute("SELECT * FROM polls WHERE is_active = 0 ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    
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
    conn = get_db()
    # On clôture automatiquement les anciens sondages
    conn.execute("UPDATE polls SET is_active = 0")
    # On insère le nouveau
    conn.execute(
        "INSERT INTO polls (question, option1, option2, option3, option4, is_active) VALUES (?, ?, ?, ?, ?, 1)", 
        (question, option1, option2, option3, option4)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/polls?created=1", status_code=303)

@router.post("/admin/polls/close")
async def close_poll(request: Request):
    conn = get_db()
    conn.execute("UPDATE polls SET is_active = 0")
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/polls?closed=1", status_code=303)
