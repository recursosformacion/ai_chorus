"""Preparation Works CRUD + permissions."""

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


def _profile_with_roles(user_id: str, roles=None):
    p = _profile(user_id)
    if roles:
        p["roles"] = roles
    return p


@pytest.mark.integration
def test_preparation_works_crud_and_permissions(integration_settings: Settings, monkeypatch):
    """CRUD completo con matriz de permisos admin/manager/member/outsider."""
    profiles = {
        "token-admin": _profile("admin-1", roles=["admin"]),
        "token-manager": _profile("mgr-1"),
        "token-member": _profile("mem-1"),
        "token-outsider": _profile("out-1"),
    }

    profiles["token-admin"] = _profile_with_roles("admin-1", roles=["admin"])
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        mem_h = {"Authorization": "Bearer token-member"}
        out_h = {"Authorization": "Bearer token-outsider"}
        adm_h = {"Authorization": "Bearer token-admin"}

        # Manager creates group
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Test Prep Works"}).json()
        group_id = grp["id"]
        join_code = grp["join_code"]

        # Member joins
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": join_code}).status_code == 200

        # ===== CREATE =====
        # Manager can create
        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mgr_h,
            json={"title": "Ave verum", "composer": "Mozart", "destination_type": "repertoire"},
        )
        assert r.status_code == 201, r.text
        work = r.json()
        assert work["title"] == "Ave verum"
        assert work["composer"] == "Mozart"
        assert work["destination_type"] == "repertoire"
        assert work["status"] == "preparing"
        assert work["folder_path"].startswith("preparation/")
        work_id = work["id"]

        # Member cannot create
        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mem_h,
            json={"title": "Unauthorized", "destination_type": "repertoire"},
        )
        assert r.status_code == 403

        # Outsider cannot create
        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=out_h,
            json={"title": "Unauthorized", "destination_type": "repertoire"},
        )
        assert r.status_code == 403

        # Admin can create
        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=adm_h,
            json={"title": "Admin Work", "destination_type": "repertoire"},
        )
        assert r.status_code == 201

        # ===== READ =====
        # Member can list
        r = client.get(f"/api/v1/groups/{group_id}/preparation-works", headers=mem_h)
        assert r.status_code == 200
        works = r.json()
        assert len(works) >= 1
        titles = {w["title"] for w in works}
        assert "Ave verum" in titles

        # Outsider cannot list
        r = client.get(f"/api/v1/groups/{group_id}/preparation-works", headers=out_h)
        assert r.status_code == 403

        # Filter by status
        r = client.get(f"/api/v1/groups/{group_id}/preparation-works?status=preparing", headers=mem_h)
        assert r.status_code == 200
        assert all(w["status"] == "preparing" for w in r.json())

        # Filter by destination_type
        r = client.get(f"/api/v1/groups/{group_id}/preparation-works?destination_type=repertoire", headers=mem_h)
        assert r.status_code == 200
        assert all(w["destination_type"] == "repertoire" for w in r.json())

        # ===== UPDATE =====
        # Manager can update
        r = client.patch(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}",
            headers=mgr_h,
            json={"composer": "W. A. Mozart", "status": "ready"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["composer"] == "W. A. Mozart"
        assert r.json()["status"] == "ready"

        # Member cannot update
        r = client.patch(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}",
            headers=mem_h,
            json={"title": "Hacked"},
        )
        assert r.status_code == 403

        # Outsider cannot update
        r = client.patch(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}",
            headers=out_h,
            json={"title": "Hacked"},
        )
        assert r.status_code == 403

        # Admin can update
        r = client.patch(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}",
            headers=adm_h,
            json={"notes": "Updated by admin"},
        )
        assert r.status_code == 200

        # ===== DELETE =====
        # Create a work to delete
        to_delete = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mgr_h,
            json={"title": "To Delete", "destination_type": "repertoire"},
        ).json()

        # Manager can delete
        r = client.delete(f"/api/v1/groups/{group_id}/preparation-works/{to_delete['id']}", headers=mgr_h)
        assert r.status_code == 200

        # Outsider cannot delete
        r = client.delete(f"/api/v1/groups/{group_id}/preparation-works/{work_id}", headers=out_h)
        assert r.status_code == 403


