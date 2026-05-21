import logging
import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# --- IMPORT CORE POSTGRESQL ---
from app.core.database import get_db_connection

# --- CONFIGURATION DU LOGGING ---
logger = logging.getLogger("masthbot.stats")

# --- INITIALISATION DU ROUTER ---
router = APIRouter(prefix="/admin", tags=["admin"])

# --- CONFIGURATION DES TEMPLATES ---
templates = Jinja2Templates(directory="app/templates")

# =================================================================
# 🛑 LISTE D'EXCLUSION GLOBALE (Bots, Streamer, Vestale)
# =================================================================
EXCLUSION_LIST = "('masthom_', 'felixthebigblackcat', 'vestale7', 'streamelements', 'wizebot', 'nightbot')"

# =================================================================
# 🛠️ FONCTIONS DE FORMATAGE ET CALCULS (XP / NIVEAUX)
# =================================================================

def format_to_hhmm(seconds: int) -> str:
    """
    Transforme des secondes brutes en format HH:MM (ex: 3661 -> 01:01).
    Essentiel pour l'affichage propre dans les tableaux.
    """
    if not seconds or seconds < 0:
        return "00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    return f"{hours:02d}:{minutes:02d}"

def format_date(ts):
    """
    Convertit n'importe quel format de date (Unix, ISO, SQL) en DD/MM/YYYY HH:MM.
    Fonction ultra-robuste pour éviter les crashs d'affichage sur les vieux logs.
    """
    if not ts: return "Date inconnue"
    try:
        ts_str = str(ts).strip()

        # Cas 1 : Timestamp Unix (ex: 1776567601 ou 1774910097.54)
        if ts_str.replace('.', '', 1).isdigit():
            return datetime.fromtimestamp(float(ts_str)).strftime('%d/%m/%Y %H:%M')

        # Cas 2 : Format ISO (ex: 2026-03-31T22:45:16...)
        if "T" in ts_str:
            return datetime.fromisoformat(ts_str.split(".")[0]).strftime('%d/%m/%Y %H:%M')

        # Cas 3 : Format SQL standard (ex: 2026-04-01 06:15:32)
        if "-" in ts_str:
            return ts_str[:16].replace("-", "/")
            
    except Exception as e:
        logger.warning(f"Erreur format date pour '{ts}': {e}")
    
    return str(ts)

def calculate_level_info(xp: int) -> dict:
    """
    Formule Mathématique Officielle FEL-X (Courbe exponentielle puissance 2.2).
    Calcule le niveau actuel, l'XP du niveau en cours, l'XP cible et le % de complétion.
    """
    if xp <= 0:
        return {"level": 1, "current_xp": 0, "current_lvl_xp": 0, "next_xp": 100, "progress": 0}
    
    # Inversion de la formule : XP = 100 * (Level ^ 2.2) => Level = (XP/100) ^ (1/2.2)
    level = int((xp / 100) ** (1 / 2.2))
    level = max(1, level) # Niveau minimum strict = 1
    
    # Calcul des paliers d'XP pour ce niveau et le suivant
    current_lvl_xp = int(100 * (level ** 2.2))
    next_lvl_xp = int(100 * ((level + 1) ** 2.2))
    
    # Calcul du pourcentage de progression pour la jauge HTML
    progress = 0
    if next_lvl_xp > current_lvl_xp:
        progress = ((xp - current_lvl_xp) / (next_lvl_xp - current_lvl_xp)) * 100
        
    return {
        "level": level,
        "current_xp": xp,
        "current_lvl_xp": current_lvl_xp,
        "next_xp": next_lvl_xp,
        "progress": round(min(100, max(0, progress)), 1)
    }

# =================================================================
# 📊 ROUTE : PAGE DES STATISTIQUES GLOBALES
# =================================================================

