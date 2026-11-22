"""Mantenimiento administrativo de grupos y miembros.

Cubre los ocho puntos de verificación:

1. Los grupos mostrados son los de Chorus.
2. Los tres catálogos se cargan al seleccionar el grupo.
3. Un administrador global incorpora usuarios como miembro ordinario.
4. Un administrador global no puede conceder permisos de gestor.
5. Un gestor autorizado sí puede conceder esos permisos desde Chorus.
6. No se pueden asignar cargos, roles o secciones de otro grupo.
7. Las operaciones usan la identidad real de osap-auth.
8. Los cambios persisten al volver a consultar.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect as db_connect
from app.main import create_app
from tests.m2m_fakes import RecordingIdentityClient, install_identity

def _uid(name: str) -> str:
    """UUID determinista a partir de un nombre legible (los ids de Auth son UUID)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"chorus-test:{name}"))



ADMIN = "admin-1"
MGR = "mgr-1"
MEMBER = "member-1"
OUTSIDER = "outsider-1"


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


def _seed_catalogs(settings: Settings, group_id: str) -> dict:
    """Crea secciones y roles del grupo y devuelve sus ids."""
    now = "2026-01-01 00:00:00"
    suffix = group_id[:8]
    section_id = f"sec-{suffix}"
    admin_role_id = f"ar-{suffix}"
    musical_role_id = f"mr-{suffix}"
    with db_connect(settings) as conn:
        conn.execute(
            "INSERT INTO group_sections (id, group_id, code, name, scope, active, "
            "sort_order, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (section_id, group_id, "soprano", "Soprano", "section", 1, 1, now, now),
        )
        conn.execute(
            "INSERT INTO group_roles (id, legacy_id, group_id, scope, code, name, parent_id, "
            "active, sort_order, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (admin_role_id, f"lg-{suffix}-ar", group_id, "admin", "secretary",
             "Secretario/a", None, 1, 1, now, now),
        )
        conn.execute(
            "INSERT INTO group_roles (id, legacy_id, group_id, scope, code, name, parent_id, "
            "active, sort_order, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (musical_role_id, f"lg-{suffix}-mr", group_id, "musical", "director",
             "Director", None, 1, 1, now, now),
        )
        conn.commit()
    return {
        "section_id": section_id,
        "admin_role_id": admin_role_id,
        "musical_role_id": musical_role_id,
    }


