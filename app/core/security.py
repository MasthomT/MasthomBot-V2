import logging

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

logger = logging.getLogger("masthbot.security")

COOKIE_NAME = "admin_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12h

if not settings.ADMIN_SESSION_SECRET:
    logger.warning(
        "⚠️ [SECURITY] ADMIN_SESSION_SECRET n'est pas défini dans le .env — "
        "les sessions admin ne sont pas sécurisées correctement."
    )

_serializer = URLSafeTimedSerializer(
    settings.ADMIN_SESSION_SECRET or "insecure-dev-secret",
    salt="admin-session",
)


def create_admin_session_token() -> str:
    return _serializer.dumps({"role": "admin"})


def require_admin(request: Request) -> None:
    """Dépendance FastAPI : protège une route en exigeant une session admin valide."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Authentification admin requise.")
    try:
        _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Session admin invalide ou expirée.")
