import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.security import require_admin

logger = logging.getLogger("masthbot.admin_games")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(prefix="/admin", tags=["admin_games"], dependencies=[Depends(require_admin)])


@router.get("/games_manager", response_class=HTMLResponse)
async def games_manager_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin/games_manager.html", context={})
