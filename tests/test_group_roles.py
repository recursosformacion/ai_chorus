"""Group Roles CRUD + permissions."""

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
def test_group_roles_crud_and_permissions(integration_settings: Settings, monkeypatch):
    """CRUD completo con matriz de permisos admin/manager/member/outsider."""
    profiles = {
        "token-admin": _profile("admin-1", roles=["admin"]),
        "token-manager": _profile("mgr-1"),
        "token-member": _profile("mem-1"),
        "token-outsider": _profile("out-1"),
    }

    def _profile_with_roles(user_id: str, roles=None):
        p = _profile(user_id)
        if roles:
            p["roles"] = roles
        return p

    profiles["token-admin"] = _profile_with_roles("admin-1", roles=["admin"])
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    with TestClient(create_app(settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        mem_h = {"Authorization": "Bearer token-member"}
        out_h = {"Authorization": "Bearer token-outsider"}
        adm_h = {"Authorization": "Bearer token-admin"}

        # Manager creates group
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Test Group Roles"}).json()
        group_id = grp["id"]
        join_code = grp["join_code"]

        # Member joins
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": join_code}).status_code == 200

        # ===== CREATE =====
        # Manager can create admin role
        r = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "admin", "code": "president", "name": "Presidency"},
        )
        assert r.status_code == 201, r.text
        admin_role = r.json()
        assert admin_role["scope"] == "admin"
        assert admin_role["code"] == "president"
        assert admin_role["name"] == "Presidency"
        assert admin_role["active"] is True
        admin_role_id = admin_role["id"]

        # Manager can create musical role
        r = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "musical", "code": "soprano", "name": "Soprano"},
        )
        assert r.status_code == 201, r.text
        musical_role = r.json()
        assert musical_role["scope"] == "musical"
        musical_role_id = musical_role["id"]

        # Member cannot create
        r = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mem_h,
            json={"scope": "musical", "code": "alto", "name": "Alto"},
        )
        assert r.status_code == 403

        # Outsider cannot create
        r = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=out_h,
            json={"scope": "musical", "code": "alto", "name": "Alto"},
        )
        assert r.status_code == 403

        # Admin can create
        r = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=adm_h,
            json={"scope": "admin", "code": "secretary", "name": "Secretary"},
        )
        assert r.status_code == 201

        # ===== READ =====
        # Member can list
        r = client.get(f"/api/v1/groups/{group_id}/roles", headers=mem_h)
        assert r.status_code == 200
        roles = r.json()
        assert len(roles) == 3
        codes = {r["code"] for r in roles}
        assert codes == {"president", "soprano", "secretary"}

        # Outsider cannot list
        r = client.get(f"/api/v1/groups/{group_id}/roles", headers=out_h)
        assert r.status_code == 403

        # Filter by scope
        r = client.get(f"/api/v1/groups/{group_id}/roles?scope=admin", headers=mem_h)
        assert r.status_code == 200
        roles = r.json()
        assert all(r["scope"] == "admin" for r in roles)

        # Filter by active
        r = client.get(f"/api/v1/groups/{group_id}/roles?active=true", headers=mem_h)
        assert r.status_code == 200
        assert all(r["active"] is True for r in r.json())

        # ===== UPDATE =====
        # Manager can update
        r = client.patch(
            f"/api/v1/groups/{group_id}/roles/{admin_role_id}",
            headers=mgr_h,
            json={"name": "Presidency Updated", "sort_order": 5},
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Presidency Updated"
        assert r.json()["sort_order"] == 5

        # Member cannot update
        r = client.patch(
            f"/api/v1/groups/{group_id}/roles/{admin_role_id}",
            headers=mem_h,
            json={"name": "Hacked"},
        )
        assert r.status_code == 403

        # Outsider cannot update
        r = client.patch(
            f"/api/v1/groups/{group_id}/roles/{admin_role_id}",
            headers=out_h,
            json={"name": "Hacked"},
        )
        assert r.status_code == 403

        # Admin can update
        r = client.patch(
            f"/api/v1/groups/{group_id}/roles/{admin_role_id}",
            headers=adm_h,
            json={"active": False},
        )
        assert r.status_code == 200
        assert r.json()["active"] is False

        # ===== DELETE =====
        # Manager can delete (but not if referenced)
        r = client.delete(f"/api/v1/groups/{group_id}/roles/{musical_role_id}", headers=mgr_h)
        assert r.status_code == 200

        # Assign admin_role to member to make it referenced
        r = client.patch(
            f"/api/v1/groups/{group_id}/members/mem-1",
            headers=mgr_h,
            json={"admin_role_id": admin_role_id},
        )
        assert r.status_code == 200

        # Cannot delete referenced role
        r = client.delete(f"/api/v1/groups/{group_id}/roles/{admin_role_id}", headers=mgr_h)
        assert r.status_code == 400
        assert "assigned to members" in r.json()["detail"].lower()

        # Outsider cannot delete
        r = client.delete(f"/api/v1/groups/{group_id}/roles/{admin_role_id}", headers=out_h)
        assert r.status_code == 403


@pytest.mark.integration
def test_group_roles_hierarchy(integration_settings: Settings, monkeypatch):
    """Parent-child hierarchy in group_roles."""
    profiles = {"token-manager": _profile("mgr-1")}
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    with TestClient(create_app(settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Hierarchy Group"}).json()
        group_id = grp["id"]

        # Create parent
        parent = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "admin", "code": "board", "name": "Board"},
        ).json()
        parent_id = parent["id"]

        # Create child
        child = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "admin", "code": "vp", "name": "Vice President", "parent_id": parent_id},
        ).json()
        assert child["parent_id"] == parent_id

        # Cannot set self as parent
        r = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "admin", "code": "self", "name": "Self", "parent_id": child["id"]},
        )
        # This should work (creating new role with parent=child)
        assert r.status_code == 201

        # Cannot update to self as parent
        r = client.patch(
            f"/api/v1/groups/{group_id}/roles/{child['id']}",
            headers=mgr_h,
            json={"parent_id": child["id"]},
        )
        assert r.status_code == 400
        assert "own parent" in r.json()["detail"].lower()

        # Cannot delete parent with children
        r = client.delete(f"/api/v1/groups/{group_id}/roles/{parent_id}", headers=mgr_h)
        assert r.status_code == 400
        assert "child roles" in r.json()["detail"].lower()


