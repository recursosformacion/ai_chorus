"""Artículos de grupo en Chorus."""

from __future__ import annotations

from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from tests.test_agenda import install_fake_auth


def _profile(user_id: str):
    return {
        "user_id": user_id,
        "roles": ["user"],
        "email_verified": True,
        "status": "active",
        "onboarding": {"required": False},
        "memberships": [],
    }


def _settings(tmp_path):
    return Settings(
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
        secure_cookies=False,
        auth_base_url="https://auth.test",
        auth_timeout_seconds=5,
        oidc_issuer="https://auth.test",
        oidc_client_id="chorus-test",
        oidc_client_secret="secret",
        oidc_redirect_uri="http://chorus.test/callback",
        osap_api_base_url="",
    )


def test_group_article_lifecycle(tmp_path, monkeypatch):
    profiles = {"token-manager": _profile("manager-1"), "token-member": _profile("member-1")}
    install_fake_auth(monkeypatch, profiles)
    with TestClient(create_app(_settings(tmp_path))) as client:
        manager = {"Authorization": "Bearer token-manager"}
        group = client.post("/api/v1/groups", headers=manager, json={"name": "Coral Nueva"}).json()
        member_headers = {"Authorization": "Bearer token-member"}
        assert client.post(
            "/api/v1/groups/join", headers=member_headers, json={"code": group["join_code"]}
        ).status_code == 200

        created = client.post(
            f"/api/v1/groups/{group['id']}/articles",
            headers=manager,
            json={
                "title": "Concierto de otoño",
                "summary": "Programa del concierto",
                "body": "Contenido completo",
                "event_date": "2026-10-10",
            },
        )
        assert created.status_code == 201, created.text
        article = created.json()
        assert article["status"] == "draft"
        assert article["can_publish"] is True

        listed = client.get(f"/api/v1/groups/{group['id']}/articles", headers=member_headers)
        assert listed.status_code == 200
        assert listed.json() == []

        published = client.post(
            f"/api/v1/articles/{article['id']}/publish", headers=manager, json={}
        )
        assert published.status_code == 200
        assert published.json()["status"] == "published"
        assert published.json()["publisher_user_id"] == "manager-1"

        visible = client.get(f"/api/v1/groups/{group['id']}/articles", headers=member_headers)
        assert [item["id"] for item in visible.json()] == [article["id"]]
        assert visible.json()[0]["can_edit"] is False

        denied = client.post(
            f"/api/v1/articles/{article['id']}/publish", headers=member_headers, json={}
        )
        assert denied.status_code == 403

        updated = client.patch(
            f"/api/v1/articles/{article['id']}",
            headers=manager,
            json={"title": "Concierto de otoño (actualizado)"},
        )
        assert updated.status_code == 200
        assert updated.json()["title"].endswith("(actualizado)")

def test_local_group_creation_does_not_require_entity(tmp_path, monkeypatch):
    profiles = {"token-user": _profile("user-1")}
    install_fake_auth(monkeypatch, profiles)
    with TestClient(create_app(_settings(tmp_path))) as client:
        created = client.post(
            "/api/v1/groups",
            headers={"Authorization": "Bearer token-user"},
            json={"name": "Coro Autónomo"},
        )
        assert created.status_code == 201, created.text
        group = created.json()
        assert group["entity_id"] == group["id"]
        assert group["role"] == "manager"
        assert group["can_manage"] is True

