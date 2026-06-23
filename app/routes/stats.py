import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# --- IMPORT CORE POSTGRESQL ---
from app.core.database import get_db_connection
from app.core.security import require_admin

# --- CONFIGURATION DU LOGGING ---
logger = logging.getLogger("masthbot.stats")

# --- INITIALISATION DU ROUTER ---
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

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

            # 6. ACTIVITÉ COMMUNAUTÉ SUR 14 JOURS (messages + watchtime agrégés par jour)
            cursor = await conn.execute(f"""
                SELECT ds.day, SUM(ds.messages) AS messages, SUM(ds.watchtime) AS watchtime
                FROM viewer_daily_stats ds
                JOIN viewers v ON v.twitch_id = ds.twitch_id
                WHERE ds.day >= CURRENT_DATE - INTERVAL '13 days'
                AND LOWER(v.username) NOT IN {EXCLUSION_LIST}
                GROUP BY ds.day
                ORDER BY ds.day ASC
            """)
            raw_activity = await cursor.fetchall()
            activity_by_day = {str(r["day"]): {"messages": r["messages"] or 0, "watchtime": r["watchtime"] or 0} for r in raw_activity}

            today = datetime.now().date()
            activity_trend = []
            for i in range(13, -1, -1):
                day = today - timedelta(days=i)
                day_str = str(day)
                entry = activity_by_day.get(day_str, {"messages": 0, "watchtime": 0})
                activity_trend.append({
                    "date": day.strftime("%d/%m"),
                    "messages": entry["messages"],
                    "watchtime_minutes": round(entry["watchtime"] / 60)
                })

            # 7. RÉTENTION : VIEWERS ACTIFS SUR 7 JOURS
            cursor = await conn.execute(f"""
                SELECT COUNT(DISTINCT ds.twitch_id) FROM viewer_daily_stats ds
                JOIN viewers v ON v.twitch_id = ds.twitch_id
                WHERE ds.day >= CURRENT_DATE - INTERVAL '6 days'
                AND LOWER(v.username) NOT IN {EXCLUSION_LIST}
                AND (ds.messages > 0 OR ds.watchtime > 0)
            """)
            res_active7 = await cursor.fetchone()
            active_viewers_7d = res_active7[0] if res_active7 else 0

            retention_rate = round((active_viewers_7d / total_viewers) * 100, 1) if total_viewers > 0 else 0
            avg_messages_per_active = round(total_messages / active_viewers_7d, 1) if active_viewers_7d > 0 else 0

        # 6. ENVOI AU TEMPLATE HTML
        return templates.TemplateResponse(
            request,
            "admin/stats.html",
            {
                "general_stats": {
                    "total_viewers": total_viewers,
                    "total_messages": total_messages,
                    "watchtime_display": format_to_hhmm(total_seconds),
                    "active_viewers_7d": active_viewers_7d,
                    "retention_rate": retention_rate,
                    "avg_messages_per_active": avg_messages_per_active
                },
                "top_messages": [dict(r) for r in top_messages],
                "top_watchtime": top_watchtime,
                "top_points": top_points,
                "recent_events": recent_events,
                "recent_unfollows": recent_unfollows,
                "recent_logins": recent_logins,
                "activity_trend": activity_trend
            }
        )

    except Exception as e:
        logger.error(f"❌ [STATS] Erreur Critique : {e}")
        return HTMLResponse(content=f"<h1>Erreur Interne : Statistiques</h1><p>{e}</p>", status_code=500)

# NOTE : GET /viewer/{twitch_id}/history et POST /viewer/{twitch_id}/save vivaient ici en
# double avec app/routes/viewers.py (mêmes routes une fois le préfixe /admin appliqué).
# La version de viewers.py gagnait silencieusement (routeur enregistré avant celui-ci) et est
# plus complète (inclut viewer_trophies) — celle-ci était totalement morte. Supprimée.
