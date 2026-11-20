"""Group Social Links CRUD + permissions."""

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
def test_group_social_links_crud_and_permissions(integration_settings: Settings, monkeypatch):
    """CRUD completo con matriz de permisos admin/manager/member/outsider."""
    profiles = {
        "token-admin": _profile("admin-1", roles=["admin"]),
        "token-manager": _profile("mgr-1"),
        "token-member": _profile("mem-1"),
        "token-outsider": _profile("out-1"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        mem_h = {"Authorization": "Bearer token-member"}
        out_h = {"Authorization": "Bearer token-outsider"}
        adm_h = {"Authorization": "Bearer token-admin"}

        # Manager creates group
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Test Social Links"}).json()
        group_id = grp["id"]
        join_code = grp["join_code"]

        # Member joins
        assert client.post("/api/v1/groups/join", headers=mem_h, json={"code": join_code}).status_code == 200

        # ===== CREATE =====
        # Manager can create
        r = client.post(
            f"/api/v1/groups/{group_id}/social-links",
            headers=mgr_h,
            json={"kind": "instagram", "label": "Instagram", "url": "https://instagram.com/test", "position": 1},
        )
        assert r.status_code == 201, r.text
        link1 = r.json()
        assert link1["kind"] == "instagram"
        assert link1["label"] == "Instagram"
        assert link1["position"] == 1
        link1_id = link1["id"]

        # Manager can create website link
        r = client.post(
            f"/api/v1/groups/{group_id}/social-links",
            headers=mgr_h,
            json={"kind": "website", "url": "https://example.org"},
        )
        assert r.status_code == 201
        link2 = r.json()
        assert link2["kind"] == "website"
        assert link2["label"] is None

        # Member cannot create
        r = client.post(
            f"/api/v1/groups/{group_id}/social-links",
            headers=mem_h,
            json={"kind": "facebook", "url": "https://facebook.com/test"},
        )
        assert r.status_code == 403

        # Outsider cannot create
        r = client.post(
            f"/api/v1/groups/{group_id}/social-links",
            headers=out_h,
            json={"kind": "facebook", "url": "https://facebook.com/test"},
        )
        assert r.status_code == 403

        # Admin can create
        r = client.post(
            f"/api/v1/groups/{group_id}/social-links",
            headers=adm_h,
            json={"kind": "youtube", "url": "https://youtube.com/test"},
        )
        assert r.status_code == 201

        # ===== READ =====
        # Member can list
        r = client.get(f"/api/v1/groups/{group_id}/social-links", headers=mem_h)
        assert r.status_code == 200
        links = r.json()
        assert len(links) == 3
        kinds = {l["kind"] for l in links}
        assert kinds == {"instagram", "website", "youtube"}

        # Outsider cannot list
        r = client.get(f"/api/v1/groups/{group_id}/social-links", headers=out_h)
        assert r.status_code == 403

        # Order by position
        assert links[0]["position"] <= links[1]["position"]

        # ===== UPDATE =====
        # Manager can update
        r = client.patch(
            f"/api/v1/groups/{group_id}/social-links/{link1_id}",
            headers=mgr_h,
            json={"label": "IG Updated", "position": 10},
        )
        assert r.status_code == 200, r.text
        assert r.json()["label"] == "IG Updated"
        assert r.json()["position"] == 10

        # Member cannot update
        r = client.patch(
            f"/api/v1/groups/{group_id}/social-links/{link1_id}",
            headers=mem_h,
            json={"url": "https://hacked.com"},
        )
        assert r.status_code == 403

        # Outsider cannot update
        r = client.patch(
            f"/api/v1/groups/{group_id}/social-links/{link1_id}",
            headers=out_h,
            json={"url": "https://hacked.com"},
        )
        assert r.status_code == 403

        # Admin can update
        r = client.patch(
            f"/api/v1/groups/{group_id}/social-links/{link1_id}",
            headers=adm_h,
            json={"kind": "other"},
        )
        assert r.status_code == 200
        assert r.json()["kind"] == "other"

        # ===== DELETE =====
        # Manager can delete
        r = client.delete(f"/api/v1/groups/{group_id}/social-links/{link1_id}", headers=mgr_h)
        assert r.status_code == 200

        # Outsider cannot delete
        r = client.delete(f"/api/v1/groups/{group_id}/social-links/{link2['id']}", headers=out_h)
        assert r.status_code == 403


@pytest.mark.integration
def test_group_social_links_kind_validation(integration_settings: Settings, monkeypatch):
    """Validate allowed kind values."""
    profiles = {"token-manager": _profile("mgr-1")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr_h = {"Authorization": "Bearer token-manager"}
        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Kind Validation"}).json()
        group_id = grp["id"]

        # Valid kinds
        for kind in ["instagram", "facebook", "twitter", "youtube", "website", "other"]:
            r = client.post(
                f"/api/v1/groups/{group_id}/social-links",
                headers=mgr_h,
                json={"kind": kind, "url": f"https://{kind}.com/test"},
            )
            assert r.status_code == 201, f"Failed for {kind}: {r.text}"

        # Invalid kind
        r = client.post(
            f"/api/v1/groups/{group_id}/social-links",
            headers=mgr_h,
            json={"kind": "tiktok", "url": "https://tiktok.com/test"},
        )
        assert r.status_code == 422  # Pydantic validation error