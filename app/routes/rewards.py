import sqlite3
import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.routes.overlays import trigger_overlay_event

logger = logging.getLogger("masthbot.rewards")
router = APIRouter(prefix="/admin", tags=["rewards"])
templates = Jinja2Templates(directory="app/templates")
DB_PATH = "bot_database.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- PAGE PRINCIPALE ---
@router.get("/trophy_manager", response_class=HTMLResponse)
@router.get("/trophy_manager.html", response_class=HTMLResponse)
async def trophy_manager_page(request: Request):
    conn = get_db()
    try:
        # On récupère tous les trophées pour le catalogue
        trophies = conn.execute("SELECT * FROM trophy_list ORDER BY label").fetchall()
        
        # 🛡️ REQUÊTE SIMPLIFIÉE : On récupère les 15 derniers trophées décernés
        # On utilise des LEFT JOIN pour éviter qu'un viewer disparaisse s'il y a un micro-bug de data
        recent_wins = conn.execute("""
            SELECT 
                v.username, 
                t.label, 
                t.icon, 
                t.tier,
                vt.earned_at, 
                vt.id as award_id
            FROM viewer_trophies vt
            LEFT JOIN viewers v ON vt.twitch_id = v.twitch_id
            LEFT JOIN trophy_list t ON vt.trophy_id = t.id
            WHERE v.username IS NOT NULL
            ORDER BY vt.earned_at DESC 
            LIMIT 50
        """).fetchall()

        return templates.TemplateResponse(
            request=request,
            name="admin/trophy_manager.html",
            context={"request": request, "trophies": trophies, "recent_wins": recent_wins}
        )
    finally:
        conn.close()

# --- BOUTON DE TEST OBS ---
@router.post("/trophy/test_obs")
async def test_specific_trophy_obs(
    label: str = Form(...), 
    icon: str = Form(...), 
    tier: str = Form("Standard")
):
    try:
        payload = {
            "type": "trophy_unlock",
            "details": {
                "username": "Testeur_Fou",
                "trophy_name": label,
                "icon": icon,
                "tier": tier
            }
        }
        await trigger_overlay_event(payload)
        return RedirectResponse(url="/admin/trophy_manager?success=1", status_code=303)
    except Exception as e:
        logger.error(f"❌ Erreur Test OBS : {e}")
        return RedirectResponse(url="/admin/trophy_manager?error=1", status_code=303)

# --- ACTIONS ADMINISTRATEUR ---
@router.post("/trophy/award")
async def award_trophy_manual(request: Request, username: str = Form(...), trophy_id: int = Form(...)):
    conn = get_db()
    try:
        # 1. Nettoyage du pseudo
        clean_username = username.lower().strip().replace("@", "").replace(" ", "")
        
        # 2. Trouver le viewer
        viewer = conn.execute("SELECT twitch_id, username FROM viewers WHERE LOWER(username) = ?", (clean_username,)).fetchone()
        if not viewer:
            return RedirectResponse(url="/admin/trophy_manager?error=viewer_not_found", status_code=303)

        # 3. Vérifier si le trophée existe déjà pour ce viewer
        exists = conn.execute("SELECT 1 FROM viewer_trophies WHERE twitch_id = ? AND trophy_id = ?", 
                             (viewer['twitch_id'], trophy_id)).fetchone()
        
        if exists:
            # ICI : Au lieu de bloquer, on va quand même essayer de déclencher l'alerte OBS 
            # pour que tu vois que ça communique, même si on n'écrit pas en base.
            logger.info(f"Le viewer {clean_username} a déjà le trophée {trophy_id}. Envoi alerte test.")
            # On récupère les infos du trophée pour l'alerte
            t_info = conn.execute("SELECT label, icon, tier FROM trophy_list WHERE id = ?", (trophy_id,)).fetchone()
            if t_info:
                await trigger_overlay_event({
                    "type": "trophy_unlock",
                    "details": {
                        "username": viewer['username'],
                        "trophy_name": t_info['label'],
                        "icon": t_info['icon'],
                        "tier": t_info['tier']
                    }
                })
            return RedirectResponse(url="/admin/trophy_manager?error=already", status_code=303)

        # 4. Insertion réelle avec COMMIT forcé
        conn.execute("""
            INSERT INTO viewer_trophies (twitch_id, trophy_id, earned_at) 
            VALUES (?, ?, datetime('now', 'localtime'))
        """, (viewer['twitch_id'], trophy_id))
        conn.commit() # 🌟 TRÈS IMPORTANT
        
        # 5. Récupérer les infos pour l'alerte OBS
        trophy = conn.execute("SELECT label, icon, tier FROM trophy_list WHERE id = ?", (trophy_id,)).fetchone()
        
        await trigger_overlay_event({
            "type": "trophy_unlock",
            "details": {
                "username": viewer['username'],
                "trophy_name": trophy['label'],
                "icon": trophy['icon'],
                "tier": trophy['tier']
            }
        })

        return RedirectResponse(url="/admin/trophy_manager?success=awarded", status_code=303)
    except Exception as e:
        logger.error(f"Erreur attribution : {e}")
        return RedirectResponse(url="/admin/trophy_manager?error=db", status_code=303)
    finally:
        conn.close()

