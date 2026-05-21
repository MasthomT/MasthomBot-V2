import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

# 👇 L'IMPORT MAGIQUE POUR POSTGRESQL (Le même que le bot)
from app.core.database import get_db_connection

logger = logging.getLogger("masthbot.announcements")

# Initialisation du router
router = APIRouter(tags=["announcements"])
templates = Jinja2Templates(directory="app/templates")

# Schéma de données attendu depuis le Javascript de l'interface
class Announcement(BaseModel):
    id: Optional[int] = None
    label: str
    message_template: str
    trigger_type: str
    interval_minutes: int
    group_name: Optional[str] = ""
    is_enabled: int = 1

# ==========================================
# PAGE HTML DU GESTIONNAIRE
# ==========================================
@router.get("/admin/announcements", response_class=HTMLResponse)
async def admin_announcements_page(request: Request):
    """Affiche la page Web d'administration des annonces."""
    return templates.TemplateResponse(request=request, name="admin/announcements.html", context={"request": request})

# ==========================================
# API : LECTURE (POUR L'INTERFACE WEB)
# ==========================================
@router.get("/api/announcements")
async def get_announcements():
    """Renvoie la liste de toutes les annonces au format JSON pour l'interface."""
    try:
        async with get_db_connection() as conn:
            cursor = await conn.execute("SELECT * FROM announcements ORDER BY id DESC")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Erreur lecture annonces : {e}")
        return []

# ==========================================
# API : SAUVEGARDE / CRÉATION
# ==========================================
@router.post("/api/announcements/save")
async def save_announcement(ann: Announcement):
    """Enregistre une nouvelle annonce ou met à jour une annonce existante."""
    try:
        async with get_db_connection() as conn:
            if ann.id:
                # Mise à jour PostgreSQL
                await conn.execute("""
                    UPDATE announcements 
                    SET label=$1, message_template=$2, trigger_type=$3, interval_minutes=$4, group_name=$5, is_enabled=$6
                    WHERE id=$7
                """, (ann.label, ann.message_template, ann.trigger_type, ann.interval_minutes, ann.group_name, ann.is_enabled, ann.id))
            else:
                # Création PostgreSQL
                await conn.execute("""
                    INSERT INTO announcements (label, message_template, trigger_type, interval_minutes, group_name, is_enabled)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, (ann.label, ann.message_template, ann.trigger_type, ann.interval_minutes, ann.group_name, ann.is_enabled))
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erreur sauvegarde annonce : {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# ==========================================
# API : SUPPRESSION
# ==========================================
@router.delete("/api/announcements/delete/{ann_id}")
async def delete_announcement(ann_id: int):
    """Supprime définitivement une annonce de la base de données."""
    try:
        async with get_db_connection() as conn:
            await conn.execute("DELETE FROM announcements WHERE id=$1", (ann_id,))
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erreur suppression annonce : {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
