import logging
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.api")
router = APIRouter(prefix="/api/v1", tags=["api"])

# ==========================================================
# 🛑 LISTE D'EXCLUSION GLOBALE
# ==========================================================
EXCLUSION_LIST = "('masthom_', 'felixthebigblackcat', 'vestale7', 'streamelements', 'wizebot', 'nightbot')"

# ==========================================================
# 1. STATS GLOBALES
# ==========================================================
@router.get("/global_stats")
async def get_global_stats():
    async with get_db_connection() as conn:
        try:
            c1 = await conn.execute(f"SELECT COUNT(*) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            r1 = await c1.fetchone()
            members = r1[0] if r1 else 0

            c2 = await conn.execute(f"SELECT SUM(points) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            r2 = await c2.fetchone()
            total_xp = r2[0] if r2 and r2[0] else 0

            c3 = await conn.execute(f"SELECT MAX(points) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            r3 = await c3.fetchone()
            max_lvl_xp = r3[0] if r3 and r3[0] else 0
            
            c4 = await conn.execute(f"SELECT username, points FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST} ORDER BY points DESC LIMIT 5")
            top5_raw = await c4.fetchall()
            top5 = [dict(r) for r in top5_raw]

            c5 = await conn.execute(f"""
                SELECT username, first_count, deuz_count, troiz_count 
                FROM viewers 
                WHERE LOWER(username) NOT IN {EXCLUSION_LIST} 
                AND (first_count > 0 OR deuz_count > 0 OR troiz_count > 0)
                ORDER BY first_count DESC, deuz_count DESC, troiz_count DESC 
                LIMIT 15
            """)
            podium_raw = await c5.fetchall()
            podium_top = [dict(r) for r in podium_raw]
            
            return {
                "total_members": members, 
                "total_xp": total_xp, 
                "max_xp": max_lvl_xp, 
                "top5": top5,
                "podium_top": podium_top
            }
        except Exception as e:
            logger.error(f"❌ Erreur global_stats : {e}")
            return {"error": str(e)}

# ==========================================================
# 2. LEADERBOARD
# ==========================================================
@router.get("/leaderboard")
async def get_leaderboard():
    async with get_db_connection() as conn:
        c = await conn.execute(f"SELECT username, points, watchtime FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST} ORDER BY points DESC")
        rows = await c.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            xp = d.get('points', 0)
            d['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
            result.append(d)
        return result

# ==========================================================
# 3. PROFIL INDIVIDUEL
# ==========================================================
@router.get("/viewer/{twitch_id}")
async def get_viewer_profile(twitch_id: str, username: str = None):
    async with get_db_connection() as conn:
        c = await conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,))
        row = await c.fetchone()
        display_name = username if username else f"Visiteur_{twitch_id[:4]}"

        if not row:
            await conn.execute("INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES (?, ?, 0, 0, 0)", (twitch_id, display_name))
            c = await conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,))
            row = await c.fetchone()
        else:
            if row['username'].startswith("Visiteur_") and username:
                await conn.execute("UPDATE viewers SET username = ? WHERE twitch_id = ?", (username, twitch_id))
                c = await conn.execute("SELECT * FROM viewers WHERE twitch_id = ?", (twitch_id,))
                row = await c.fetchone()
        
        viewer_data = dict(row)
        await conn.execute("UPDATE viewers SET last_seen = NOW(), last_web_login = NOW() WHERE twitch_id = ?", (twitch_id,))

        xp = viewer_data.get('points', 0)
        viewer_data['level'] = max(1, int((xp / 100) ** (1 / 2.2))) if xp > 0 else 1
        
        crank = await conn.execute(f"SELECT COUNT(*) FROM viewers WHERE points > ? AND LOWER(username) NOT IN {EXCLUSION_LIST}", (xp,))
        rank_val = await crank.fetchone()
        viewer_data['rank'] = (rank_val[0] if rank_val else 0) + 1
        
        ctrophies = await conn.execute("""
            SELECT t.label, t.icon, t.description, t.tier, vt.earned_at
            FROM viewer_trophies vt
            JOIN trophy_list t ON vt.trophy_id = t.id
            WHERE vt.twitch_id = ?
            ORDER BY vt.earned_at DESC
        """, (twitch_id,))
        trophies_raw = await ctrophies.fetchall()

        trophies_list = []
        tier_counts = {"Standard": 0, "Bronze": 0, "Argent": 0, "Or": 0, "Platine": 0, "Diamant": 0}

        for tr in trophies_raw:
            t_dict = dict(tr)
            if isinstance(t_dict.get('earned_at'), datetime):
                t_dict['earned_at'] = t_dict['earned_at'].isoformat()
            trophies_list.append(t_dict)
            tier_name = t_dict.get('tier', 'Standard')
            tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

        viewer_data['trophies'] = trophies_list
        viewer_data['tier_counts'] = tier_counts

        history_list = []
        cset = await conn.execute("SELECT exp_per_message, exp_per_watchtime FROM settings WHERE id=1")
        settings_row = await cset.fetchone()
        exp_msg = settings_row['exp_per_message'] if settings_row else 2
        exp_wt = settings_row['exp_per_watchtime'] if settings_row else 5
        
        ctoday = await conn.execute("SELECT messages, watchtime FROM viewer_daily_stats WHERE twitch_id = ? AND day = CURRENT_DATE", (twitch_id,))
        today_stats = await ctoday.fetchone()
        
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

        chist = await conn.execute("SELECT * FROM viewer_exp_log WHERE twitch_id = ? ORDER BY timestamp DESC LIMIT 15", (twitch_id,))
        raw_history = await chist.fetchall()
        for r in raw_history:
            log = dict(r)
            ev = log['event_type'].upper()
            icon, color = "✨", "#00f5c3"
            if any(x in ev for x in ["BIT", "CHEER"]): icon, color = "💎", "#ffb300"
            elif "RAID" in ev: icon, color = "⚔️", "#a855f7"
            elif "SUB" in ev: icon, color = "💜", "#9146ff"

            ts = log['timestamp']
            if isinstance(ts, datetime):
                ts = ts.strftime('%Y-%m-%d %H:%M:%S')
            elif not isinstance(ts, str):
                ts = str(ts)

            history_list.append({
                "event_type": ev, "amount": log['amount'], "details": log['details'] or "Action standard",
                "date": ts[:10].replace("-", "/"), "icon": icon, "color": color
            })

        viewer_data['history'] = history_list
        for k, v in viewer_data.items():
            if isinstance(v, datetime):
                viewer_data[k] = v.isoformat()
        return viewer_data