@router.post("/trophy/revoke/{award_id}")
async def revoke_award(award_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM viewer_trophies WHERE id = ?", (award_id,))
        conn.commit()
        return RedirectResponse(url="/admin/trophy_manager.html?success=revoked", status_code=303)
    finally:
        conn.close()

@router.post("/trophy/delete/{id}")
async def delete_trophy_type(id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM trophy_list WHERE id = ?", (id,))
        conn.execute("DELETE FROM viewer_trophies WHERE trophy_id = ?", (id,))
        conn.commit()
        return RedirectResponse(url="/admin/trophy_manager.html?success=deleted", status_code=303)
    finally:
        conn.close()

@router.post("/trophy/create")
async def create_trophy(request: Request):
    conn = get_db()
    try:
        form_data = await request.form()
        conn.execute("""
            INSERT INTO trophy_list (label, icon, category, condition_type, condition_value, reward_exp, tier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            form_data.get('label'),
            form_data.get('icon', '🏆'),
            'general',
            form_data.get('condition_type', 'none'),
            int(form_data.get('condition_value', 0)),
            int(form_data.get('reward_exp', 0)),
            form_data.get('tier', 'Standard')
        ))
        conn.commit()
        return RedirectResponse(url="/admin/trophy_manager.html?success=created", status_code=303)
    finally:
        conn.close()

@router.post("/trophy/update")
async def update_trophy(request: Request):
    conn = get_db()
    try:
        form_data = await request.form()
        conn.execute("""
            UPDATE trophy_list 
            SET label=?, icon=?, condition_type=?, condition_value=?, reward_exp=?, tier=?
            WHERE id=?
        """, (
            form_data.get('label'),
            form_data.get('icon', '🏆'),
            form_data.get('condition_type', 'none'),
            int(form_data.get('condition_value', 0)),
            int(form_data.get('reward_exp', 0)),
            form_data.get('tier', 'Standard'),
            form_data.get('id')
        ))
        conn.commit()
        return RedirectResponse(url="/admin/trophy_manager.html?success=updated", status_code=303)
    finally:
        conn.close()

@router.post("/trophy/sync_auto")
async def sync_auto_trophies():
    conn = get_db()
    try:
        # 1. Récupération de tous les trophées ayant une condition automatique définie
        auto_trophies = conn.execute("SELECT * FROM trophy_list WHERE condition_type != 'none'").fetchall()

        new_awards_count = 0

        for trophy in auto_trophies:
            t_id = trophy['id']
            c_type = trophy['condition_type'].lower().strip()
            c_val = trophy['condition_value']

            # --- Préparation de la requête SQL flexible ---
            base_query = "SELECT v.twitch_id FROM viewers v"
            joins = " LEFT JOIN viewer_trophies vt ON v.twitch_id = vt.twitch_id AND vt.trophy_id = ?"
            where_clause = ""
            params = [t_id]
            target_value = c_val

            # --- LOGIQUE DES COMPTEURS ---

            # Catégorie : Fidélité & Temps
            if c_type == 'level':
                target_value = int(100 * (c_val ** 2.2)) 
                where_clause = "v.points >= ?"
            elif c_type == 'points':
                where_clause = "v.points >= ?"
            elif c_type == 'points_session':
                joins += " JOIN viewer_daily_stats ds ON v.twitch_id = ds.twitch_id AND ds.day = date('now', 'localtime')"
                where_clause = "ds.points >= ?"
            elif c_type == 'watchtime_h':
                target_value = c_val * 3600 
                where_clause = "v.watchtime >= ?"
            elif c_type == 'watchtime_session_m':
                target_value = c_val * 60 
                joins += " JOIN viewer_daily_stats ds ON v.twitch_id = ds.twitch_id AND ds.day = date('now', 'localtime')"
                where_clause = "ds.watchtime >= ?"
            elif c_type == 'streak_days':
                where_clause = "v.streak_days >= ? AND v.streak_days > 0"

            # Catégorie : Activité Chat
            elif c_type == 'messages':
                where_clause = "v.messages >= ?"
            elif c_type == 'messages_session':
                joins += " JOIN viewer_daily_stats ds ON v.twitch_id = ds.twitch_id AND ds.day = date('now', 'localtime')"
                where_clause = "ds.messages >= ?"
            elif c_type == 'emotes_global':
                where_clause = "v.emotes_count >= ?"

            # Catégorie : Statut & Soutien (CORRECTIF SUB_MONTHS)
            elif c_type == 'is_vip':
                where_clause = "v.is_vip = 1"
                target_value = None
            elif c_type == 'gifts_count':
                where_clause = "v.gifts_count >= ?"
            elif c_type == 'sub_months':
                # On utilise la nouvelle colonne sub_months que nous avons créée
                where_clause = "v.sub_months >= ? AND v.sub_months IS NOT NULL AND v.sub_months > 0"

            # Catégorie : Jeux & Rapidité
            elif c_type == 'first_count':
                where_clause = "v.first_count >= ?"
            elif c_type == 'deuz_count':
                where_clause = "v.deuz_count >= ?"
            elif c_type == 'troiz_count':
                where_clause = "v.troiz_count >= ?"

            # Catégorie : IA & Site Web
            elif c_type == 'has_context':
                where_clause = "v.nickname IS NOT NULL AND v.nickname != ''"
                target_value = None
            elif c_type == 'roast_level':
                where_clause = "v.roast_level >= ? AND v.roast_level IS NOT NULL"

            # 3. EXÉCUTION DE LA SYNCHRONISATION
            if where_clause:
                if target_value is not None:
                    params.append(target_value)

                final_query = f"{base_query}{joins} WHERE {where_clause} AND vt.id IS NULL"

                try:
                    eligible_viewers = conn.execute(final_query, tuple(params)).fetchall()

                    for v in eligible_viewers:
                        conn.execute("""
                            INSERT INTO viewer_trophies (twitch_id, trophy_id, earned_at)
                            VALUES (?, ?, datetime('now', 'localtime'))
                        """, (v['twitch_id'], t_id))
                        new_awards_count += 1

                except Exception as loop_error:
                    logger.error(f"Erreur technique sur condition '{c_type}' : {loop_error}")
                    continue

        conn.commit()
        return RedirectResponse(url=f"/admin/trophy_manager.html?success=synced&count={new_awards_count}", status_code=303)
    except Exception as e:
        logger.error(f"Erreur critique lors de la synchronisation : {e}")
        return RedirectResponse(url="/admin/trophy_manager.html?error=sync_failed", status_code=303)
    finally:
        conn.close()
