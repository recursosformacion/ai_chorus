from __future__ import annotations

import sqlite3
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeOidcClient:
    def __init__(self, timeout=None):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, method, url, json=None, headers=None, data=None):
        if method == "GET" and url.endswith("/.well-known/openid-configuration"):
            return FakeResponse(
                200,
                {
                    "authorization_endpoint": "https://auth.test/auth/authorize",
                    "token_endpoint": "https://auth.test/oauth/token",
                },
            )
        if method == "GET" and url.endswith("/auth/me"):
            return FakeResponse(
                200,
                {
                    "user_id": "user-1",
                    "roles": ["user"],
                    "email_verified": True,
                    "status": "active",
                    "onboarding": {"required": False},
                },
            )
        if method == "POST" and url.endswith("/oauth/token"):
            return FakeResponse(
                200, {"access_token": "access-1", "refresh_token": "refresh-1"}
            )
        return FakeResponse(404, {})

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


def _settings(tmp_path) -> Settings:
    return Settings(
        auth_base_url="https://auth.test",
        public_base_url="http://chorus.test",
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
        secure_cookies=False,
        oidc_issuer="https://auth.test",
        oidc_client_id="chorus-web",
        oidc_client_secret="secret",
        oidc_redirect_uri="http://chorus.test/api/v1/auth/oidc/callback",
    )


def test_oidc_start_builds_a_pkce_authorize_url(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.httpx.Client", FakeOidcClient)
    with TestClient(create_app(_settings(tmp_path))) as client:
        response = client.get("/api/v1/auth/oidc/start")
    assert response.status_code == 200, response.text
    authorize = urlparse(response.json()["authorize_url"])
    query = parse_qs(authorize.query)
    assert query["client_id"] == ["chorus-web"]
    assert query["redirect_uri"] == ["http://chorus.test/api/v1/auth/oidc/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"]


def test_oidc_callback_exchanges_code_and_sets_refresh_cookie(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.httpx.Client", FakeOidcClient)
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        client.get("/api/v1/auth/oidc/start")
        with sqlite3.connect(settings.database_path) as conn:
            state = conn.execute("SELECT state FROM oidc_states").fetchone()[0]
        response = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "code-1", "state": state},
            follow_redirects=False,
        )
    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "http://chorus.test/auth-callback.html#access_token=access-1"
    )
    assert "chorus_refresh=refresh-1" in response.headers.get("set-cookie", "")

    with sqlite3.connect(settings.database_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM oidc_states").fetchone()[0] == 0


def test_oidc_callback_rejects_unknown_or_reused_state(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.httpx.Client", FakeOidcClient)
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        invalid = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "code-1", "state": "missing"},
            follow_redirects=False,
        )
        assert invalid.status_code == 400

        client.get("/api/v1/auth/oidc/start")
        with sqlite3.connect(settings.database_path) as conn:
            state = conn.execute("SELECT state FROM oidc_states").fetchone()[0]
        first = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "code-1", "state": state},
            follow_redirects=False,
        )
        assert first.status_code == 302
        reused = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "code-1", "state": state},
            follow_redirects=False,
        )
        assert reused.status_code == 400
