"""Routes viewer : l'identité doit être prouvée (jeton Twitch ou cookie signé),
et un viewer ne peut agir que sur sa propre fiche."""

import pytest

from app.core import viewer_auth
from app.core.viewer_auth import ViewerIdentity, make_viewer_cookie_value

ME, OTHER = "111", "222"


@pytest.fixture
def fake_twitch(monkeypatch):
    """Simule /oauth2/validate : seul le jeton "good" est valide, et il appartient à ME."""
    async def _validate(token):
        return ViewerIdentity(user_id=ME, login="moi") if token == "good" else None
    monkeypatch.setattr(viewer_auth, "_validate_token", _validate)


def _bearer(token="good"):
    return {"Authorization": f"Bearer {token}"}


VIEWER_ROUTES = [
    ("post", "/api/v1/viewer/update_context", {"json": {"twitch_id": OTHER}}),
    ("post", "/viewer/update_context", {"json": {"twitch_id": OTHER}}),
    ("get", f"/api/viewers/{OTHER}", {}),
    ("get", f"/viewer/{OTHER}", {}),
    ("get", f"/api/vip-sound/status?twitch_id={OTHER}", {}),
    ("post", "/api/vip-sound/submit", {"data": {"twitch_id": OTHER}, "files": {"file": ("a.mp3", b"x", "audio/mpeg")}}),
    ("post", "/api/auth/session", {"json": {"twitch_id": OTHER}}),
]


@pytest.mark.parametrize("method,path,kwargs", VIEWER_ROUTES)
def test_viewer_routes_require_proof(client, fake_twitch, method, path, kwargs):
    assert getattr(client, method)(path, **kwargs).status_code == 401


@pytest.mark.parametrize("method,path,kwargs", VIEWER_ROUTES)
def test_invalid_token_rejected(client, fake_twitch, method, path, kwargs):
    assert getattr(client, method)(path, headers=_bearer("bad"), **kwargs).status_code == 401


@pytest.mark.parametrize("method,path,kwargs", VIEWER_ROUTES)
def test_cannot_act_on_someone_else(client, fake_twitch, method, path, kwargs):
    assert getattr(client, method)(path, headers=_bearer(), **kwargs).status_code == 403


def test_forged_plain_cookie_is_ignored(client, fake_twitch):
    client.cookies.set("viewer_id", OTHER)
    assert client.get(f"/api/viewers/{OTHER}").status_code == 401


def test_signed_cookie_only_works_for_its_owner(client, fake_twitch):
    client.cookies.set("viewer_id", make_viewer_cookie_value(ME))
    assert client.get(f"/api/viewers/{OTHER}").status_code == 403


def test_unused_viewer_admin_routes_need_admin(client):
    assert client.get("/api/viewers").status_code == 401
    assert client.get(f"/api/v1/viewers/{OTHER}").status_code == 401
    assert client.post(f"/api/viewers/{OTHER}/nickname", json={"nickname": "x"}).status_code == 401
    assert client.post(f"/api/viewers/{OTHER}/roast", json={"level": 1}).status_code == 401


def test_token_from_foreign_app_rejected(monkeypatch):
    """Un jeton valide mais émis pour une autre application Twitch est refusé."""
    class _Resp:
        status = 200
        async def json(self):
            return {"client_id": "autre-appli", "user_id": ME, "login": "moi", "expires_in": 3600}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False

    class _Session:
        def __init__(self, *a, **k): pass
        def get(self, *a, **k): return _Resp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    monkeypatch.setattr(viewer_auth.aiohttp, "ClientSession", _Session)
    viewer_auth._cache.clear()
    import asyncio
    assert asyncio.run(viewer_auth._validate_token("jeton-autre-appli")) is None