# ==========================================================
# 4. SAUVEGARDE FORMULAIRE IA
# ==========================================================
@router.post("/viewer/update_context")
async def update_viewer_context(request: Request):
    try:
        data = await request.json()
        t_id = data.get("twitch_id")
        if not t_id: 
            raise HTTPException(status_code=400, detail="ID Twitch manquant")
        
        async with get_db_connection() as conn:
            await conn.execute("""
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
                data.get("free_message"), int(data.get("roast_level") or 5), str(t_id)
            ))
            
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"❌ [API ERROR] Impossible de sauvegarder le contexte: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================================
# 5. SONDAGES
# ==========================================================
@router.get("/poll/active")
async def get_active_poll_api(twitch_id: str = None):
    async with get_db_connection() as conn:
        cpoll = await conn.execute("SELECT * FROM polls WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        poll = await cpoll.fetchone()
        if not poll: return {"active": False}

        poll_dict = dict(poll)
        cvotes = await conn.execute("SELECT option_index, COUNT(*) as count FROM poll_votes WHERE poll_id = ? GROUP BY option_index", (poll_dict['id'],))
        votes = await cvotes.fetchall()
        
        results = {"1": 0, "2": 0, "3": 0, "4": 0}
        total_votes = 0
        for v in votes:
            results[str(v['option_index'])] = v['count']
            total_votes += v['count']

        user_vote = None
        if twitch_id:
            cuv = await conn.execute("SELECT option_index FROM poll_votes WHERE poll_id = ? AND twitch_id = ?", (poll_dict['id'], str(twitch_id)))
            uv = await cuv.fetchone()
            if uv: user_vote = str(uv['option_index'])

        return {
            "active": True, "id": poll_dict['id'], "question": poll_dict['question'],
            "options": {"1": poll_dict['option1'], "2": poll_dict['option2'], "3": poll_dict['option3'], "4": poll_dict['option4']},
            "results": results, "total_votes": total_votes, "user_vote": user_vote
        }

@router.post("/poll/vote")
async def submit_vote_api(request: Request):
    data = await request.json()
    p_id, t_id, opt = data.get("poll_id"), data.get("twitch_id"), data.get("option_index")
    if not all([p_id, t_id, opt]): return JSONResponse(status_code=400, content={"error": "Données manquantes"})
    async with get_db_connection() as conn:
        try:
            await conn.execute("INSERT INTO poll_votes (poll_id, twitch_id, option_index) VALUES (?, ?, ?) ON CONFLICT(poll_id, twitch_id) DO UPDATE SET option_index = excluded.option_index", (p_id, str(t_id), opt))
            return {"status": "success"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

# ==========================================================
# 6. FAQ
# ==========================================================
@router.post("/questions/ask")
async def ask_question_api(request: Request):
    data = await request.json()
    t_id, username, text = data.get("twitch_id"), data.get("username"), data.get("question")
    if not text or len(text) < 5: return JSONResponse(status_code=400, content={"error": "Texte trop court"})
    async with get_db_connection() as conn:
        await conn.execute("INSERT INTO questions (twitch_id, username, question_text) VALUES (?, ?, ?)", (str(t_id), username, text))
        return {"status": "success"}

@router.get("/questions/faq")
async def get_faq_api():
    async with get_db_connection() as conn:
        c = await conn.execute("SELECT question_text, answer_text, answered_at FROM questions WHERE is_public = 1 AND answer_text IS NOT NULL ORDER BY answered_at DESC")
        rows = await c.fetchall()
        res = []
        for r in rows:
            ans = r["answered_at"]
            if isinstance(ans, datetime):
                ans = ans.isoformat()
            res.append({"username": "Anonyme", "question_text": r["question_text"], "answer_text": r["answer_text"], "answered_at": ans})
        return res

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

        async with get_db_connection() as conn:
            await conn.execute(
                "INSERT INTO viewers (twitch_id, username, points, messages, watchtime) VALUES (?, ?, 0, 0, 0) "
                "ON CONFLICT(twitch_id) DO UPDATE SET username = excluded.username", 
                (str(t_id), username)
            )
            col_name = f"{reward_type}_count"
            if count_val is not None and str(count_val).strip().isdigit():
                exact_count = int(str(count_val).strip())
                await conn.execute(f"UPDATE viewers SET {col_name} = ? WHERE twitch_id = ?", (exact_count, str(t_id)))
            else:
                await conn.execute(f"UPDATE viewers SET {col_name} = COALESCE(viewers.{col_name}, 0) + 1 WHERE twitch_id = ?", (str(t_id),))
            
            return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ Erreur Podium Reward : {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
