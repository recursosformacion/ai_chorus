"""Comunicados internos de Chorus: grupo, administración y personas."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

from tests.test_agenda import _profile, install_fake_auth


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
def test_group_messages_and_recipients(settings, tmp_path, monkeypatch):
    profiles = {
        "token-manager": _profile("manager-1", representative=True),
        "token-member": _profile("member-1"),
        "token-outsider": _profile("outsider-1"),
    }
    install_fake_auth(monkeypatch, profiles)
    with TestClient(create_app(settings)) as client:
        manager = {"Authorization": "Bearer token-manager"}
        member = {"Authorization": "Bearer token-member"}
        outsider = {"Authorization": "Bearer token-outsider"}
        group = client.post(
            "/api/v1/groups",
            headers=manager,
            json={"entity_id": "entity-1", "name": "Coral Aurora"},
        ).json()
        group_id = group["id"]
        client.post(
            "/api/v1/groups/join",
            headers=member,
            json={"code": group["join_code"]},
        )

        members = client.get(f"/api/v1/groups/{group_id}/members", headers=manager)
        assert members.status_code == 200
        assert {row["user_sub"] for row in members.json()} == {"manager-1", "member-1"}

        sent = client.post(
            f"/api/v1/groups/{group_id}/messages",
            headers=manager,
            json={
                "scope": "group",
                "subject": "Ensayo general",
                "body": "Recordad traer la carpeta.",
            },
        )
        assert sent.status_code == 201
        message_id = sent.json()["id"]
        assert sent.json()["recipient_count"] == 2

        inbox = client.get(f"/api/v1/groups/{group_id}/messages", headers=member).json()
        assert inbox[0]["id"] == message_id
        assert inbox[0]["my_read_at"] is None

        assert client.post(f"/api/v1/messages/{message_id}/read", headers=member).status_code == 200
        inbox = client.get(f"/api/v1/groups/{group_id}/messages", headers=member).json()
        assert inbox[0]["my_read_at"] is not None

        assert client.get(f"/api/v1/groups/{group_id}/messages", headers=outsider).json() == []
        assert client.get(f"/api/v1/groups/{group_id}/members", headers=outsider).status_code == 403
        contact = client.post(
            f"/api/v1/groups/{group_id}/messages",
            headers=outsider,
            json={"scope": "managers", "subject": "Contacto", "body": "Hola"},
        )
        assert contact.status_code == 201

        direct = client.post(
            f"/api/v1/groups/{group_id}/messages",
            headers=member,
            json={
                "scope": "users",
                "subject": "Duda de tesitura",
                "body": "¿Puedo cantar la segunda voz?",
                "recipient_subs": ["manager-1"],
            },
        )
        assert direct.status_code == 201
        assert direct.json()["recipient_count"] == 1
        manager_inbox = client.get(
            f"/api/v1/groups/{group_id}/messages", headers=manager
        ).json()
        assert any(row["id"] == direct.json()["id"] for row in manager_inbox)

        managers = client.post(
            f"/api/v1/groups/{group_id}/messages",
            headers=member,
            json={
                "scope": "managers",
                "subject": "Aviso",
                "body": "No podré asistir.",
            },
        )
        assert managers.status_code == 201
        assert managers.json()["recipient_count"] == 1