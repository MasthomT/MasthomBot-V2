import sqlite3
import logging
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("masthbot.api")
router = APIRouter(prefix="/api/v1", tags=["api"])
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

# ==========================================================
# 🛑 LISTE D'EXCLUSION GLOBALE
# ==========================================================
EXCLUSION_LIST = "('masthom_', 'felixthebigblackcat', 'vestale7', 'streamelements', 'wizebot', 'nightbot')"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================================
# 1. STATS GLOBALES
# ==========================================================
@router.get("/global_stats")
async def get_global_stats():
    conn = get_db()
    try:
        members = conn.execute(f"SELECT COUNT(*) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}").fetchone()[0]
        total_xp = conn.execute(f"SELECT SUM(points) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}").fetchone()[0] or 0
        max_lvl_xp = conn.execute(f"SELECT MAX(points) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}").fetchone()[0] or 0
        
        top5_raw = conn.execute(f"SELECT username, points FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST} ORDER BY points DESC LIMIT 5").fetchall()
        top5 = [dict(r) for r in top5_raw]

        podium_raw = conn.execute(f"""
            SELECT username, first_count, deuz_count, troiz_count 
            FROM viewers 
            WHERE LOWER(username) NOT IN {EXCLUSION_LIST} 
            AND (first_count > 0 OR deuz_count > 0 OR troiz_count > 0)
            ORDER BY first_count DESC, deuz_count DESC, troiz_count DESC 
            LIMIT 15
        """).fetchall()
        podium_top = [dict(r) for r in podium_raw]
        
        return {
            "total_members": members, 
            "total_xp": total_xp, 
            "max_xp": max_lvl_xp, 
            "top5": top5,
            "podium_top": podium_top
        }
    finally:
        conn.close()