@pytest.fixture
def ctx(integration_settings: Settings, monkeypatch):
    """Dos grupos con catálogos, un administrador global y Auth simulado."""
    profiles = {
        "token-admin": _profile(ADMIN, roles=["admin"]),
        "token-mgr": _profile(MGR),
        "token-member": _profile(MEMBER),
        "token-outsider": _profile(OUTSIDER),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    # osap-auth resuelve los nombres públicos de los destinatarios de alta.
    # Se instala antes de crear la app porque create_app construye el cliente.
    directory = {
        _uid("nuevo-usuario"): "Usuario Nuevo",
        _uid("quiere-ser-gestor"): "Quiere Ser Gestor",
        _uid("otro-gestor"): "Otro Gestor",
        _uid("futuro-gestor"): "Futuro Gestor",
        _uid("seccion-ajena"): "Seccion Ajena",
        _uid("rol-ajeno"): "Rol Ajeno",
        _uid("cargo-ajeno"): "Cargo Ajeno",
        _uid("id-falso"): "Id Falso",
        _uid("identidad-real"): "Identidad Real",
        _uid("persistente"): "Persistente",
        "colado": "Colado",
    }
    identity = RecordingIdentityClient(directory)
    install_identity(monkeypatch, identity)

    client = TestClient(create_app(integration_settings))
    admin = {"Authorization": "Bearer token-admin"}
    mgr = {"Authorization": "Bearer token-mgr"}
    member = {"Authorization": "Bearer token-member"}
    outsider = {"Authorization": "Bearer token-outsider"}

    g1 = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Uno"}).json()
    g2 = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Dos"}).json()
    cat1 = _seed_catalogs(integration_settings, g1["id"])
    cat2 = _seed_catalogs(integration_settings, g2["id"])

    data = {
        "client": client, "admin": admin, "mgr": mgr, "member": member,
        "outsider": outsider,
        "g1": g1["id"], "g2": g2["id"],
        "join1": g1["join_code"],
        "cat1": cat1, "cat2": cat2,
        "identity": identity,
    }
    try:
        yield data
    finally:
        client.close()


# --------------------------------------------------------------------------
# 1. Los grupos mostrados son los de Chorus
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_admin_groups_are_chorus_groups(ctx):
    client, admin = ctx["client"], ctx["admin"]

    listed = client.get("/api/v1/admin/groups", headers=admin)
    assert listed.status_code == 200, listed.text
    ids = {group["id"] for group in listed.json()}
    assert ctx["g1"] in ids and ctx["g2"] in ids

    # Cada grupo listado existe realmente en la tabla groups de Chorus
    with db_connect_from_ctx(ctx) as conn:
        for group in listed.json():
            row = conn.execute(
                "SELECT name FROM groups WHERE id = ?", (group["id"],)
            ).fetchone()
            assert row is not None, "Los grupos listados deben ser de Chorus"
            assert row["name"] == group["name"]

    # Sólo un administrador puede usar el mantenimiento
    assert client.get("/api/v1/admin/groups", headers=ctx["mgr"]).status_code == 403
    assert client.get("/api/v1/admin/groups", headers=ctx["outsider"]).status_code == 403


def db_connect_from_ctx(ctx):
    """Conexión a la BD de pruebas (misma carga que usa la aplicación)."""
    return db_connect(Settings.load())


# --------------------------------------------------------------------------
# 2. Los tres catálogos se cargan al seleccionar el grupo
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_catalogs_are_loaded_per_group(ctx):
    client, admin = ctx["client"], ctx["admin"]

    r1 = client.get(f"/api/v1/admin/groups/{ctx['g1']}/catalog", headers=admin)
    assert r1.status_code == 200, r1.text
    cat1 = r1.json()
    assert cat1["group_id"] == ctx["g1"]
    assert [s["id"] for s in cat1["sections"]] == [ctx["cat1"]["section_id"]]
    assert [r["id"] for r in cat1["admin_roles"]] == [ctx["cat1"]["admin_role_id"]]
    assert [r["id"] for r in cat1["musical_roles"]] == [ctx["cat1"]["musical_role_id"]]

    # Los catálogos son distintos por grupo
    r2 = client.get(f"/api/v1/admin/groups/{ctx['g2']}/catalog", headers=admin)
    assert r2.status_code == 200, r2.text
    cat2 = r2.json()
    assert [s["id"] for s in cat2["sections"]] == [ctx["cat2"]["section_id"]]
    assert cat1["sections"] != cat2["sections"]

    # No se mezclan: los ids del grupo 1 no aparecen en el catálogo del grupo 2
    ids2 = {s["id"] for s in cat2["sections"]}
    ids2 |= {r["id"] for r in cat2["admin_roles"]}
    ids2 |= {r["id"] for r in cat2["musical_roles"]}
    assert ctx["cat1"]["section_id"] not in ids2

    # Catálogo de un grupo inexistente
    assert client.get(
        "/api/v1/admin/groups/no-existe/catalog", headers=admin
    ).status_code == 404


# --------------------------------------------------------------------------
# 3. El administrador global incorpora como miembro ordinario
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_global_admin_onboards_ordinary_member(ctx):
    client, admin = ctx["client"], ctx["admin"]

    r = client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={
            "user_sub": _uid("nuevo-usuario"),
            "display_name": "Usuario Nuevo",
            "admin_role_id": ctx["cat1"]["admin_role_id"],
            "musical_role_id": ctx["cat1"]["musical_role_id"],
            "section_id": ctx["cat1"]["section_id"],
        },
    )
    assert r.status_code == 201, r.text
    member = r.json()
    # Rol de miembro ordinario, nunca gestor
    assert member["role"] == "member"
    assert member["status"] == "active"
    assert member["admin_role_id"] == ctx["cat1"]["admin_role_id"]
    assert member["musical_role_id"] == ctx["cat1"]["musical_role_id"]
    assert member["section_id"] == ctx["cat1"]["section_id"]

    # Persiste y se refleja al volver a consultar
    listed = client.get(f"/api/v1/admin/groups/{ctx['g1']}/members", headers=admin).json()
    found = next(m for m in listed if m["user_sub"] == _uid("nuevo-usuario"))
    assert found["role"] == "member"
    assert found["status"] == "active"
    assert found["section_id"] == ctx["cat1"]["section_id"]
    assert found["granted_by"] == ADMIN

    detail = client.get(f"/api/v1/admin/groups/{ctx['g1']}", headers=admin).json()
    assert detail["member_count"] >= 2
    assert detail["manager_count"] == 1, "El alta administrativa no crea gestores"

    # Queda auditado
    with db_connect_from_ctx(ctx) as conn:
        log = conn.execute(
            "SELECT actor, event_type, detail_json FROM activity_log "
            "WHERE group_id = ? AND event_type = 'member_added' ORDER BY created_at DESC",
            (ctx["g1"],),
        ).fetchone()
        assert log is not None
        assert log["actor"] == ADMIN
        assert "admin_onboarding" in (log["detail_json"] or "")


