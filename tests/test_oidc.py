from __future__ import annotations

import pytest
from urllib.parse import parse_qs, urlparse

from app.config import Settings
from app.db import connect as db_connect
from app.main import create_app
from fastapi.testclient import TestClient


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


@pytest.fixture
def settings(integration_settings: Settings, tmp_path):
    """Settings con MariaDB de integración y storage_root en tmp_path."""
    return Settings(
        auth_base_url="https://auth.test",
        osap_api_base_url="http://osap.test",
        editor_base_url="http://editor.test",
        editor_origin="http://editor.test",
        public_base_url="http://chorus.test",
        database_url=integration_settings.database_url,
        storage_root=str(tmp_path / "private"),
        cors_origins=integration_settings.cors_origins,
        max_upload_bytes=integration_settings.max_upload_bytes,
        source_token_ttl_seconds=integration_settings.source_token_ttl_seconds,
        oidc_issuer="https://auth.test",
        oidc_authorize_url="https://auth.test/auth/authorize",
        oidc_token_url="https://auth.test/oauth/token",
        oidc_client_id="chorus-web",
        oidc_client_secret="secret",
        oidc_redirect_uri="http://chorus.test/api/v1/auth/oidc/callback",
        oidc_scope="openid profile email",
        auth_timeout_seconds=15.0,
        osap_timeout_seconds=45.0,
        secure_cookies=False,
    )


@pytest.mark.db
def test_oidc_start_builds_a_pkce_authorize_url(settings, monkeypatch):
    monkeypatch.setattr("app.main.httpx.Client", FakeOidcClient)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/auth/oidc/start")
    assert response.status_code == 200, response.text
    authorize = urlparse(response.json()["authorize_url"])
    query = parse_qs(authorize.query)
    assert query["client_id"] == ["chorus-web"]
    assert query["redirect_uri"] == ["http://chorus.test/api/v1/auth/oidc/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"]


@pytest.mark.db
def test_oidc_callback_exchanges_code_and_sets_refresh_cookie(settings, monkeypatch):
    monkeypatch.setattr("app.main.httpx.Client", FakeOidcClient)
    with TestClient(create_app(settings)) as client:
        client.get("/api/v1/auth/oidc/start")
        with db_connect(settings) as conn:
            state = conn.execute("SELECT state FROM oidc_states").fetchone()["state"]
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

    with db_connect(settings) as conn:
        count = conn.execute("SELECT COUNT(*) AS cnt FROM oidc_states").fetchone()["cnt"]
    assert count == 0


@pytest.mark.db
def test_oidc_callback_rejects_unknown_or_reused_state(settings, monkeypatch):
    monkeypatch.setattr("app.main.httpx.Client", FakeOidcClient)
    with TestClient(create_app(settings)) as client:
        invalid = client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "code-1", "state": "missing"},
            follow_redirects=False,
        )
        assert invalid.status_code == 400

        client.get("/api/v1/auth/oidc/start")
        with db_connect(settings) as conn:
            state = conn.execute("SELECT state FROM oidc_states").fetchone()["state"]
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