@pytest.mark.integration
def test_preparation_works_destination_program(integration_settings: Settings, monkeypatch):
    """Test creating works with destination_type=program."""
    profiles = {"token-manager": _profile("mgr-1")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Program Test"}).json()
        group_id = grp["id"]

        # Create work with program destination
        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mgr_h,
            json={
                "title": "Concierto de Navidad",
                "destination_type": "program",
                "event_name": "Navidad 2024",
                "event_date": "2024-12-20",
            },
        )
        assert r.status_code == 201, r.text
        work = r.json()
        assert work["destination_type"] == "program"
        assert work["event_name"] == "Navidad 2024"
        assert work["event_date"] == "2024-12-20"

        # Update to repertoire
        r = client.patch(
            f"/api/v1/groups/{group_id}/preparation-works/{work['id']}",
            headers=mgr_h,
            json={"destination_type": "repertoire", "event_name": None, "event_date": None},
        )
        assert r.status_code == 200
        assert r.json()["destination_type"] == "repertoire"
        assert r.json()["event_name"] is None


@pytest.mark.integration
def test_preparation_works_files(integration_settings: Settings, monkeypatch):
    """Test file upload/download for preparation works."""
    profiles = {"token-manager": _profile("mgr-1")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Files Test"}).json()
        group_id = grp["id"]

        # Create work
        work = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mgr_h,
            json={"title": "Work with files", "destination_type": "repertoire"},
        ).json()
        work_id = work["id"]

        # Upload files
        files = [
            ("files", ("score.pdf", b"%PDF test content", "application/pdf")),
            ("files", ("part.mxl", b"<?xml version='1.0'?>", "application/vnd.recordare.musicxml")),
        ]
        parts = [
            {"part_label": "Soprano", "purpose": "part"},
            {"part_label": "Director", "purpose": "score"},
        ]
        import json as json_std
        form_data = {"parts": json_std.dumps(parts)}
        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files",
            headers=mgr_h,
            files=files,
            data=form_data,
        )
        assert r.status_code == 201, r.text
        result = r.json()
        assert result["work_id"] == work_id
        assert len(result["files"]) == 2
        assert result["files"][0]["part_label"] == "Soprano"
        assert result["files"][0]["purpose"] == "part"
        assert result["files"][1]["part_label"] == "Director"
        assert result["files"][1]["purpose"] == "score"

        # List files
        r = client.get(f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files", headers=mgr_h)
        assert r.status_code == 200
        listed = r.json()
        assert len(listed) == 2

        # Download file
        file_name = listed[0]["name"]
        r = client.get(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}/download",
            headers=mgr_h,
        )
        assert r.status_code == 200

        # Delete file
        r = client.delete(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}",
            headers=mgr_h,
        )
        assert r.status_code == 200

        # Member cannot upload
        profiles["token-member"] = _profile("mem-1")
        install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)
        mem_h = {"Authorization": "Bearer token-member"}
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": grp["join_code"]}).status_code == 200

        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files",
            headers=mem_h,
            files=[("files", ("test.pdf", b"test", "application/pdf"))],
            data={"parts": "[]"},
        )
        assert r.status_code == 403