# --------------------------------------------------------------------------
# 4. El administrador global no puede conceder permisos de gestor
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_global_admin_cannot_grant_manager(ctx):
    client, admin = ctx["client"], ctx["admin"]

    # Alta administrativa: el modelo no expone el campo role
    r = client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={"user_sub": _uid("quiere-ser-gestor"), "role": "manager"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "member", "El campo role se ignora en el alta administrativa"

    # Ruta histórica de alta: el administrador global no puede dar rol manager
    r2 = client.post(
        f"/api/v1/groups/{ctx['g1']}/members",
        headers=admin,
        json={"user_sub": _uid("otro-gestor"), "role": "manager"},
    )
    assert r2.status_code == 403, r2.text

    # Modificación: el administrador global no puede ascender a gestor
    r3 = client.patch(
        f"/api/v1/groups/{ctx['g1']}/members/{_uid('quiere-ser-gestor')}",
        headers=admin,
        json={"role": "manager"},
    )
    assert r3.status_code == 403, r3.text

    # Ni retirar la responsabilidad de gestor
    r4 = client.patch(
        f"/api/v1/groups/{ctx['g1']}/members/{MGR}",
        headers=admin,
        json={"role": "member"},
    )
    assert r4.status_code == 403, r4.text

    # El rol de la BD no ha cambiado
    with db_connect_from_ctx(ctx) as conn:
        row = conn.execute(
            "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ?",
            (ctx["g1"], _uid("quiere-ser-gestor")),
        ).fetchone()
        assert row["role"] == "member"


# --------------------------------------------------------------------------
# 5. Un gestor autorizado sí puede conceder esos permisos
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_group_manager_can_grant_manager(ctx):
    client, mgr, admin = ctx["client"], ctx["mgr"], ctx["admin"]

    client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={"user_sub": _uid("futuro-gestor")},
    )

    # El gestor del grupo concede la responsabilidad
    r = client.patch(
        f"/api/v1/groups/{ctx['g1']}/members/{_uid("futuro-gestor")}",
        headers=mgr,
        json={"role": "manager"},
    )
    assert r.status_code == 200, r.text

    listed = client.get(f"/api/v1/groups/{ctx['g1']}/members", headers=mgr).json()
    found = next(m for m in listed if m["user_sub"] == _uid("futuro-gestor"))
    assert found["role"] == "manager"

    # Queda auditado el cambio de rol
    with db_connect_from_ctx(ctx) as conn:
        log = conn.execute(
            "SELECT actor, event_type, detail_json FROM activity_log "
            "WHERE group_id = ? AND event_type = 'member_role_change' ORDER BY created_at DESC",
            (ctx["g1"],),
        ).fetchone()
        assert log is not None
        assert log["actor"] == MGR
        assert "manager" in (log["detail_json"] or "")

    # Y también puede retirarla
    r2 = client.patch(
        f"/api/v1/groups/{ctx['g1']}/members/{_uid("futuro-gestor")}",
        headers=mgr,
        json={"role": "member"},
    )
    assert r2.status_code == 200, r2.text


# --------------------------------------------------------------------------
# 6. No se pueden asignar catálogos de otro grupo
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_catalogs_from_another_group_are_rejected(ctx):
    client, admin = ctx["client"], ctx["admin"]

    # Sección del grupo 2 en el grupo 1
    r = client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={"user_sub": _uid("seccion-ajena"), "section_id": ctx["cat2"]["section_id"]},
    )
    assert r.status_code == 400, r.text
    assert "Section not found in this group" in r.text

    # Rol musical del grupo 2 en el grupo 1
    r2 = client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={"user_sub": _uid("rol-ajeno"), "musical_role_id": ctx["cat2"]["musical_role_id"]},
    )
    assert r2.status_code == 400, r2.text
    assert "Musical role not found in this group" in r2.text

    # Cargo del grupo 2 en el grupo 1
    r3 = client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={"user_sub": _uid("cargo-ajeno"), "admin_role_id": ctx["cat2"]["admin_role_id"]},
    )
    assert r3.status_code == 400, r3.text
    assert "Admin role not found in this group" in r3.text

    # Un id inexistente también se rechaza
    r4 = client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={"user_sub": _uid("id-falso"), "section_id": "no-existe"},
    )
    assert r4.status_code == 400, r4.text

    # Nada se ha insertado
    with db_connect_from_ctx(ctx) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?",
            (ctx["g1"],),
        ).fetchone()["c"]
        assert count == 1, "Sólo debe existir el gestor inicial"


