"""Authentification des viewers (site fel-x.icu et pages publiques du bot).

Avant, le site envoyait simplement un `twitch_id` au bot, qui le croyait sur parole :
n'importe qui pouvait modifier la fiche « Félix et moi » d'un autre viewer.

Désormais, une identité viewer est prouvée par :
  1. l'en-tête `Authorization: Bearer <jeton Twitch>` (envoyé par fel-x.icu) : le bot
     demande à Twitch (/oauth2/validate) à qui appartient le jeton — résultat mis en cache ;
  2. ou le cookie `viewer_id` SIGNÉ posé par le bot lui-même après une vraie connexion
     Twitch (/auth/callback) ou un appel /api/auth/session authentifié.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp
from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

logger = logging.getLogger("masthbot.viewer_auth")

COOKIE_NAME = "viewer_id"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 jours

# Applications Twitch dont on accepte les jetons : le site fel-x.icu (implicit flow) et le bot.
SITE_CLIENT_ID = "kgyfzs0k3wk8enx7p3pd6299ro4izv"

_CACHE_TTL = 600          # un jeton validé est réutilisé 10 min sans redemander à Twitch
_CACHE_MAX = 2000
_cache: dict[str, tuple["ViewerIdentity", float]] = {}

_serializer = URLSafeTimedSerializer(
    settings.ADMIN_SESSION_SECRET or "insecure-dev-secret",
    salt="viewer-session",
)


@dataclass(frozen=True)
class ViewerIdentity:
    user_id: str
    login: str = ""


def _allowed_client_ids() -> set[str]:
    return {cid for cid in (SITE_CLIENT_ID, settings.TWITCH_CLIENT_ID) if cid}


async def _validate_token(token: str) -> Optional[ViewerIdentity]:
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    hit = _cache.get(key)
    if hit and hit[1] > now:
        return hit[0]

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get("https://id.twitch.tv/oauth2/validate",
                                   headers={"Authorization": f"OAuth {token}"}) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception as e:
        logger.warning(f"⚠️ [VIEWER AUTH] Validation Twitch impossible : {e}")
        return None

    if data.get("client_id") not in _allowed_client_ids() or not data.get("user_id"):
        return None

    identity = ViewerIdentity(user_id=str(data["user_id"]), login=data.get("login") or "")
    ttl = min(_CACHE_TTL, int(data.get("expires_in") or _CACHE_TTL))
    if len(_cache) >= _CACHE_MAX:
        for k in [k for k, (_, exp) in _cache.items() if exp <= now] or list(_cache)[: _CACHE_MAX // 2]:
            _cache.pop(k, None)
    _cache[key] = (identity, now + ttl)
    return identity


def make_viewer_cookie_value(user_id: str) -> str:
    return _serializer.dumps(str(user_id))


def set_viewer_cookie(response, user_id: str) -> None:
    response.set_cookie(COOKIE_NAME, make_viewer_cookie_value(user_id), max_age=COOKIE_MAX_AGE,
                        httponly=True, samesite="none", secure=True)


def viewer_id_from_cookie(request: Request) -> Optional[str]:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        return str(_serializer.loads(raw, max_age=COOKIE_MAX_AGE))
    except (BadSignature, SignatureExpired):
        return None  # ancien cookie en clair ou falsifié : ignoré


async def get_viewer(request: Request) -> Optional[ViewerIdentity]:
    """Identité prouvée du viewer, ou None."""
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        token = auth[7:].strip()
        if token:
            return await _validate_token(token)
        return None
    cookie_id = viewer_id_from_cookie(request)
    return ViewerIdentity(user_id=cookie_id) if cookie_id else None


async def require_viewer(request: Request) -> ViewerIdentity:
    """Dépendance FastAPI : exige un viewer authentifié (jeton Twitch ou cookie signé)."""
    identity = await get_viewer(request)
    if not identity:
        raise HTTPException(status_code=401, detail="Connexion Twitch requise.")
    return identity


def ensure_self(identity: ViewerIdentity, twitch_id) -> None:
    """Refuse d'agir sur un autre viewer que celui qui est connecté."""
    if twitch_id is not None and str(twitch_id) != identity.user_id:
        raise HTTPException(status_code=403, detail="Ce profil n'est pas le tien.")
