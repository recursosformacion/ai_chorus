from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.config import Settings
from app.db import connect as db_connect
from app.main import create_app, initialise_database, validate_mxl
from fastapi.testclient import TestClient


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


# True unit tests (no database needed)
@pytest.mark.unit
def test_valid_mxl_container_and_score_are_accepted():
    assert validate_mxl(make_mxl(), "ave-verum.mxl") == "score.xml"


@pytest.mark.unit
@pytest.mark.parametrize("filename", ["score.xml", "score.pdf", "score.zip"])
def test_only_mxl_extension_is_accepted(filename):
    with pytest.raises(ValueError, match="compressed MusicXML"):
        validate_mxl(make_mxl(), filename)


@pytest.mark.unit
def test_zip_without_container_is_rejected():
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("score.xml", '<score-partwise/>')
    with pytest.raises(ValueError, match="container.xml"):
        validate_mxl(stream.getvalue(), "score.mxl")


@pytest.mark.unit
def test_non_musicxml_root_is_rejected():
    with pytest.raises(ValueError, match="not a MusicXML score"):
        validate_mxl(make_mxl("<html/>"), "score.mxl")


@pytest.mark.unit
def test_path_traversal_inside_archive_is_rejected():
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("META-INF/container.xml", (
            '<container><rootfiles><rootfile full-path="../score.xml"/></rootfiles></container>'
        ))
        archive.writestr("../score.xml", "<score-partwise/>")
    with pytest.raises(ValueError, match="Unsafe path"):
        validate_mxl(stream.getvalue(), "score.mxl")


# Tests that need a database
@pytest.mark.db
def test_api_health_and_authentication_fail_closed(settings):
    # Use settings without auth_base_url to test missing auth config
    settings_no_auth = Settings(
        auth_base_url="",
        osap_api_base_url="http://osap.test",
        editor_base_url="http://editor.test",
        editor_origin="http://editor.test",
        public_base_url="http://chorus.test",
        database_url=settings.database_url,
        storage_root=settings.storage_root,
        cors_origins=settings.cors_origins,
        max_upload_bytes=settings.max_upload_bytes,
        source_token_ttl_seconds=settings.source_token_ttl_seconds,
        oidc_issuer=settings.oidc_issuer,
        oidc_authorize_url=settings.oidc_authorize_url,
        oidc_token_url=settings.oidc_token_url,
        oidc_client_id=settings.oidc_client_id,
        oidc_client_secret=settings.oidc_client_secret,
        oidc_redirect_uri=settings.oidc_redirect_uri,
        oidc_scope=settings.oidc_scope,
        auth_timeout_seconds=settings.auth_timeout_seconds,
        osap_timeout_seconds=settings.osap_timeout_seconds,
        secure_cookies=settings.secure_cookies,
    )
    with TestClient(create_app(settings_no_auth)) as client:
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


@pytest.mark.db
def test_login_delegates_to_osap_auth_and_uses_auth_user_id_as_owner(settings, monkeypatch):
    profile = {
        "user_id": "user-1", "roles": ["user"], "email_verified": True, "status": "active",
        "onboarding": {"required": False},
    }
    other_profile = {
        "user_id": "user-2", "roles": ["user"], "email_verified": True, "status": "active",
        "onboarding": {"required": False},
    }
    profiles = {"token-user-1": profile, "token-user-2": other_profile}
    install_fake_auth(monkeypatch, profiles)
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


@pytest.mark.db
def test_onboarding_is_required_before_creating_drafts(settings, monkeypatch):
    profile = {
        "user_id": "pending-user", "roles": ["user"], "email_verified": True, "status": "active",
        "onboarding": {"required": True},
    }
    profiles = {"token-user-1": profile}
    install_fake_auth(monkeypatch, profiles)
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


@pytest.mark.migrations
def test_database_migrations_are_repeatable_mariadb(migration_settings):
    """Test que las migraciones MySQL son idempotentes en MariaDB real."""
    initialise_database(migration_settings)
    initialise_database(migration_settings)
    from app.db import _get_table_names

    with db_connect(migration_settings) as conn:
        tables = set(_get_table_names(conn))
        required = {
            "works", "resources", "files", "creation_drafts", "editor_source_tokens",
            "library_items", "collections", "collection_items", "oidc_states",
            "groups", "group_members", "events", "event_groups", "event_rsvps",
            "entity_leads", "messages", "event_targets", "message_recipients",
            "group_sections", "group_articles", "group_article_media",
            "chorus_schema_migrations",
        }
        assert required <= tables
        applied = conn.execute("SELECT COUNT(*) AS cnt FROM chorus_schema_migrations").fetchone()["cnt"]
        # 001_schema.sql + 004-007 + 016 + 017 = 7 migraciones
        assert applied == 7