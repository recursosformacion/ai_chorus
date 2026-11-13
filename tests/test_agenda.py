"""Agenda de grupo y RSVP binario (Asisto / No asisto)."""

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


def _profile(user_id: str, *, representative: bool = False):
    return {
        "user_id": user_id,
        "roles": ["user"],
        "email_verified": True,
        "status": "active",
        "onboarding": {"required": False},
        "memberships": [
            {
                "entity_id": "entity-1",
                "entity_name": "Coral Aurora",
                "entity_kind": "coral",
                "status": "approved",
                "is_representative": representative,
            }
        ],
    }


def _settings(tmp_path):
    return Settings(
        auth_base_url="https://auth.test",
        database_path=str(tmp_path / "chorus.sqlite3"),
        storage_root=str(tmp_path / "private"),
        secure_cookies=False,
    )


def test_create_group_event_and_rsvp(tmp_path, monkeypatch):
    profiles = {
        "token-rep": _profile("rep-1", representative=True),
        "token-other": _profile("other-1"),
        "token-third": _profile("third-1"),
    }
    install_fake_auth(monkeypatch, profiles)
    with TestClient(create_app(_settings(tmp_path))) as client:
        headers = {"Authorization": "Bearer token-rep"}
        group = client.post(
            "/api/v1/groups",
            headers=headers,
            json={"entity_id": "entity-1", "name": "Coral Aurora"},
        )
        assert group.status_code == 201
        group_id = group.json()["id"]
        join_code = group.json()["join_code"]

        joined = client.post(
            "/api/v1/groups/join",
            headers={"Authorization": "Bearer token-other"},
            json={"code": join_code},
        )
        assert joined.status_code == 200

        event = client.post(
            "/api/v1/events",
            headers=headers,
            json={
                "group_id": group_id,
                "kind": "rehearsal",
                "title": "Ensayo general",
                "starts_at": "2030-01-10T19:30:00+01:00",
                "location": "Sala 2",
            },
        )
        assert event.status_code == 201
        event_id = event.json()["id"]
        assert event.json()["rsvp_required"] is True

        agenda = client.get("/api/v1/agenda", headers=headers).json()
        assert agenda["events"][0]["id"] == event_id
        assert agenda["events"][0]["my_rsvp"] is None

        assert client.post(
            f"/api/v1/events/{event_id}/rsvp",
            headers=headers,
            json={"status": "yes"},
        ).status_code == 200
        agenda = client.get("/api/v1/agenda", headers=headers).json()
        assert agenda["events"][0]["my_rsvp"] == "yes"

        assert client.post(
            f"/api/v1/events/{event_id}/rsvp",
            headers=headers,
            json={"status": "no"},
        ).status_code == 200
        agenda = client.get("/api/v1/agenda", headers=headers).json()
        assert agenda["events"][0]["my_rsvp"] == "no"

        other = client.get(
            "/api/v1/agenda", headers={"Authorization": "Bearer token-other"}
        ).json()
        assert other["events"][0]["id"] == event_id
        assert client.post(
            f"/api/v1/events/{event_id}/rsvp",
            headers={"Authorization": "Bearer token-other"},
            json={"status": "yes"},
        ).status_code == 200

        third = client.get(
            "/api/v1/agenda", headers={"Authorization": "Bearer token-third"}
        ).json()
        assert third["events"] == []
        assert client.post(
            f"/api/v1/events/{event_id}/rsvp",
            headers={"Authorization": "Bearer token-third"},
            json={"status": "yes"},
        ).status_code == 403


def test_note_does_not_take_rsvp(tmp_path, monkeypatch):
    profiles = {"token-rep": _profile("rep-1", representative=True)}
    install_fake_auth(monkeypatch, profiles)
    with TestClient(create_app(_settings(tmp_path))) as client:
        headers = {"Authorization": "Bearer token-rep"}
        group_id = client.post(
            "/api/v1/groups",
            headers=headers,
            json={"entity_id": "entity-1", "name": "Coral Aurora"},
        ).json()["id"]
        event_id = client.post(
            "/api/v1/events",
            headers=headers,
            json={
                "group_id": group_id,
                "kind": "note",
                "title": "Aviso de sala",
                "starts_at": "2030-01-10T19:30:00+01:00",
            },
        ).json()["id"]

        response = client.post(
            f"/api/v1/events/{event_id}/rsvp", headers=headers, json={"status": "yes"}
        )
        assert response.status_code == 400