@pytest.mark.integration
def test_preparation_works_musical_director_permission(integration_settings: Settings, monkeypatch):
    """Test that user with musical_role_id (scope=musical) can manage preparation works."""
    profiles = {
        "token-manager": _profile("mgr-1"),
        "token-member": _profile("mem-1"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        mem_h = {"Authorization": "Bearer token-member"}

        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Musical Director Test"}).json()
        group_id = grp["id"]
        join_code = grp["join_code"]

        # Member joins
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": join_code}).status_code == 200

        # Create musical role
        musical_role = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "musical", "code": "director", "name": "Director Musical"},
        ).json()
        musical_role_id = musical_role["id"]

        # Assign musical role to member
        r = client.patch(
            f"/api/v1/groups/{group_id}/members/mem-1",
            headers=mgr_h,
            json={"musical_role_id": musical_role_id},
        )
        assert r.status_code == 200

        # Now member (with musical role) can create preparation work
        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mem_h,
            json={"title": "Director's Work", "destination_type": "repertoire"},
        )
        assert r.status_code == 201, r.text
        work = r.json()
        assert work["title"] == "Director's Work"

        # Member can also update
        r = client.patch(
            f"/api/v1/groups/{group_id}/preparation-works/{work['id']}",
            headers=mem_h,
            json={"notes": "Updated by director"},
        )
        assert r.status_code == 200

        # Member can delete
        r = client.delete(
            f"/api/v1/groups/{group_id}/preparation-works/{work['id']}",
            headers=mem_h,
        )
        assert r.status_code == 200


@pytest.mark.integration
def test_preparation_works_other_musical_role_no_permission(integration_settings: Settings, monkeypatch):
    """Test that user with musical role that is NOT director (e.g., soprano) cannot manage."""
    profiles = {
        "token-manager": _profile("mgr-1"),
        "token-member": _profile("mem-1"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        mem_h = {"Authorization": "Bearer token-member"}

        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Other Musical Role Test"}).json()
        group_id = grp["id"]
        join_code = grp["join_code"]

        # Member joins
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": join_code}).status_code == 200

        # Create a non-director musical role (e.g., soprano)
        soprano_role = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "musical", "code": "soprano", "name": "Soprano"},
        ).json()
        soprano_role_id = soprano_role["id"]

        # Assign soprano role to member
        r = client.patch(
            f"/api/v1/groups/{group_id}/members/mem-1",
            headers=mgr_h,
            json={"musical_role_id": soprano_role_id},
        )
        assert r.status_code == 200

        # Member with soprano role CANNOT create preparation work
        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mem_h,
            json={"title": "Unauthorized", "destination_type": "repertoire"},
        )
        assert r.status_code == 403


@pytest.mark.integration
def test_preparation_works_cross_group_isolation(integration_settings: Settings, monkeypatch):
    """Test that permissions in one group don't grant access to another."""
    profiles = {
        "token-manager": _profile("mgr-1"),
        "token-manager2": _profile("mgr-2"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr1_h = {"Authorization": "Bearer token-manager"}
        mgr2_h = {"Authorization": "Bearer token-manager2"}

        # Manager 1 creates group
        grp1 = client.post("/api/v1/groups", headers=mgr1_h, json={"name": "Group 1"}).json()
        group1_id = grp1["id"]

        # Manager 2 creates group
        grp2 = client.post("/api/v1/groups", headers=mgr2_h, json={"name": "Group 2"}).json()
        group2_id = grp2["id"]

        # Manager 1 creates work in group 1
        work = client.post(
            f"/api/v1/groups/{group1_id}/preparation-works",
            headers=mgr1_h,
            json={"title": "Group 1 Work", "destination_type": "repertoire"},
        ).json()
        work_id = work["id"]

        # Manager 2 cannot access group 1's work
        r = client.get(f"/api/v1/groups/{group1_id}/preparation-works", headers=mgr2_h)
        assert r.status_code == 403

        r = client.get(f"/api/v1/groups/{group1_id}/preparation-works/{work_id}", headers=mgr2_h)
        assert r.status_code == 403

        r = client.patch(
            f"/api/v1/groups/{group1_id}/preparation-works/{work_id}",
            headers=mgr2_h,
            json={"title": "Hacked"},
        )
        assert r.status_code == 403

        r = client.delete(f"/api/v1/groups/{group1_id}/preparation-works/{work_id}", headers=mgr2_h)
        assert r.status_code == 403

        # Manager 2 can create work in group 2
        r = client.post(
            f"/api/v1/groups/{group2_id}/preparation-works",
            headers=mgr2_h,
            json={"title": "Group 2 Work", "destination_type": "repertoire"},
        )
        assert r.status_code == 201