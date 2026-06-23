import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.security import COOKIE_NAME, SESSION_MAX_AGE, create_admin_session_token
from app.core.rate_limit import limiter

router = APIRouter(tags=["admin_auth"])

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: bool = False):
    return templates.TemplateResponse(request=request, name="admin/login.html", context={"error": error})


@router.post("/admin/login")
@limiter.limit("5/minute")
async def admin_login(request: Request, password: str = Form(...)):
    if not settings.ADMIN_PASSWORD or password != settings.ADMIN_PASSWORD:
        return RedirectResponse(url="/admin/login?error=true", status_code=303)

    response = RedirectResponse(url="/admin/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        create_admin_session_token(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