# ==========================================================
# 2. LEADERBOARD
# ==========================================================
@router.get("/leaderboard")
async def get_leaderboard():
    conn = get_db()
    try:
        rows = conn.execute(f"SELECT username, points, watchtime FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST} ORDER BY points DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            xp = d.get('points', 0)
            d['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
            result.append(d)
        return result
    finally:
        conn.close()

# ==========================================================
# 3. PROFIL INDIVIDUEL (NETTOYÉ DU SPAM)
# ==========================================================
@router.get("/viewer/{twitch_id}")
async def get_viewer_profile(twitch_id: str, username: str = None):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,)).fetchone()
        display_name = username if username else f"Visiteur_{twitch_id[:4]}"

        if not row:
            conn.execute("INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES (?, ?, 0, 0, 0)", (twitch_id, display_name))
            conn.commit()
            row = conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,)).fetchone()
        else:
            if row['username'].startswith("Visiteur_") and username:
                conn.execute("UPDATE viewers SET username = ? WHERE twitch_id = ?", (username, twitch_id))
                conn.commit()
                row = conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,)).fetchone()
        
        viewer_data = dict(row)

        # ✅ FIX: On met à jour l'heure de connexion, mais SANS SPAMMER LE FIL D'ACTUALITÉ
        conn.execute("UPDATE viewers SET last_seen = datetime('now', 'localtime'), last_web_login = datetime('now', 'localtime') WHERE twitch_id = ?", (twitch_id,))
        conn.commit()

        xp = viewer_data.get('points', 0)
        viewer_data['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
        rank = conn.execute(f"SELECT COUNT(*) FROM viewers WHERE points > ? AND LOWER(username) NOT IN {EXCLUSION_LIST}", (xp,)).fetchone()[0] + 1
        viewer_data['rank'] = rank
        
        history_list = []
        settings_row = conn.execute("SELECT exp_per_message, exp_per_watchtime FROM settings WHERE id=1").fetchone()
        exp_msg = settings_row['exp_per_message'] if settings_row else 2
        exp_wt = settings_row['exp_per_watchtime'] if settings_row else 5
        
        today_stats = conn.execute("SELECT messages, watchtime FROM viewer_daily_stats WHERE twitch_id = ? AND day = date('now', 'localtime')", (twitch_id,)).fetchone()
        
        if today_stats:
            if today_stats['watchtime'] > 0:
                wt = today_stats['watchtime']
                wt_str = f"{wt // 3600}h {(wt % 3600) // 60}m" if wt >= 3600 else f"{wt // 60} min"
                history_list.append({
                    "event_type": "PRÉSENCE (LIVE)", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "date": "Aujourd'hui", "details": f"Session : {wt_str}", "amount": (wt // 60) * exp_wt,
                    "icon": "⏱️", "color": "#10b981" 
                })
            if today_stats['messages'] > 0:
                history_list.append({
                    "event_type": "ACTIVITÉ CHAT", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "date": "Aujourd'hui", "details": f"{today_stats['messages']} messages envoyés", "amount": today_stats['messages'] * exp_msg,
                    "icon": "💬", "color": "#0ea5e9"
                })

        raw_history = conn.execute("SELECT * FROM viewer_exp_log WHERE twitch_id = ? ORDER BY timestamp DESC LIMIT 15", (twitch_id,)).fetchall()
        for r in raw_history:
            log = dict(r)
            ev = log['event_type'].upper()
            icon, color = "✨", "#00f5c3"
            if any(x in ev for x in ["BIT", "CHEER"]): icon, color = "💎", "#ffb300"
            elif "RAID" in ev: icon, color = "⚔️", "#a855f7"
            elif "SUB" in ev: icon, color = "💜", "#9146ff"

            history_list.append({
                "event_type": ev, "amount": log['amount'], "details": log['details'] or "Action standard",
                "date": log['timestamp'][:10].replace("-", "/"), "icon": icon, "color": color
            })

        viewer_data['history'] = history_list
        return viewer_data
    finally:
        conn.close()

# ==========================================================
# 4. SAUVEGARDE FORMULAIRE IA
# ==========================================================
@router.post("/viewer/update_context")
async def update_viewer_context(request: Request):
    try:
        data = await request.json()
        t_id = data.get("twitch_id")
        if not t_id: raise HTTPException(status_code=400, detail="ID Twitch manquant")
        
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
        return {"status": "success"}
    finally:
        conn.close()

# ==========================================================
# 5. SONDAGES
# ==========================================================
@router.get("/poll/active")
async def get_active_poll_api(twitch_id: str = None):
    conn = get_db()
    try:
        poll = conn.execute("SELECT * FROM polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
        if not poll: return {"active": False}

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

        return {
            "active": True, "id": poll_dict['id'], "question": poll_dict['question'],
            "options": {"1": poll_dict['option1'], "2": poll_dict['option2'], "3": poll_dict['option3'], "4": poll_dict['option4']},
            "results": results, "total_votes": total_votes, "user_vote": user_vote
        }
    finally:
        conn.close()

@router.post("/poll/vote")
async def submit_vote_api(request: Request):
    data = await request.json()
    p_id, t_id, opt = data.get("poll_id"), data.get("twitch_id"), data.get("option_index")
    if not all([p_id, t_id, opt]): return JSONResponse(status_code=400, content={"error": "Données manquantes"})
    conn = get_db()
    try:
        conn.execute("INSERT INTO poll_votes (poll_id, twitch_id, option_index) VALUES (?, ?, ?) ON CONFLICT(poll_id, twitch_id) DO UPDATE SET option_index = excluded.option_index", (p_id, t_id, opt))
        conn.commit()
        return {"status": "success"}
    finally:
        conn.close()

# ==========================================================
# 6. FAQ
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
        rows = conn.execute("SELECT question_text, answer_text, answered_at FROM questions WHERE is_public = 1 AND answer_text IS NOT NULL ORDER BY answered_at DESC").fetchall()
        return [{"username": "Anonyme", "question_text": r["question_text"], "answer_text": r["answer_text"], "answered_at": r["answered_at"]} for r in rows]
    finally:
        conn.close()

# ==========================================================
# 7. STREAMERBOT (Récompenses First/Deuz/Troiz)
# ==========================================================
@router.post("/rewards/podium")
async def claim_podium_reward(request: Request):
    try:
        data = await request.json()
        t_id = data.get("twitch_id")
        username = data.get("username")
        reward_type = str(data.get("reward_type", "")).lower() 
        count_val = data.get("count")

        if not t_id or reward_type not in ["first", "deuz", "troiz"]:
            return JSONResponse(status_code=400, content={"error": "Données invalides ou type de récompense non géré."})

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES (?, ?, 0, 0, 0) "
                "ON CONFLICT(twitch_id) DO UPDATE SET username = excluded.username", 
                (t_id, username)
            )
            col_name = f"{reward_type}_count"
            if count_val is not None and str(count_val).strip().isdigit():
                exact_count = int(str(count_val).strip())
                conn.execute(f"UPDATE viewers SET {col_name} = ? WHERE twitch_id = ?", (exact_count, t_id))
            else:
                conn.execute(f"UPDATE viewers SET {col_name} = {col_name} + 1 WHERE twitch_id = ?", (t_id,))
            conn.commit()
            return {"status": "success"}
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"❌ Erreur Podium Reward : {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
