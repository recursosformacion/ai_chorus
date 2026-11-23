"""Regresión: la renovación de sesión debe guardar el refresh token rotado por Auth."""

from dataclasses import replace

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import create_app


class _AuthResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _AuthClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, method, url, json=None, headers=None):
        if url.endswith("/auth/refresh"):
            assert method == "POST"
            assert json == {"refresh_token": "old-refresh"}
            return _AuthResponse(200, {
                "access_token": "new-access",
                "refresh_token": "rotated-refresh",
                "user_id": "user-1",
                "roles": ["user"],
            })
        if url.endswith("/auth/me"):
            assert method == "GET"
            return _AuthResponse(200, {
                "user_id": "user-1",
                "email": "user@example.test",
                "status": "active",
                "roles": ["user"],
                "onboarding": {"required": False},
            })
        raise AssertionError(f"Unexpected Auth request: {method} {url}")


def test_refresh_persists_rotated_refresh_token(integration_settings, monkeypatch):
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    monkeypatch.setattr(main_module.httpx, "Client", _AuthClient)

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/auth/refresh",
            cookies={"chorus_refresh": "old-refresh"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["access_token"] == "new-access"
    set_cookies = response.headers.get_list("set-cookie")
    assert any("chorus_refresh=rotated-refresh" in value for value in set_cookies)
    assert not any("chorus_refresh=old-refresh" in value for value in set_cookies)
