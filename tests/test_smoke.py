"""Tests de fumée : vérifient que l'app démarre et que les routes critiques
répondent correctement, sans dépendre d'une vraie base Postgres ou de
credentials externes. Objectif : attraper les régressions de câblage
(import cassé, dépendance d'auth manquante, signature TemplateResponse
incompatible) avant un déploiement.
"""

import app.main as main_module
from app.core.config import settings


def test_app_imports_and_has_routes():
    assert len(main_module.app.routes) > 50


def test_admin_routes_require_auth_without_cookie(client):
    protected_paths = [
        "/admin/",
        "/admin/stats",
        "/admin/vips",
        "/admin/clips_manager",
    ]
    for path in protected_paths:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} devrait être protégé (401), reçu {resp.status_code}"


def test_deck_and_sensitive_routes_require_auth(client):
    # Le port 8000 est exposé publiquement (tunnel) : le deck (qui pilote OBS, le chat,
    # les pubs…) et les routes d'écriture sensibles exigent désormais la session admin.
    assert client.get("/deck", headers={"accept": "application/json"}).status_code == 401
    assert client.post("/api/deck/action", json={"action": "clear"}).status_code == 401
    assert client.post("/api/instant-replay").status_code == 401
    assert client.post("/api/trigger-effect", json={}).status_code == 401
    assert client.post("/api/stop-effect", json={}).status_code == 401
    assert client.get("/api/felix/toggle").status_code == 401


def test_admin_login_page_renders(client):
    resp = client.get("/admin/login")
    assert resp.status_code == 200
    assert "Connexion Admin" in resp.text or "mot de passe" in resp.text.lower()


def test_admin_login_wrong_password_redirects_with_error(client):
    resp = client.post("/admin/login", data={"password": "totalement_faux"}, follow_redirects=False)
    assert resp.status_code == 303
    assert "error" in resp.headers["location"]


def test_admin_login_correct_password_grants_access(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "test-password-123")

    login_resp = client.post("/admin/login", data={"password": "test-password-123"}, follow_redirects=False)
    assert login_resp.status_code == 303
    assert "admin_session" in login_resp.cookies

    authed_resp = client.get("/admin/")
    assert authed_resp.status_code == 200


def test_admin_login_rate_limited_after_5_attempts(client):
    for _ in range(5):
        client.post("/admin/login", data={"password": "wrong"})
    resp = client.post("/admin/login", data={"password": "wrong"})
    assert resp.status_code == 429


def test_public_overlay_routes_stay_open(client):
    for path in ["/overlay/clips", "/admin/overlay/clips", "/overlay_deck"]:
        resp = client.get(path)
        assert resp.status_code != 401, f"{path} ne devrait pas exiger d'auth admin"


def test_leaderboard_page_open_without_login(client):
    resp = client.get("/classement")
    assert resp.status_code == 200
    assert "Classement" in resp.text


