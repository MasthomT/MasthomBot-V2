import sqlite3
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("masthbot.announcements")

# Initialisation du router
router = APIRouter(tags=["announcements"])
templates = Jinja2Templates(directory="app/templates")

# CHEMIN OFFICIEL DE LA BASE DE DONNÉES (CORRIGÉ)
DB_PATH = "/home/masthom/BOT_V2/bot_database.db"

# Schéma de données attendu depuis le Javascript de l'interface
class Announcement(BaseModel):
    id: Optional[int] = None
    label: str
    message_template: str
    trigger_type: str
    interval_minutes: int
    group_name: Optional[str] = ""
    is_enabled: int = 1

def get_db():
    """
    Connexion à la BDD. 
    Vérifie et crée la table 'announcements' si elle n'existe pas encore.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            message_template TEXT,
            trigger_type TEXT,
            interval_minutes INTEGER,
            group_name TEXT,
            is_enabled INTEGER DEFAULT 1,
            last_triggered DATETIME
        )
    ''')
    conn.commit()
    return conn

# ==========================================
# PAGE HTML DU GESTIONNAIRE
# ==========================================
@router.get("/admin/announcements", response_class=HTMLResponse)
async def admin_announcements_page(request: Request):
    """Affiche la page Web d'administration des annonces."""
    # On initialise la table au moment où tu ouvres la page (sécurité)
    conn = get_db()
    conn.close()
    
    # CORRECTION FASTAPI : 'request' DOIT être le premier argument de TemplateResponse
    return templates.TemplateResponse(request, "admin/announcements.html", {"request": request})

# ==========================================
# API : LECTURE (POUR L'INTERFACE WEB)
# ==========================================
@router.get("/api/announcements")
async def get_announcements():
    """Renvoie la liste de toutes les annonces au format JSON pour l'interface."""
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM announcements ORDER BY id DESC").fetchall()
        conn.close()
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
        conn = get_db()
        if ann.id:
            # Mise à jour d'une annonce existante
            conn.execute("""
                UPDATE announcements 
                SET label=?, message_template=?, trigger_type=?, interval_minutes=?, group_name=?, is_enabled=?
                WHERE id=?
            """, (ann.label, ann.message_template, ann.trigger_type, ann.interval_minutes, ann.group_name, ann.is_enabled, ann.id))
        else:
            # Création d'une toute nouvelle annonce
            conn.execute("""
                INSERT INTO announcements (label, message_template, trigger_type, interval_minutes, group_name, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ann.label, ann.message_template, ann.trigger_type, ann.interval_minutes, ann.group_name, ann.is_enabled))
        conn.commit()
        conn.close()
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
        conn = get_db()
        conn.execute("DELETE FROM announcements WHERE id=?", (ann_id,))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Erreur suppression annonce : {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
