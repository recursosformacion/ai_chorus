"""Solicitudes públicas de alta de entidades."""

from __future__ import annotations

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


class FakeAuthResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def install_fake_auth(monkeypatch, profiles):
    class FakeAuthClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, json=None, headers=None):
            path = url.removeprefix("https://auth.test")
            token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
            if method == "GET" and path == "/auth/me":
                profile = profiles.get(token)
                return FakeAuthResponse(200, profile) if profile else FakeAuthResponse(401, {})
            return FakeAuthResponse(404, {})

    monkeypatch.setattr("app.main.httpx.Client", FakeAuthClient)


def _settings(tmp_path):
    return Settings(
        auth_base_url="https://auth.test",
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
        secure_cookies=False,
    )


PAYLOAD = {
    "entity_name": "Coral Aurora",
    "entity_kind": "coral",
    "city": "Madrid",
    "members": 35,
    "contact_name": "Ana Belmonte",
    "contact_email": "ana@example.com",
    "contact_phone": "+34600000000",
    "manager_name": "Ana Belmonte",
    "manager_email": "ana@example.com",
    "manager_has_account": True,
    "website": "https://coral.example",
    "interests": ["subscription", "whatsapp"],
    "message": "Nos interesa la agenda y el repertorio.",
    "consent": True,
    "company_website": "",
}


def test_alta_publica_y_listado_admin(tmp_path, monkeypatch):
    profiles = {
        "token-admin": {"user_id": "admin-1", "roles": ["admin"], "email_verified": True,
                        "status": "active", "onboarding": {"required": False}},
        "token-user": {"user_id": "user-1", "roles": ["user"], "email_verified": True,
                       "status": "active", "onboarding": {"required": False}},
    }
    install_fake_auth(monkeypatch, profiles)
    with TestClient(create_app(_settings(tmp_path))) as client:
        created = client.post("/api/v1/entity-leads", json=PAYLOAD)
        assert created.status_code == 201
        assert created.json()["status"] == "received"

        assert client.post(
            "/api/v1/entity-leads", json={**PAYLOAD, "consent": False}
        ).status_code == 400

        denied = client.get(
            "/api/v1/admin/entity-leads", headers={"Authorization": "Bearer token-user"}
        )
        assert denied.status_code == 403

        leads = client.get(
            "/api/v1/admin/entity-leads", headers={"Authorization": "Bearer token-admin"}
        )
        assert leads.status_code == 200
        assert leads.json()[0]["entity_name"] == "Coral Aurora"
        assert leads.json()[0]["interests"] == ["subscription", "whatsapp"]


def test_honeypot_no_guarda(tmp_path, monkeypatch):
    install_fake_auth(monkeypatch, {})
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.post(
            "/api/v1/entity-leads", json={**PAYLOAD, "company_website": "spam"}
        )
        assert response.status_code == 201
        assert response.json()["id"] == ""

