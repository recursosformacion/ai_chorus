"""Legacy Uploads read-only API + permissions."""

from __future__ import annotations

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
def test_legacy_uploads_read_permissions(integration_settings: Settings, monkeypatch):
    """Read-only API: admin and group manager can read, member/outsider cannot."""
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
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Test Legacy Uploads"}).json()
        group_id = grp["id"]
        join_code = grp["join_code"]

        # Member joins
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": join_code}).status_code == 200

        # Insert test data directly (simulating migration data)
        import uuid
from dataclasses import replace
        from app.utils import utcnow
        from app.db import connect as db_connect

        with db_connect(settings) as conn:
            # Clean ALL legacy_uploads for this group to ensure clean state
            conn.execute("DELETE FROM legacy_uploads WHERE group_id = ?", (group_id,))
            import uuid
            from app.utils import utcnow
            base_file_id = 900000 + int(uuid.uuid4().int % 1000)
            for i in range(3):
                # Use different timestamps to ensure consistent ordering
                ts = utcnow()
                conn.execute(
                    "INSERT INTO legacy_uploads (id, legacy_file_id, group_id, mime_type, size_bytes, created_by, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (uuid.uuid4().hex, base_file_id + i, group_id, f"application/pdf", 1024 * (i + 1), f"user-{i}", ts),
                )
                # Small delay to ensure different timestamps
                import time
                time.sleep(0.01)

        # ===== LIST (group-scoped) =====
        # Manager can list
        r = client.get(f"/api/v1/groups/{group_id}/legacy-uploads", headers=mgr_h)
        assert r.status_code == 200, r.text
        uploads = r.json()
        assert len(uploads) == 3
        assert uploads[0]["mime_type"] == "application/pdf"
        # Verify order by created_at DESC (last inserted first)
        assert uploads[0]["legacy_file_id"] == base_file_id + 2
        assert uploads[1]["legacy_file_id"] == base_file_id + 1
        assert uploads[2]["legacy_file_id"] == base_file_id

        # Admin can list
        r = client.get(f"/api/v1/groups/{group_id}/legacy-uploads", headers=adm_h)
        assert r.status_code == 200
        assert len(r.json()) == 3

        # Member CANNOT list (403 - only managers/admins)
        r = client.get(f"/api/v1/groups/{group_id}/legacy-uploads", headers=mem_h)
        assert r.status_code == 403

        # Outsider cannot list
        r = client.get(f"/api/v1/groups/{group_id}/legacy-uploads", headers=out_h)
        assert r.status_code == 403

        # ===== FILTERS =====
        # Filter by mime_type
        r = client.get(f"/api/v1/groups/{group_id}/legacy-uploads?mime_type=application/pdf", headers=mgr_h)
        assert r.status_code == 200
        assert len(r.json()) == 3

        # Pagination
        r = client.get(f"/api/v1/groups/{group_id}/legacy-uploads?limit=2&offset=0", headers=mgr_h)
        assert r.status_code == 200
        assert len(r.json()) == 2

        r = client.get(f"/api/v1/groups/{group_id}/legacy-uploads?limit=2&offset=2", headers=mgr_h)
        assert r.status_code == 200
        assert len(r.json()) == 1

        # ===== GET SINGLE =====
        upload_id = uploads[0]["id"]

        # Manager can get single
        r = client.get(f"/api/v1/legacy-uploads/{upload_id}", headers=mgr_h)
        assert r.status_code == 200
        assert r.json()["id"] == upload_id

        # Admin can get single
        r = client.get(f"/api/v1/legacy-uploads/{upload_id}", headers=adm_h)
        assert r.status_code == 200

        # Member cannot get single
        r = client.get(f"/api/v1/legacy-uploads/{upload_id}", headers=mem_h)
        assert r.status_code == 403

        # Outsider cannot get single
        r = client.get(f"/api/v1/legacy-uploads/{upload_id}", headers=out_h)
        assert r.status_code == 403

        # ===== NON-EXISTENT =====
        r = client.get(f"/api/v1/legacy-uploads/{uuid.uuid4().hex}", headers=mgr_h)
        assert r.status_code == 404

        # ===== CROSS-GROUP ISOLATION =====
        # Manager creates another group
        grp2 = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Group 2"}).json()
        group_id2 = grp2["id"]

        with db_connect(settings) as conn:
            conn.execute(
                "INSERT INTO legacy_uploads (id, legacy_file_id, group_id, mime_type, size_bytes, created_by, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, int(uuid.uuid4().int % 1000000), group_id2, "image/png", 2048, "user-x", utcnow()),
            )

        # Manager of group1 cannot see group2's uploads via group-scoped endpoint
        r = client.get(f"/api/v1/groups/{group_id}/legacy-uploads", headers=mgr_h)
        assert r.status_code == 200
        assert len(r.json()) == 3  # Only group1's uploads

        # But admin can see all via single endpoint
        r = client.get(f"/api/v1/legacy-uploads/{upload_id}", headers=adm_h)
        assert r.status_code == 200