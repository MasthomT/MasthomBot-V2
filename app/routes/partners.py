"""
partners_routes.py — Routes API pour la page Partenaires

Routes publiques (lues par partenaires.html, pas d'auth nécessaire) :
  GET  /api/v1/partners

Routes admin (protégées) :
  GET    /admin/partners               -> page de gestion
  POST   /api/v1/partners/add          -> ajout manuel
  PATCH  /api/v1/partners/{id}         -> édition (description, type)
  DELETE /api/v1/partners/{id}         -> suppression définitive
  POST   /api/v1/partners/{id}/deactivate -> masquage (garde l'historique)

⚠️ INTÉGRATION REQUISE : adapte l'import de `require_admin` ci-dessous selon
ton système d'auth réel. Je l'ai vu utilisé dans credits.py comme
`from app.core.security import require_admin` — je réutilise le même import
ici pour rester cohérent avec ton code existant.
"""

import logging
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from app.core.security import require_admin
from app.services import partners_service

logger = logging.getLogger("masthbot.partners_routes")
router = APIRouter(tags=["partners"])
templates = Jinja2Templates(directory="app/templates")


class AddPartnerPayload(BaseModel):
    twitch_login: str
    description: str = ""
    partnership_type: str = "Collab"
    category: str = "manual"


class UpdatePartnerPayload(BaseModel):
    description: Optional[str] = None
    partnership_type: Optional[str] = None
    category: Optional[str] = None


# ==========================================
# ROUTE PUBLIQUE
# ==========================================

@router.get("/api/v1/partners")
async def get_partners_public():
    """
    Liste publique des partenaires actifs, avec statut live calculé en direct.
    Appelée par partenaires.html — pas d'authentification requise.
    """
    try:
        partners = await partners_service.get_all_partners(include_inactive=False)
        return {"partners": partners}
    except Exception as e:
        logger.error(f"❌ [PARTNERS API] Erreur get_partners_public: {e}")
        return JSONResponse(status_code=500, content={"partners": [], "error": "Erreur serveur"})


# ==========================================
# ROUTES ADMIN
# ==========================================

@router.get("/admin/partners", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_partners_page(request: Request):
    """Page de gestion des partenaires (ajout manuel, édition, suppression)."""
    partners = await partners_service.get_all_partners(include_inactive=True)
    return templates.TemplateResponse(
        request=request,
        name="admin/partners.html",
        context={"request": request, "partners": partners}
    )


@router.post("/api/v1/partners/add", dependencies=[Depends(require_admin)])
async def add_partner(payload: AddPartnerPayload):
    try:
        user_info = await partners_service.add_partner_manual(
            twitch_login=payload.twitch_login,
            description=payload.description,
            partnership_type=payload.partnership_type,
            category=payload.category
        )
        return {"status": "success", "partner": user_info}
    except ValueError as e:
        return JSONResponse(status_code=404, content={"status": "error", "message": str(e)})
    except Exception as e:
        logger.error(f"❌ [PARTNERS API] Erreur add_partner: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "Erreur serveur"})


@router.patch("/api/v1/partners/{partner_id}", dependencies=[Depends(require_admin)])
async def edit_partner(partner_id: int, payload: UpdatePartnerPayload):
    try:
        await partners_service.update_partner(
            partner_id,
            description=payload.description,
            partnership_type=payload.partnership_type,
            category=payload.category
        )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ [PARTNERS API] Erreur edit_partner: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "Erreur serveur"})


@router.delete("/api/v1/partners/{partner_id}", dependencies=[Depends(require_admin)])
async def delete_partner(partner_id: int):
    try:
        await partners_service.remove_partner(partner_id)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ [PARTNERS API] Erreur delete_partner: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "Erreur serveur"})


@router.post("/api/v1/partners/{partner_id}/deactivate", dependencies=[Depends(require_admin)])
async def deactivate_partner_route(partner_id: int):
    try:
        await partners_service.deactivate_partner(partner_id)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"❌ [PARTNERS API] Erreur deactivate_partner: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "Erreur serveur"})


@router.post("/api/v1/partners/import_tracked", dependencies=[Depends(require_admin)])
async def import_tracked_partners():
    """Reprend les streamers suivis dans les notifications de live comme partenaires 'Recommandés'."""
    try:
        result = await partners_service.import_from_tracked_streamers()
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"❌ [PARTNERS API] Erreur import_tracked_partners: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "Erreur serveur"})


@router.post("/api/v1/partners/import_moderators", dependencies=[Depends(require_admin)])
async def import_moderator_partners():
    """Reprend les modérateurs/rices Twitch comme partenaires 'Modérateur/rice'."""
    try:
        result = await partners_service.import_twitch_moderators()
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"❌ [PARTNERS API] Erreur import_moderator_partners: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "Erreur serveur"})
