"""Activity Log read-only API + permissions + trigger verification."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.config import Settings


def _profile(user_id: str, roles=None):
    return {
        "user_id": user_id,
        "roles": roles if roles is not None else ["user"],
        "email_verified": True,
        "status": "active",
        "onboarding": {"required": False},
        "memberships": [],
    }


def install_fake_auth(monkeypatch, profiles, auth_base_url="https://auth.test"):
    from tests.test_coral_fields import install_fake_auth as base_install
    base_install(monkeypatch, profiles, auth_base_url)


@pytest.mark.integration
def test_activity_log_read_permissions(integration_settings: Settings, monkeypatch):
    """Read-only API: group manager/admin can read group-scoped, admin only for global."""
    profiles = {
        "token-admin": _profile("admin-1", roles=["admin"]),
        "token-manager": _profile("mgr-1"),
        "token-member": _profile("mem-1"),
        "token-outsider": _profile("out-1"),
    }
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    with TestClient(create_app(settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        mem_h = {"Authorization": "Bearer token-member"}
        out_h = {"Authorization": "Bearer token-outsider"}
        adm_h = {"Authorization": "Bearer token-admin"}

        # Manager creates group
        group_response = client.post(
            "/api/v1/groups", headers=mgr_h, json={"name": "Test Activity Log"}
        )
        assert group_response.status_code == 201, group_response.text
        grp = group_response.json()
        group_id = grp["id"]
        join_code = grp["join_code"]

        # Member joins
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": join_code}).status_code == 200

        # Insert test data directly (simulating system-generated logs)
        import uuid
        from app.utils import utcnow
        from app.db import connect as db_connect

        with db_connect(settings) as conn:
            now = utcnow()
            test_run_id = uuid.uuid4().hex[:8]
            for i in range(5):
                conn.execute(
                    "INSERT INTO activity_log (legacy_id, group_id, event_type, actor, from_status, to_status, detail_json, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        f"legacy-evt-{test_run_id}-{i}", group_id, "article_publish" if i % 2 == 0 else "member_role_change",
                        f"user-{i}", "draft" if i % 2 == 0 else "member", "published" if i % 2 == 0 else "manager",
                        '{"note": "test"}', now,
                    ),
                )

        # ===== GROUP-SCOPED LIST =====
        # Manager can list
        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=mgr_h)
        assert r.status_code == 200, r.text
        logs = r.json()
        assert len(logs) == 5
        assert logs[0]["event_type"] in ("article_publish", "member_role_change")

        # Admin can list
        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=adm_h)
        assert r.status_code == 200
        assert len(r.json()) == 5

        # Member CANNOT list (403)
        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=mem_h)
        assert r.status_code == 403

        # Outsider cannot list
        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=out_h)
        assert r.status_code == 403

        # ===== FILTERS =====
        # Filter by event_type
        r = client.get(f"/api/v1/groups/{group_id}/activity-log?event_type=article_publish", headers=mgr_h)
        assert r.status_code == 200
        assert all(l["event_type"] == "article_publish" for l in r.json())

        # Filter by actor
        r = client.get(f"/api/v1/groups/{group_id}/activity-log?actor=user-0", headers=mgr_h)
        assert r.status_code == 200
        assert all(l["actor"] == "user-0" for l in r.json())

        # Filter by date_from/date_to
        r = client.get(f"/api/v1/groups/{group_id}/activity-log?date_from=2020-01-01", headers=mgr_h)
        assert r.status_code == 200

        # Pagination
        r = client.get(f"/api/v1/groups/{group_id}/activity-log?limit=2&offset=0", headers=mgr_h)
        assert r.status_code == 200
        assert len(r.json()) == 2

        # ===== GLOBAL ADMIN LIST =====
        # Admin can list all
        r = client.get("/api/v1/admin/activity-log", headers=adm_h)
        assert r.status_code == 200
        all_logs = r.json()
        assert len(all_logs) >= 5

        # Non-admin cannot access global
        r = client.get("/api/v1/admin/activity-log", headers=mgr_h)
        assert r.status_code == 403

        r = client.get("/api/v1/admin/activity-log", headers=mem_h)
        assert r.status_code == 403

        # Global filters
        r = client.get(f"/api/v1/admin/activity-log?group_id={group_id}", headers=adm_h)
        assert r.status_code == 200
        assert all(l["group_id"] == group_id for l in r.json())

        r = client.get("/api/v1/admin/activity-log?event_type=member_role_change", headers=adm_h)
        assert r.status_code == 200
        assert all(l["event_type"] == "member_role_change" for l in r.json())


@pytest.mark.integration
def test_activity_log_trigger_on_article_publish(integration_settings: Settings, monkeypatch):
    """Verify activity_log entry is created when article is published."""
    profiles = {
        "token-manager": _profile("mgr-1"),
        "token-member": _profile("mem-1"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        mem_h = {"Authorization": "Bearer token-member"}

        # Create group and join
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Trigger Test"}).json()
        group_id = grp["id"]
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": grp["join_code"]}).status_code == 200

        # Create article as manager
        art = client.post(
            f"/api/v1/groups/{group_id}/articles",
            headers=mgr_h,
            json={"title": "Test Article", "summary": "Test", "body": "Content"},
        ).json()
        article_id = art["id"]

        # Check activity log before publish (should be empty or not have publish event)
        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=mgr_h)
        before_count = len(r.json())

        # Publish article
        r = client.post(f"/api/v1/articles/{article_id}/publish", headers=mgr_h, json={})
        assert r.status_code == 200

        # Check activity log after publish
        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=mgr_h)
        after_count = len(r.json())
        logs = r.json()

        # Should have at least one new entry
        assert after_count > before_count

        # Find the publish event
        publish_logs = [l for l in logs if l["event_type"] == "article_publish" and l["article_id"] == article_id]
        assert len(publish_logs) >= 1
        log = publish_logs[0]
        assert log["actor"] == "mgr-1"
        assert log["from_status"] == "draft"
        assert log["to_status"] == "published"
        assert log["group_id"] == group_id


@pytest.mark.integration
def test_activity_log_trigger_on_member_role_change(integration_settings: Settings, monkeypatch):
    """Verify activity_log entry when member role is changed."""
    profiles = {
        "token-manager": _profile("mgr-1"),
        "token-member": _profile("mem-1"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        mem_h = {"Authorization": "Bearer token-member"}

        # Create group and join
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Role Change Trigger"}).json()
        group_id = grp["id"]
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": grp["join_code"]}).status_code == 200

        # Create roles first
        admin_role = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "admin", "code": "president", "name": "President"},
        ).json()

        # Check activity log before role change
        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=mgr_h)
        before_count = len(r.json())

        # Change member role to manager and assign admin role
        r = client.patch(
            f"/api/v1/groups/{group_id}/members/mem-1",
            headers=mgr_h,
            json={"role": "manager", "admin_role_id": admin_role["id"]},
        )
        assert r.status_code == 200

        # Check activity log after role change
        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=mgr_h)
        after_count = len(r.json())
        logs = r.json()

        # Should have at least one new entry
        assert after_count > before_count

        # Find the member_role_change event
        role_logs = [l for l in logs if l["event_type"] == "member_role_change" and l["actor"] == "mgr-1"]
        assert len(role_logs) >= 1
        log = role_logs[0]
        assert log["group_id"] == group_id
        assert log["from_status"] in ("member", "active")
        assert log["to_status"] == "manager"


@pytest.mark.integration
def test_activity_log_detail_json(integration_settings: Settings, monkeypatch):
    """Verify detail_json is properly parsed."""
    profiles = {"token-manager": _profile("mgr-1")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "JSON Test"}).json()
        group_id = grp["id"]

        # Insert test data with JSON detail
        import uuid
        from app.utils import utcnow
        from app.db import connect as db_connect

        with db_connect(integration_settings) as conn:
            test_id = uuid.uuid4().hex[:8]
            conn.execute(
                "INSERT INTO activity_log (legacy_id, group_id, event_type, actor, detail_json, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (f"legacy-json-{test_id}", group_id, "test_event", "user-1", '{"key": "value", "num": 42}', utcnow()),
            )

        r = client.get(f"/api/v1/groups/{group_id}/activity-log", headers=mgr_h)
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) == 1
        assert logs[0]["detail_json"] == {"key": "value", "num": 42}
        assert isinstance(logs[0]["detail_json"], dict)