@router.get("/stats", response_class=HTMLResponse)
@router.get("/stats.html", response_class=HTMLResponse)
async def admin_stats_page(request: Request):
    """
    Affiche le tableau de bord principal des statistiques admin.
    Incorpore les stats globales, les classements, et le fil d'actualité robuste.
    """
    try:
        async with get_db_connection() as conn:
            # 1. RÉCUPÉRATION DES STATISTIQUES GÉNÉRALES (SANS L'EXCLUSION LIST)
            cursor = await conn.execute(f"SELECT COUNT(*) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            res_v = await cursor.fetchone()
            total_viewers = res_v[0] if res_v else 0

            cursor = await conn.execute(f"SELECT SUM(messages) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            res_m = await cursor.fetchone()
            total_messages = (res_m[0] or 0) if res_m else 0

            cursor = await conn.execute(f"SELECT SUM(watchtime) FROM viewers WHERE LOWER(username) NOT IN {EXCLUSION_LIST}")
            res_w = await cursor.fetchone()
            total_seconds = (res_w[0] or 0) if res_w else 0

            # =========================================================
            # 2. CLASSEMENTS (TOP 15)
            # =========================================================
            
            # --- Top Messages ---
            cursor = await conn.execute(f"""
                SELECT username, messages FROM viewers 
                WHERE messages > 0 AND LOWER(username) NOT IN {EXCLUSION_LIST}
                ORDER BY messages DESC LIMIT 15
            """)
            top_messages = await cursor.fetchall()

            # --- Top Watchtime ---
            cursor = await conn.execute(f"""
                SELECT username, watchtime FROM viewers 
                WHERE watchtime > 0 AND LOWER(username) NOT IN {EXCLUSION_LIST}
                ORDER BY watchtime DESC LIMIT 15
            """)
            raw_watchtime = await cursor.fetchall()
            
            top_watchtime = []
            for r in raw_watchtime:
                item = dict(r)
                item['watchtime_readable'] = format_to_hhmm(item.get('watchtime', 0))
                top_watchtime.append(item)

            # --- Top Points (+ Intégration du Niveau mathématique IA) ---
            cursor = await conn.execute(f"""
                SELECT username, points FROM viewers 
                WHERE points > 0 AND LOWER(username) NOT IN {EXCLUSION_LIST}
                ORDER BY points DESC LIMIT 15
            """)
            raw_points = await cursor.fetchall()
            
            top_points = []
            for r in raw_points:
                item = dict(r)
                item['level'] = calculate_level_info(item.get('points', 0))['level']
                top_points.append(item)

            # 3. FIL D'ACTUALITÉ (LOGIQUE ULTRA-ROBUSTE POUR LES NOMS MANQUANTS)
            cursor = await conn.execute("""
                SELECT id, event_type, username, details, timestamp 
                FROM stream_events ORDER BY id DESC LIMIT 100
            """)
            raw_events = await cursor.fetchall()

            recent_events = []
            for row in raw_events:
                d = dict(row)
                v = list(row)
                etype = str(d.get("event_type") or v[1] or "info").lower()

                # Chasse au pseudo : on cherche d'abord dans la colonne 'username', puis 'user', puis à l'index physique 2
                pseudo = d.get("username") or d.get("user")
                if not pseudo or str(pseudo).lower() in ["none", "null", ""]:
                    if len(v) >= 3 and v[2]:
                        pseudo = v[2]

                # Dernier recours : Fallbacks logiques selon le type d'événement
                if not pseudo or str(pseudo).lower() in ["none", "null", ""]:
                    if etype == "backup": pseudo = "SYSTÈME"
                    elif etype in ["brb", "raid_sent"]: pseudo = "Masthom"
                    else: pseudo = "Inconnu"

                recent_events.append({
                    "id": d.get("id") or v[0],
                    "event_type": etype,
                    "username": str(pseudo).replace("masthom_", "Masthom"),
                    "details": d.get("details") or v[3],
                    "timestamp": format_date(d.get("timestamp") or v[4])
                })

            # 4. RÉCUPÉRATION DES DERNIERS UNFOLLOWS
            cursor = await conn.execute("""
                SELECT id, username, timestamp FROM unfollows 
                ORDER BY id DESC LIMIT 20
            """)
            raw_unfollows = await cursor.fetchall()
            
            recent_unfollows = []
            for row in raw_unfollows:
                recent_unfollows.append({
                    "username": row["username"] or "Anonyme",
                    "timestamp": format_date(row["timestamp"])
                })

            # 5. DERNIERS CONNECTÉS (UNIQUEMENT SUR LE WEB FEL-X)
            cursor = await conn.execute(f"""
                SELECT username, last_web_login FROM viewers 
                WHERE LOWER(username) NOT IN {EXCLUSION_LIST}
                AND last_web_login >= NOW() - INTERVAL '10 days'
                ORDER BY last_web_login DESC LIMIT 40
            """)
            raw_last_seen = await cursor.fetchall()
            
            recent_logins = []
            for row in raw_last_seen:
                recent_logins.append({
                    "username": row["username"],
                    "timestamp": format_date(row["last_web_login"])
                })

        # 6. ENVOI AU TEMPLATE HTML
        return templates.TemplateResponse(
            request,
            "admin/stats.html",
            {
                "general_stats": {
                    "total_viewers": total_viewers,
                    "total_messages": total_messages,
                    "watchtime_display": format_to_hhmm(total_seconds)
                },
                "top_messages": [dict(r) for r in top_messages],
                "top_watchtime": top_watchtime,
                "top_points": top_points,
                "recent_events": recent_events,
                "recent_unfollows": recent_unfollows,
                "recent_logins": recent_logins
            }
        )

    except Exception as e:
        logger.error(f"❌ [STATS] Erreur Critique : {e}")
        return HTMLResponse(content=f"<h1>Erreur Interne : Statistiques</h1><p>{e}</p>", status_code=500)

# =================================================================
# 👤 ROUTE : FICHE PROFIL / HISTORIQUE DU VIEWER
# =================================================================

@router.get("/viewer/{twitch_id}/history", response_class=HTMLResponse)
async def viewer_profile_page(request: Request, twitch_id: str):
    """
    Affiche la fiche profil complète d'un viewer précis.
    Incorpore les stats globales, le niveau, l'historique journalier et le contexte IA.
    """
    try:
        async with get_db_connection() as conn:
            # 1. RÉCUPÉRATION DU PROFIL GLOBAL
            cursor = await conn.execute("SELECT * FROM viewers WHERE twitch_id = $1", (twitch_id,))
            v_info = await cursor.fetchone()
            
            if not v_info:
                logger.warning(f"⚠️ Tentative d'accès à un profil inexistant : ID {twitch_id}")
                raise HTTPException(status_code=404, detail="Viewer introuvable dans la base de données.")
            
            viewer = dict(v_info)
            viewer['watchtime_readable'] = format_to_hhmm(viewer.get('watchtime', 0))
            viewer['last_seen_readable'] = format_date(viewer.get('last_seen'))
            
            # --- CALCUL DU NIVEAU IA ET DE LA PROGRESSION ---
            viewer['level_info'] = calculate_level_info(viewer.get('points', 0))

            # 2. RÉCUPÉRATION DES RÉGLAGES (Pour éviter les erreurs Jinja2 'Undefined')
            cursor = await conn.execute("SELECT * FROM settings WHERE id = 1")
            s_info = await cursor.fetchone()
            exp_settings = dict(s_info) if s_info else {}

            # 3. RÉCUPÉRATION DE L'HISTORIQUE JOURNALIER (30 Derniers Jours)
            cursor = await conn.execute("""
                SELECT day, messages, watchtime, points_gained 
                FROM viewer_daily_stats 
                WHERE twitch_id = $1 
                ORDER BY day DESC LIMIT 30
            """, (twitch_id,))
            raw_daily = await cursor.fetchall()
            
            daily_stats = []
            for d in raw_daily:
                item = dict(d)
                item['watchtime_readable'] = format_to_hhmm(item.get('watchtime', 0))
                daily_stats.append(item)

            # 4. RÉCUPÉRATION DES LOGS D'ÉVÉNEMENTS SPÉCIAUX D'EXP
            cursor = await conn.execute("""
                SELECT event_type, amount, details, timestamp 
                FROM viewer_exp_log 
                WHERE twitch_id = $1 
                ORDER BY timestamp DESC LIMIT 50
            """, (twitch_id,))
            raw_exp = await cursor.fetchall()
            
            exp_logs = []
            for e in raw_exp:
                item = dict(e)
                item['timestamp'] = format_date(item.get('timestamp'))
                exp_logs.append(item)

        # 5. ENVOI DE LA FICHE AU TEMPLATE
        return templates.TemplateResponse(
            request,
            "admin/viewer_history.html",
            {
                "viewer": viewer,
                "daily_stats": daily_stats,
                "special_events": exp_logs,
                "exp_settings": exp_settings
            }
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ [PROFILE ERROR] Erreur Fatale pour l'ID {twitch_id} : {e}")
        return HTMLResponse(content=f"<h1>Erreur Profil</h1><p>{e}</p>", status_code=500)

# =================================================================
# 💾 ROUTE : SAUVEGARDE DU PROFIL (POST)
# =================================================================

@router.post("/viewer/{twitch_id}/save")
async def save_viewer_profile(
    request: Request, 
    twitch_id: str,
    nickname: str = Form(None),
    nickname_for_bot: str = Form(None),
    birthday: str = Form(None),
    sleep_pattern: str = Form("none"),
    pronouns: str = Form(None),
    vibe: str = Form(None),
    favorite_game: str = Form(None),
    comfort_game: str = Form(None),
    signature_emote: str = Form(None),
    play_style: str = Form("chill"),
    useless_talent: str = Form(None),
    favorite_feature: str = Form(None),
    favorite_food: str = Form(None),
    favorite_drink: str = Form(None),
    free_message: str = Form(None),
    roast_level: int = Form(5)
):
    """
    Enregistre les modifications de la fiche viewer.
    Met à jour toutes les colonnes destinées au contexte du Cerveau de Félix.
    """
    try:
        async with get_db_connection() as conn:
            await conn.execute("""
                UPDATE viewers SET 
                    nickname = $1, 
                    nickname_for_bot = $2, 
                    birthday = $3, 
                    sleep_pattern = $4, 
                    pronouns = $5, 
                    vibe = $6, 
                    favorite_game = $7, 
                    comfort_game = $8, 
                    signature_emote = $9, 
                    play_style = $10, 
                    useless_talent = $11, 
                    favorite_feature = $12, 
                    favorite_food = $13, 
                    favorite_drink = $14, 
                    free_message = $15, 
                    roast_level = $16
                WHERE twitch_id = $17
            """, (
                nickname, nickname_for_bot, birthday, sleep_pattern,
                pronouns, vibe, favorite_game, comfort_game,
                signature_emote, play_style, useless_talent,
                favorite_feature, favorite_food, favorite_drink,
                free_message, roast_level, twitch_id
            ))
        
        return RedirectResponse(url=f"/admin/viewer/{twitch_id}/history?saved=true", status_code=303)
        
    except Exception as e:
        logger.error(f"❌ [SAVE ERROR] Profil {twitch_id} : {e}")
        return HTMLResponse(content=f"Erreur lors de la sauvegarde : {e}", status_code=500)
