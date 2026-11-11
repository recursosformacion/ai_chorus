from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.config import Settings
from fastapi.testclient import TestClient

from app.main import create_app, initialise_database, validate_mxl


def make_mxl(root_xml: str = '<score-partwise version="4.0"/>') -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", (
            '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/>'
            '</rootfiles></container>'
        ))
        archive.writestr("score.xml", root_xml)
    return stream.getvalue()


def test_valid_mxl_container_and_score_are_accepted():
    assert validate_mxl(make_mxl(), "ave-verum.mxl") == "score.xml"


@pytest.mark.parametrize("filename", ["score.xml", "score.pdf", "score.zip"])
def test_only_mxl_extension_is_accepted(filename):
    with pytest.raises(ValueError, match="compressed MusicXML"):
        validate_mxl(make_mxl(), filename)


def test_zip_without_container_is_rejected():
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("score.xml", '<score-partwise/>')
    with pytest.raises(ValueError, match="container.xml"):
        validate_mxl(stream.getvalue(), "score.mxl")


def test_non_musicxml_root_is_rejected():
    with pytest.raises(ValueError, match="not a MusicXML score"):
        validate_mxl(make_mxl("<html/>"), "score.mxl")


def test_path_traversal_inside_archive_is_rejected():
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("META-INF/container.xml", (
            '<container><rootfiles><rootfile full-path="../score.xml"/></rootfiles></container>'
        ))
        archive.writestr("../score.xml", "<score-partwise/>")
    with pytest.raises(ValueError, match="Unsafe path"):
        validate_mxl(stream.getvalue(), "score.mxl")


def test_database_migrations_are_repeatable(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
    )
    initialise_database(settings)
    initialise_database(settings)
    import sqlite3

    with sqlite3.connect(settings.database_path) as conn:
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"works", "resources", "files", "creation_drafts", "editor_source_tokens", "library_items", "collections", "collection_items", "oidc_states"} <= tables
        applied = conn.execute("SELECT COUNT(*) FROM chorus_schema_migrations").fetchone()[0]
        assert applied == 4


def test_api_health_and_authentication_fail_closed(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
    )
    with TestClient(create_app(settings)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["service"] == "chorus-api"

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "musician@example.org", "password": "not-a-real-password"},
        )
        assert login.status_code == 503

        draft = client.post("/api/v1/drafts", json={"title": "Ave verum"})
        assert draft.status_code == 401


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
            if method == "POST" and path == "/auth/login":
                return FakeAuthResponse(200, {
                    "access_token": "token-user-1",
                    "refresh_token": "refresh-user-1",
                    "user_id": "user-1",
                    "roles": ["user"],
                    "email_verified": True,
                })
            if method == "GET" and path == "/auth/me":
                profile = profiles.get(token)
                return FakeAuthResponse(200, profile) if profile else FakeAuthResponse(401, {})
            if method == "POST" and path == "/auth/onboarding":
                profile = profiles[token]
                profile["onboarding"]["required"] = False
                return FakeAuthResponse(200, profile)
            if method == "POST" and path == "/auth/logout":
                return FakeAuthResponse(200, {"message": "sesión cerrada"})
            if method == "GET" and path == "/auth/legal/current":
                return FakeAuthResponse(200, {
                    "terms_version": "2026-10-01",
                    "privacy_version": "2026-10-01",
                    "terms_url": "/terms",
                    "privacy_url": "/privacy",
                })
            return FakeAuthResponse(404, {})

    monkeypatch.setattr("app.main.httpx.Client", FakeAuthClient)


def test_login_delegates_to_osap_auth_and_uses_auth_user_id_as_owner(tmp_path, monkeypatch):
    profile = {
        "user_id": "user-1", "roles": ["user"], "email_verified": True, "status": "active",
        "onboarding": {"required": False},
    }
    other_profile = {
        "user_id": "user-2", "roles": ["user"], "email_verified": True, "status": "active",
        "onboarding": {"required": False},
    }
    profiles = {"token-user-1": profile, "token-user-2": other_profile}
    settings = Settings(
        auth_base_url="https://auth.test",
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
        secure_cookies=False,
    )
    with TestClient(create_app(settings)) as client:
        install_fake_auth(monkeypatch, profiles)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "musician@example.org", "password": "example-password"},
        )
        assert login.status_code == 200
        assert login.json()["access_token"] == "token-user-1"
        assert "chorus_refresh" in login.cookies

        created = client.post(
            "/api/v1/drafts",
            headers={"Authorization": "Bearer token-user-1"},
            json={"title": "Ave verum"},
        )
        assert created.status_code == 201
        draft_id = created.json()["id"]

        denied = client.get(
            f"/api/v1/drafts/{draft_id}",
            headers={"Authorization": "Bearer token-user-2"},
        )
        assert denied.status_code == 404


def test_onboarding_is_required_before_creating_drafts(tmp_path, monkeypatch):
    profile = {
        "user_id": "pending-user", "roles": ["user"], "email_verified": True, "status": "active",
        "onboarding": {"required": True},
    }
    profiles = {"token-user-1": profile}
    settings = Settings(
        auth_base_url="https://auth.test",
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
        secure_cookies=False,
    )
    with TestClient(create_app(settings)) as client:
        install_fake_auth(monkeypatch, profiles)
        headers = {"Authorization": "Bearer token-user-1"}
        blocked = client.post("/api/v1/drafts", headers=headers, json={"title": "Ave verum"})
        assert blocked.status_code == 403
        assert blocked.json()["detail"]["code"] == "ONBOARDING_REQUIRED"

        completed = client.post(
            "/api/v1/auth/onboarding",
            headers=headers,
            json={
                "nickname": "musician",
                "terms_version": "2026-10-01",
                "privacy_version": "2026-10-01",
            },
        )
        assert completed.status_code == 200

        allowed = client.post("/api/v1/drafts", headers=headers, json={"title": "Ave verum"})
        assert allowed.status_code == 201
