import sqlite3
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("masthbot.api")
router = APIRouter(prefix="/api/v1", tags=["api"])
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

# ==========================================================
# 🛑 LISTE D'EXCLUSION GLOBALE (Bots, Streamer, Vestale)
# ==========================================================
EXCLUSION_LIST = "('masthom_', 'felixthebigblackcat', 'vestale7', 'streamelements', 'wizebot', 'nightbot')"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================================
# 1. STATS GLOBALES (Pour stats.js sur Vercel)
# ==========================================================
@router.get("/global_stats")
async def get_global_stats():
    conn = get_db()
    try:
        # Totaux filtrés
        members = conn.execute(f"SELECT COUNT(*) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}").fetchone()[0]
        total_xp = conn.execute(f"SELECT SUM(points) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}").fetchone()[0] or 0
        max_lvl_xp = conn.execute(f"SELECT MAX(points) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}").fetchone()[0] or 0
        
        # Top 5 filtré
        top5_raw = conn.execute(f"SELECT username, points FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST} ORDER BY points DESC LIMIT 5").fetchall()
        top5 = [dict(r) for r in top5_raw]
        
        conn.close()
        return {
            "total_members": members,
            "total_xp": total_xp,
            "max_xp": max_lvl_xp,
            "top5": top5
        }
    except Exception as e:
        if conn: conn.close()
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================================
# 2. LEADERBOARD (Pour leaderboard.js sur Vercel)
# ==========================================================
@router.get("/leaderboard")
async def get_leaderboard():
    conn = get_db()
    try:
        # On récupère TOUS les viewers SANS les exclus
        rows = conn.execute(f"SELECT username, points, watchtime FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST} ORDER BY points DESC").fetchall()
        conn.close()
        
        result = []
        for r in rows:
            d = dict(r)
            xp = d.get('points', 0)
            d['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
            result.append(d)
            
        return result
    except Exception as e:
        if conn: conn.close()
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================================
# 3. PROFIL INDIVIDUEL ET HISTORIQUE (Pour profile.html)
# ==========================================================
@router.get("/viewer/{twitch_id}")
async def get_viewer_profile(twitch_id: str, username: str = None):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,)).fetchone()
        
        # ✅ LA VRAIE SOLUTION : On utilise le pseudo fourni par Twitch lors de la connexion web
        display_name = username if username else f"Visiteur_{twitch_id[:4]}"

        if not row:
            # S'il n'a jamais parlé, on le crée DIRECTEMENT avec son VRAI nom
            conn.execute("INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES (?, ?, 0, 0, 0)", (twitch_id, display_name))
            conn.commit()
        else:
            # S'il s'appelait "Visiteur_" suite à ton test d'hier, on le corrige !
            if row['username'].startswith("Visiteur_") and username:
                conn.execute("UPDATE viewers SET username = ? WHERE twitch_id = ?", (username, twitch_id))
                conn.commit()

        # On recharge la ligne pour avoir les données fraîches
        row = conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,)).fetchone()
        viewer_data = dict(row)

        # ✅ Mise à jour de la présence Web avec l'heure locale (PAS de spam dans le fil d'actu)
        conn.execute("UPDATE viewers SET last_seen = datetime('now', 'localtime'), last_web_login = datetime('now', 'localtime') WHERE twitch_id = ?", (twitch_id,))
        conn.commit()

        xp = viewer_data.get('points', 0)
        viewer_data['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
        
        rank = conn.execute(f"SELECT COUNT(*) FROM viewers WHERE points > ? AND LOWER(username) NOT IN {EXCLUSION_LIST}", (xp,)).fetchone()[0] + 1
        viewer_data['rank'] = rank
        
        history_list = []
        
        settings_row = conn.execute("SELECT exp_per_message, exp_per_watchtime FROM settings WHERE id=1").fetchone()
        exp_msg = settings_row['exp_per_message'] if settings_row and settings_row['exp_per_message'] is not None else 2
        exp_wt = settings_row['exp_per_watchtime'] if settings_row and settings_row['exp_per_watchtime'] is not None else 5
        
        today_stats = conn.execute("SELECT messages, watchtime FROM viewer_daily_stats WHERE twitch_id = ? AND day = date('now', 'localtime')", (twitch_id,)).fetchone()
        
        if today_stats:
            msgs = today_stats['messages'] or 0
            wt = today_stats['watchtime'] or 0
            
            if wt > 0:
                wt_h = wt // 3600
                wt_m = (wt % 3600) // 60
                wt_str = f"{wt_h}h {wt_m}m" if wt_h > 0 else f"{wt_m} min"
                wt_points = (wt // 60) * exp_wt
                
                history_list.append({
                    "event_type": "PRÉSENCE (SESSION EN COURS)",
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "date": "Aujourd'hui",
                    "details": f"Temps passé sur le live : {wt_str}",
                    "amount": wt_points,
                    "icon": "⏱️",
                    "color": "#10b981" 
                })
                
            if msgs > 0:
                msg_points = msgs * exp_msg
                history_list.append({
                    "event_type": "ACTIVITÉ CHAT (SESSION EN COURS)",
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "date": "Aujourd'hui",
                    "details": f"{msgs} messages envoyés",
                    "amount": msg_points,
                    "icon": "💬",
                    "color": "#0ea5e9"
                })

        raw_history = conn.execute("SELECT * FROM viewer_exp_log WHERE twitch_id = ? ORDER BY timestamp DESC LIMIT 15", (twitch_id,)).fetchall()
        for r in raw_history:
            log = dict(r)
            try:
                dt = datetime.fromisoformat(log['timestamp'].replace(' ', 'T'))
                d_str = dt.strftime('%d/%m/%Y')
            except:
                d_str = log['timestamp']
                
            ev = log['event_type'].upper()
            icon, color = "✨", "#00f5c3"
            if "BIT" in ev or "CHEER" in ev: icon, color = "💎", "#ffb300"
            elif "RAID" in ev: icon, color = "⚔️", "#a855f7"
            elif "SUB" in ev: icon, color = "💜", "#9146ff"

            history_list.append({
                "event_type": ev,
                "amount": log['amount'],
                "details": log['details'] or "Action standard",
                "date": d_str,
                "icon": icon,
                "color": color
            })

        viewer_data['history'] = history_list
        return viewer_data
    finally:
        conn.close()

# ==========================================================
# 4. SAUVEGARDE DU FORMULAIRE IA (Pour felix.html)
# ==========================================================
@router.post("/viewer/update_context")
async def update_viewer_context(request: Request):
    try:
        data = await request.json()
        t_id = data.get("twitch_id")
        if not t_id: 
            raise HTTPException(status_code=400, detail="ID Twitch manquant")
        
        conn = get_db()
        conn.execute("""
            UPDATE viewers SET 
                nickname = ?, nickname_for_bot = ?, birthday = ?, sleep_pattern = ?, 
                pronouns = ?, vibe = ?, favorite_game = ?, comfort_game = ?, 
                signature_emote = ?, play_style = ?, useless_talent = ?, 
                favorite_feature = ?, favorite_food = ?, favorite_drink = ?, 
                free_message = ?, roast_level = ?
            WHERE twitch_id = ?
        """, (
            data.get("nickname"), data.get("nickname_for_bot"), data.get("birthday"), data.get("sleep_pattern"),
            data.get("pronouns"), data.get("vibe"), data.get("favorite_game"), data.get("comfort_game"),
            data.get("signature_emote"), data.get("play_style"), data.get("useless_talent"),
            data.get("favorite_feature"), data.get("favorite_food"), data.get("favorite_drink"),
            data.get("free_message"), int(data.get("roast_level") or 5), t_id
        ))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erreur update_context: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================================
# 5. SONDAGES (API pour le Widget Vercel)
# ==========================================================
@router.get("/poll/active")
async def get_active_poll_api(twitch_id: str = None):
    conn = get_db()
    try:
        poll = conn.execute("SELECT * FROM polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
        if not poll:
            conn.close()
            return {"active": False}

        poll_dict = dict(poll)
        votes = conn.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id = ? GROUP BY option_index", (poll_dict['id'],)).fetchall()
        
        results = {"1": 0, "2": 0, "3": 0, "4": 0}
        total_votes = 0
        for v in votes:
            results[str(v['option_index'])] = v['count']
            total_votes += v['count']

        user_vote = None
        if twitch_id:
            uv = conn.execute("SELECT option_index FROM poll_votes WHERE poll_id = ? AND twitch_id = ?", (poll_dict['id'], twitch_id)).fetchone()
            if uv: user_vote = str(uv['option_index'])

        conn.close()
        return {
            "active": True, "id": poll_dict['id'], "question": poll_dict['question'],
            "options": {"1": poll_dict['option1'], "2": poll_dict['option2'], "3": poll_dict['option3'], "4": poll_dict['option4']},
            "results": results, "total_votes": total_votes, "user_vote": user_vote
        }
    except Exception as e:
        if conn: conn.close()
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/poll/vote")
async def submit_vote_api(request: Request):
    try:
        data = await request.json()
        poll_id, t_id, opt_idx = data.get("poll_id"), data.get("twitch_id"), data.get("option_index")
        
        if not all([poll_id, t_id, opt_idx]):
            return JSONResponse(status_code=400, content={"error": "Données manquantes"})
            
        conn = get_db()
        conn.execute("INSERT INTO poll_votes (poll_id, twitch_id, option_index) VALUES (?, ?, ?) ON CONFLICT(poll_id, twitch_id) DO UPDATE SET option_index = excluded.option_index", (poll_id, t_id, opt_idx))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================================
# 6. FAQ & QUESTIONS (API pour le site web)
# ==========================================================
@router.post("/questions/ask")
async def ask_question_api(request: Request):
    data = await request.json()
    t_id, username, text = data.get("twitch_id"), data.get("username"), data.get("question")
    if not text or len(text) < 5: return JSONResponse(status_code=400, content={"error": "Texte trop court"})
    conn = get_db()
    try:
        conn.execute("INSERT INTO questions (twitch_id, username, question_text) VALUES (?, ?, ?)", (t_id, username, text))
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()

@router.get("/questions/faq")
async def get_faq_api():
    conn = get_db()
    try:
        # ✅ FIX : On ne renvoie pas le pseudo original, tout le monde est 'Anonyme' en public
        rows = conn.execute("SELECT question_text, answer_text, answered_at FROM questions WHERE is_public = 1 AND answer_text IS NOT NULL ORDER BY answered_at DESC").fetchall()
        return [{"username": "Anonyme", "question_text": r["question_text"], "answer_text": r["answer_text"], "answered_at": r["answered_at"]} for r in rows]
    finally:
        conn.close()