@pytest.mark.integration
def test_group_roles_scope_validation(integration_settings: Settings, monkeypatch):
    """Admin role must have scope=admin, musical role must have scope=musical."""
    profiles = {"token-manager": _profile("mgr-1")}
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    with TestClient(create_app(settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Scope Validation"}).json()
        group_id = grp["id"]

        # Create roles
        admin_role = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "admin", "code": "pres", "name": "President"},
        ).json()
        musical_role = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr_h,
            json={"scope": "musical", "code": "cond", "name": "Conductor"},
        ).json()

        # Join a member
        mem_h = {"Authorization": "Bearer token-member"}
        profiles["token-member"] = _profile("mem-1")
        settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": grp["join_code"]}).status_code == 200

        # Assign admin role with musical scope -> should fail
        r = client.patch(
            f"/api/v1/groups/{group_id}/members/mem-1",
            headers=mgr_h,
            json={"admin_role_id": musical_role["id"]},
        )
        assert r.status_code == 400
        assert "scope 'admin'" in r.json()["detail"]

        # Assign musical role with admin scope -> should fail
        r = client.patch(
            f"/api/v1/groups/{group_id}/members/mem-1",
            headers=mgr_h,
            json={"musical_role_id": admin_role["id"]},
        )
        assert r.status_code == 400
        assert "scope 'musical'" in r.json()["detail"]

        # Correct assignments work
        r = client.patch(
            f"/api/v1/groups/{group_id}/members/mem-1",
            headers=mgr_h,
            json={"admin_role_id": admin_role["id"], "musical_role_id": musical_role["id"]},
        )
        assert r.status_code == 200

        # Verify in members list
        r = client.get(f"/api/v1/groups/{group_id}/members", headers=mgr_h)
        assert r.status_code == 200
        members = r.json()
        mem = next(m for m in members if m["user_sub"] == "mem-1")
        assert mem["admin_role"]["code"] == "pres"
        assert mem["musical_role"]["code"] == "cond"