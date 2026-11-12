import json
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import JSONResponse

# --- IMPORT CORE POSTGRESQL ---
from app.core.database import get_db_connection
from app.core.viewer_auth import ViewerIdentity, require_viewer, ensure_self, set_viewer_cookie

router = APIRouter(tags=["public"])

EXCLUSION_LIST = "('masthou', 'felixthebigblackcat', 'vestale7', 'streamelements', 'wizebot', 'nightbot')"

# ==========================================
# ROUTES API POUR LE SITE fel-x.icu
# (le mini-site public que servait aussi le bot — /, /classement, /profile, /felix,
#  /infos, /login — a été retiré le 12/11/2026 : fel-x.icu est le seul site viewer)
# ==========================================
@router.get("/viewer/{twitch_id}")
async def get_viewer_profile_api(twitch_id: str, username: str = None, identity: ViewerIdentity = Depends(require_viewer)):
    ensure_self(identity, twitch_id)
    username = identity.login or username
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

@router.get("/rewards/secret")
async def get_secret_rewards():
    """API publique pour charger la liste des trophées masqués de la table trophy_list"""
    async with get_db_connection() as conn:
        try:
            cursor = await conn.execute("SELECT * FROM trophy_list WHERE is_secret = 1")
            return [dict(t) for t in await cursor.fetchall()]
        except Exception as e:
            print(f"Erreur chargement trophées secrets: {e}")
            return []

@router.post("/viewer/update_context")
async def update_viewer_context_public(request: Request):
    from app.routes.api import update_viewer_context
    return await update_viewer_context(request)

@router.get("/api/public/commands")
async def api_public_commands():
    """API publique (sans auth) listant les commandes actives, pour un affichage viewer.
    Ne renvoie que les champs utiles publiquement — pas created_by/use_count/réponse brute.
    Champs alignés sur le contrat attendu par commands.js : trigger/category/description/access."""
    from app.services.command_service import list_commands
    commands = await list_commands(active_only=True)

    result = []
    for c in commands:
        if c.get("hide_from_list"):
            continue
        try:
            resp = json.loads(c.get("response") or "{}")
        except (TypeError, ValueError):
            resp = {}
        aliases = [a for a in (c.get("aliases") or "").split(",") if a]
        trigger = " ".join(f"!{n}" for n in [c["name"], *aliases])
        result.append({
            "trigger": trigger,
            "category": c.get("category") or "Général",
            "access": c.get("min_role") or "viewer",
            "description": c.get("description") or resp.get("text") or "",
        })
    return result

# ==========================================
# SON PERSO VIP (soumission par le viewer, validation côté admin)
# ==========================================
@router.post("/api/auth/session")
async def create_viewer_session(request: Request):
    from fastapi.responses import JSONResponse
    identity = await require_viewer(request)
    data = await request.json()
    ensure_self(identity, data.get("twitch_id") or None)
    twitch_id    = identity.user_id
    display_name = data.get("display_name", "").strip()
    avatar_url   = data.get("avatar_url", "").strip()

    if not twitch_id:
        return JSONResponse({"error": "twitch_id manquant"}, status_code=400)

    response = JSONResponse({"status": "ok"})
    set_viewer_cookie(response, twitch_id)
    response.set_cookie("viewer_name",   display_name, max_age=2592000, httponly=False, samesite="none", secure=True)
    response.set_cookie("viewer_avatar", avatar_url,   max_age=2592000, httponly=False, samesite="none", secure=True)
    return response

@router.get("/api/vip-sound/status")
async def api_vip_sound_status(request: Request, twitch_id: str = None, identity: ViewerIdentity = Depends(require_viewer)):
    # Chrome bloque les cookies tiers (fel-x.icu et l'API du bot sont deux domaines
    # différents) : le cookie viewer_id ne peut pas être livré de manière fiable en
    # cross-origin. On accepte donc le twitch_id explicitement (déjà connu du frontend,
    # même principe que /viewer/{twitch_id}), avec le cookie en repli pour l'usage same-origin.
    from app.services.vip_sound_service import get_viewer_vip_status
    ensure_self(identity, twitch_id)
    viewer_id = identity.user_id
    return await get_viewer_vip_status(viewer_id)

@router.post("/api/vip-sound/submit")
async def api_vip_sound_submit(request: Request, file: UploadFile = File(...), twitch_id: str = Form(None),
                               identity: ViewerIdentity = Depends(require_viewer)):
    from app.services.vip_sound_service import submit_vip_sound
    ensure_self(identity, twitch_id)
    viewer_id = identity.user_id

    async with get_db_connection() as conn:
        c = await conn.execute("SELECT username FROM viewers WHERE twitch_id = $1", (viewer_id,))
        row = await c.fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "Viewer introuvable."})

    content = await file.read()
    result = await submit_vip_sound(viewer_id, row["username"], file.filename, content)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result
