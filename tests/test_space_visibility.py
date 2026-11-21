"""Visibilidad de espacios y espacio general único por grupo (§4 y §5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect as db_connect
from app.main import create_app


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


# --------------------------------------------------------------------------
# §4 Visibilidad
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_space_list_visibility_rules(integration_settings: Settings, monkeypatch):
    """owner_sub sólo da visibilidad en espacios personales."""
    profiles = {
        "token-mgr": _profile("vis-mgr"),
        "token-mem": _profile("vis-mem"),
        "token-out": _profile("vis-out"),
        "token-admin": _profile("vis-admin", roles=["admin"]),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        mem = {"Authorization": "Bearer token-mem"}
        out = {"Authorization": "Bearer token-out"}
        adm = {"Authorization": "Bearer token-admin"}

        # Grupo con espacio general y un proyecto
        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Vis"}).json()
        group_id, join_code = grp["id"], grp["join_code"]

        general = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "group", "group_id": group_id, "name": "General"},
        ).json()
        project = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "project", "group_id": group_id, "name": "Proyecto"},
        ).json()

        # owner_sub es NULL en espacios no personales
        assert general["owner_sub"] is None
        assert project["owner_sub"] is None

        # El manager ve sus espacios (membresía)
        mgr_ids = [s["id"] for s in client.get("/api/v1/spaces", headers=mgr).json()]
        assert general["id"] in mgr_ids and project["id"] in mgr_ids

        # El outsider no ve nada del grupo
        out_ids = [s["id"] for s in client.get("/api/v1/spaces", headers=out).json()]
        assert general["id"] not in out_ids and project["id"] not in out_ids

        # Un espacio personal es visible sólo para su dueño
        personal = client.post(
            "/api/v1/spaces", headers=out,
            json={"space_type": "personal", "name": "Solo mío"},
        ).json()
        assert personal["owner_sub"] == "vis-out"
        assert personal["id"] in [s["id"] for s in client.get("/api/v1/spaces", headers=out).json()]
        assert personal["id"] not in [s["id"] for s in client.get("/api/v1/spaces", headers=mem).json()]

        # El admin conserva privilegios administrativos
        adm_ids = [s["id"] for s in client.get("/api/v1/spaces", headers=adm).json()]
        assert general["id"] in adm_ids


@pytest.mark.integration
def test_access_revoked_after_leaving_group(integration_settings: Settings, monkeypatch):
    """Quien deja de ser miembro deja de ver el espacio (listado y acceso directo)."""
    profiles = {
        "token-mgr": _profile("rev-mgr"),
        "token-mem": _profile("rev-mem"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        mem = {"Authorization": "Bearer token-mem"}

        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Rev"}).json()
        group_id, join_code = grp["id"], grp["join_code"]
        assert client.post("/api/v1/groups/join", headers=mem,
                           json={"code": join_code}).status_code == 200

        space = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "group", "group_id": group_id, "name": "General"},
        ).json()
        space_id = space["id"]
        work_id = client.post(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=mgr,
            json={"title": "Privado"},
        ).json()["id"]

        # Mientras es miembro: ve el espacio y puede consultarlo
        assert space_id in [s["id"] for s in client.get("/api/v1/spaces", headers=mem).json()]
        assert client.get(f"/api/v1/spaces/{space_id}", headers=mem).status_code == 200
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=mem
        ).status_code == 200
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}", headers=mem
        ).status_code == 200

        # El manager lo expulsa del grupo
        member_row = client.get(
            f"/api/v1/groups/{group_id}/members", headers=mgr
        ).json()
        sub = next(m["user_sub"] for m in member_row if m["user_sub"] == "rev-mem")
        assert client.delete(
            f"/api/v1/groups/{group_id}/members/{sub}", headers=mgr
        ).status_code in (200, 204)

        # Revocación: ni listado ni acceso directo
        assert space_id not in [s["id"] for s in client.get("/api/v1/spaces", headers=mem).json()]
        assert client.get(f"/api/v1/spaces/{space_id}", headers=mem).status_code == 403
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=mem
        ).status_code == 403
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}", headers=mem
        ).status_code == 403
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/items", headers=mem
        ).status_code == 403
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files", headers=mem
        ).status_code == 403
        # Y tampoco puede modificar
        assert client.patch(
            f"/api/v1/spaces/{space_id}", headers=mem, json={"name": "hack"}
        ).status_code == 403


@pytest.mark.integration
def test_creator_loses_group_space_access_if_no_longer_manager(
    integration_settings: Settings, monkeypatch
):
    """Ser creador del espacio no conserva acceso si deja de ser manager."""
    profiles = {
        "token-a": _profile("cre-a"),
        "token-b": _profile("cre-b"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        a = {"Authorization": "Bearer token-a"}
        b = {"Authorization": "Bearer token-b"}

        grp = client.post("/api/v1/groups", headers=a, json={"name": "Grupo Creador"}).json()
        group_id, join_code = grp["id"], grp["join_code"]

        # 'a' crea el espacio; luego cede la gestión a 'b' creando otro grupo
        space_id = client.post(
            "/api/v1/spaces", headers=a,
            json={"space_type": "group", "group_id": group_id, "name": "General"},
        ).json()["id"]

        # 'a' deja de ser manager (el manager pasa a ser 'b')
        members = client.get(f"/api/v1/groups/{group_id}/members", headers=a).json()
        row_a = next(m for m in members if m["user_sub"] == "cre-a")
        assert client.patch(
            f"/api/v1/groups/{group_id}/members/cre-a", headers=a, json={"role": "member"}
        ).status_code == 200

        # Sigue siendo miembro: conserva consulta, pierde gestión
        assert client.get(f"/api/v1/spaces/{space_id}", headers=a).status_code == 200
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=a
        ).status_code == 200
        assert client.patch(
            f"/api/v1/spaces/{space_id}", headers=a, json={"name": "reescrito"}
        ).status_code == 403
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=a,
            json={"title": "no"},
        ).status_code == 403
        assert row_a["role"] == "manager"


# --------------------------------------------------------------------------
# §5 Espacio general único
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_group_general_space_is_unique_and_not_a_project(
    integration_settings: Settings, monkeypatch
):
    """Un grupo con varios proyectos resuelve siempre el espacio general."""
    profiles = {"token-mgr": _profile("gs-mgr")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}

        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo GS"}).json()
        group_id = grp["id"]

        # Dos proyectos creados ANTES que el espacio general
        p1 = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "project", "group_id": group_id, "name": "Proyecto 1"},
        ).json()
        p2 = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "project", "group_id": group_id, "name": "Proyecto 2"},
        ).json()

        # La ruta antigua crea el espacio general bajo demanda
        w1 = client.post(
            f"/api/v1/groups/{group_id}/preparation-works", headers=mgr,
            json={"title": "A"},
        ).json()
        w2 = client.post(
            f"/api/v1/groups/{group_id}/preparation-works", headers=mgr,
            json={"title": "B"},
        ).json()

        # Ambos trabajos comparten el MISMO espacio general
        assert w1["space_id"] == w2["space_id"]
        general_id = w1["space_id"]
        assert general_id not in (p1["id"], p2["id"])

        # owner_sub del espacio general es NULL (no el id del grupo)
        with db_connect(integration_settings) as conn:
            row = conn.execute(
                "SELECT space_type, owner_sub, group_id FROM spaces WHERE id = ?",
                (general_id,),
            ).fetchone()
            assert row["space_type"] == "group"
            assert row["owner_sub"] is None
            assert row["group_id"] == group_id

            # Un único espacio general para el grupo
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM spaces WHERE group_id = ? AND space_type = 'group'",
                (group_id,),
            ).fetchone()["c"]
            assert count == 1

            # Sigue habiendo dos proyectos
            projects = conn.execute(
                "SELECT COUNT(*) AS c FROM spaces WHERE group_id = ? AND space_type = 'project'",
                (group_id,),
            ).fetchone()["c"]
            assert projects == 2

        # La ruta antigua ve los dos trabajos (mismo espacio general)
        assert len(client.get(
            f"/api/v1/groups/{group_id}/preparation-works", headers=mgr
        ).json()) == 2


@pytest.mark.integration
def test_general_space_creation_is_idempotent(integration_settings: Settings, monkeypatch):
    """Creaciones repetidas no generan espacios generales duplicados."""
    profiles = {"token-mgr": _profile("idem-mgr")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Idem"}).json()
        group_id = grp["id"]

        space_ids = set()
        for i in range(6):
            r = client.post(
                f"/api/v1/groups/{group_id}/preparation-works", headers=mgr,
                json={"title": f"T{i}"},
            )
            assert r.status_code == 201, r.text
            space_ids.add(r.json()["space_id"])

        assert len(space_ids) == 1, f"Se crearon varios espacios generales: {space_ids}"

        with db_connect(integration_settings) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM spaces WHERE group_id = ? AND space_type = 'group'",
                (group_id,),
            ).fetchone()["c"]
            assert count == 1


@pytest.mark.integration
def test_db_rejects_second_general_space(integration_settings: Settings, monkeypatch):
    """El índice único impide un segundo espacio general a nivel de BD."""
    profiles = {"token-mgr": _profile("uniq-mgr")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Uniq"}).json()
        group_id = grp["id"]
        client.post(f"/api/v1/groups/{group_id}/preparation-works", headers=mgr,
                    json={"title": "inicial"})

        with db_connect(integration_settings) as conn:
            existing = conn.execute(
                "SELECT COUNT(*) AS c FROM spaces WHERE group_id = ? AND space_type = 'group'",
                (group_id,),
            ).fetchone()["c"]
            assert existing == 1

            raised = False
            try:
                conn.execute(
                    "INSERT INTO spaces "
                    "(id, space_type, owner_sub, group_id, name, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    ("dup-space-1", "group", None, group_id, "Duplicado",
                     "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
                )
                conn.commit()
            except Exception as exc:
                raised = True
                assert "uq_spaces_general_group" in str(exc) or "Duplicate" in str(exc)
            finally:
                conn.rollback()
            assert raised, "La BD debe impedir un segundo espacio general por grupo"


@pytest.mark.integration
def test_personal_space_can_be_created_without_group(integration_settings: Settings, monkeypatch):
    """Un músico independiente no necesita grupo (regla base del modelo)."""
    profiles = {"token-ind": _profile("ind-1")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        h = {"Authorization": "Bearer token-ind"}

        space = client.post("/api/v1/spaces", headers=h,
                            json={"space_type": "personal", "name": "Mi estudio"})
        assert space.status_code == 201, space.text
        body = space.json()
        assert body["space_type"] == "personal"
        assert body["group_id"] is None
        assert body["owner_sub"] == "ind-1"

        with db_connect(integration_settings) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM spaces s "
                "LEFT JOIN groups g ON g.id = s.group_id WHERE s.id = ? AND g.id IS NULL",
                (body["id"],),
            ).fetchone()["c"]
            assert count == 1, "El espacio personal no debe tener grupo"

        # Puede trabajar sin grupo
        work = client.post(
            f"/api/v1/spaces/{body['id']}/preparation-works", headers=h,
            json={"title": "Mi primer programa"},
        )
        assert work.status_code == 201, work.text