# --------------------------------------------------------------------------
# 7. Identidad real de osap-auth
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_operations_use_real_osap_auth_identity(ctx):
    """El user_id procede de /auth/me, no de un parámetro de la petición."""
    client, admin = ctx["client"], ctx["admin"]

    r = client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={"user_sub": _uid("identidad-real")},
    )
    assert r.status_code == 201, r.text

    with db_connect_from_ctx(ctx) as conn:
        row = conn.execute(
            "SELECT user_sub, granted_by FROM group_members "
            "WHERE group_id = ? AND user_sub = ?",
            (ctx["g1"], _uid("identidad-real")),
        ).fetchone()
        # El alta la realiza el admin autenticado por osap-auth
        assert row["granted_by"] == ADMIN

    # Un token inválido no permite operar
    assert client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers={"Authorization": "Bearer token-invalido"},
        json={"user_sub": _uid("intruso")},
    ).status_code == 401

    # Un usuario sin rol de admin no puede usar el mantenimiento
    assert client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=ctx["member"],
        json={"user_sub": _uid("colado")},
    ).status_code == 403


# --------------------------------------------------------------------------
# 8. Los cambios persisten y se reflejan al volver a consultar
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_changes_persist_on_reload(ctx):
    client, admin, mgr = ctx["client"], ctx["admin"], ctx["mgr"]

    client.post(
        f"/api/v1/admin/groups/{ctx['g1']}/members",
        headers=admin,
        json={
            "user_sub": _uid("persistente"),
            "display_name": "Nombre Inicial",
            "section_id": ctx["cat1"]["section_id"],
        },
    )

    # El gestor ajusta cargo, rol musical y sección (campos de mantenimiento)
    r = client.patch(
        f"/api/v1/groups/{ctx['g1']}/members/{_uid("persistente")}",
        headers=mgr,
        json={
            "admin_role_id": ctx["cat1"]["admin_role_id"],
            "musical_role_id": ctx["cat1"]["musical_role_id"],
            "section_id": ctx["cat1"]["section_id"],
            "status": "active",
        },
    )
    assert r.status_code == 200, r.text

    # Nueva consulta: los cambios se conservan
    listed = client.get(
        f"/api/v1/admin/groups/{ctx['g1']}/members", headers=admin
    ).json()
    found = next(m for m in listed if m["user_sub"] == _uid("persistente"))
    # El nombre procede de Auth, no de un registro local
    assert found["name"] == "Persistente"
    assert found["identity_verified"] is True
    # display_name queda como instantanea historica no verificada
    assert found["legacy_display_name"] == "Persistente"
    assert found["admin_role_id"] == ctx["cat1"]["admin_role_id"]
    assert found["musical_role_id"] == ctx["cat1"]["musical_role_id"]
    assert found["section_id"] == ctx["cat1"]["section_id"]
    assert found["status"] == "active"

    # También en la base de datos
    with db_connect_from_ctx(ctx) as conn:
        row = conn.execute(
            "SELECT role, status, admin_role_id, musical_role_id, section_id, display_name "
            "FROM group_members WHERE group_id = ? AND user_sub = ?",
            (ctx["g1"], _uid("persistente")),
        ).fetchone()
        assert row["role"] == "member"
        assert row["status"] == "active"
        # El alta guarda el nombre canonico de Auth como instantanea
        assert row["display_name"] == "Persistente"

    # Baja y alta posterior
    assert client.delete(
        f"/api/v1/groups/{ctx['g1']}/members/{_uid("persistente")}", headers=mgr
    ).status_code == 200
    after = client.get(
        f"/api/v1/admin/groups/{ctx['g1']}/members", headers=admin
    ).json()
    found = next(m for m in after if m["user_sub"] == _uid("persistente"))
    assert found["status"] == "removed"

    # El filtro por estado funciona
    only_active = client.get(
        f"/api/v1/admin/groups/{ctx['g1']}/members?status=active", headers=admin
    ).json()
    assert all(m["status"] == "active" for m in only_active)
    assert "persistente" not in {m["user_sub"] for m in only_active}