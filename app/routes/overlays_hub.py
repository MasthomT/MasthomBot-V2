"""Page unique « Overlays OBS » : Scène OBS, Alertes et Labels réunis en onglets.

Chaque onglet charge la page d'origine en mode intégré (?embed=1, sans menu latéral) ; les pages
/admin/scene, /admin/alerts et /admin/labels continuent de fonctionner seules.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.security import require_admin

router = APIRouter(tags=["overlays_hub"], dependencies=[Depends(require_admin)])
templates = Jinja2Templates(directory="app/templates")


@router.get("/admin/overlays", response_class=HTMLResponse)
async def admin_overlays_hub(request: Request):
    return templates.TemplateResponse(request=request, name="admin/overlays_hub.html")
