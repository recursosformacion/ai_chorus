"""Normalización canónica de user_sub en las altas M2M.

Dos representaciones del mismo UUID (minúsculas, mayúsculas, llaves) son la
misma identidad. El valor persistido y comparado debe ser siempre canónico.

Se verifica en los dos endpoints de alta con el mismo comportamiento:
  - POST /api/v1/groups/{group_id}/members          (histórico)
  - POST /api/v1/admin/groups/{group_id}/members    (administrativo)
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect as db_connect
from app.identity import canonical_uuid
from app.main import create_app
from tests.m2m_fakes import RecordingIdentityClient, install_identity

ADMIN = "cccccccc-0000-4000-8000-000000000001"
MGR = "cccccccc-0000-4000-8000-000000000002"

CANONICO = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
MAYUSCULAS = CANONICO.upper()
ENTRE_LLAVES = "{" + MAYUSCULAS + "}"
NOMBRE = "Nombre Canonico"


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


def _directory():
    return {
        CANONICO: NOMBRE,
        MAYUSCULAS: NOMBRE,
        ENTRE_LLAVES: NOMBRE,
    }


@pytest.fixture
def env(integration_settings: Settings, monkeypatch):
    """Grupo con gestor e identidad M2M que reconoce las tres representaciones."""
    profiles = {
        "token-admin": _profile(ADMIN, roles=["admin"]),
        "token-mgr": _profile(MGR),
    }
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    identity = RecordingIdentityClient(_directory())
    install_identity(monkeypatch, identity)

    client = TestClient(create_app(settings))
    group_response = client.post(
        "/api/v1/groups",
        headers={"Authorization": "Bearer token-mgr"},
        json={"name": "Grupo Canonico"},
    )
    assert group_response.status_code == 201, group_response.text
    group = group_response.json()

    class Env:
        def __init__(self):
            self.client = client
            self.group_id = group["id"]
            self.identity = identity
            self.mgr = {"Authorization": "Bearer token-mgr"}
            self.admin = {"Authorization": "Bearer token-admin"}
            self.legacy_url = f"/api/v1/groups/{group['id']}/members"
            self.admin_url = f"/api/v1/admin/groups/{group['id']}/members"

        def rows(self):
            with db_connect(Settings.load()) as conn:
                return conn.execute(
                    "SELECT * FROM group_members WHERE group_id = ?",
                    (self.group_id,),
                ).fetchall()

        def logs(self):
            with db_connect(Settings.load()) as conn:
                return conn.execute(
                    "SELECT * FROM activity_log WHERE group_id = ? "
                    "AND event_type = 'member_added' ORDER BY id",
                    (self.group_id,),
                ).fetchall()

    try:
        yield Env()
    finally:
        client.close()


# Los dos endpoints deben comportarse igual
ENDPOINTS = [
    pytest.param("legacy", id="legacy"),
    pytest.param("admin", id="admin"),
]


def _post(env, kind: str, user_sub: str, **extra):
    url = env.legacy_url if kind == "legacy" else env.admin_url
    headers = env.mgr if kind == "legacy" else env.admin
    return env.client.post(url, headers=headers, json={"user_sub": user_sub, **extra})


# --------------------------------------------------------------------------
# Alta con UUID canónico
# --------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.parametrize("kind", ENDPOINTS)
def test_canonical_uuid_onboarding_succeeds(env, kind):
    response = _post(env, kind, CANONICO)
    assert response.status_code == 201, response.text

    rows = env.rows()
    assert len(rows) == 2, "Gestor inicial + nuevo miembro"
    row = next(r for r in rows if r["user_sub"] == CANONICO)
    assert row["display_name"] == NOMBRE
    assert row["role"] == "member"


# --------------------------------------------------------------------------
# Mayúsculas: misma identidad
# --------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.parametrize("kind", ENDPOINTS)
def test_uppercase_uuid_is_the_same_identity(env, kind):
    response = _post(env, kind, MAYUSCULAS)
    assert response.status_code == 201, response.text

    rows = env.rows()
    row = next(r for r in rows if r["user_sub"] == CANONICO)
    assert row is not None, "Debe persistirse en forma canónica"
    assert not any(r["user_sub"] == MAYUSCULAS for r in rows), (
        "No debe persistirse la forma en mayúsculas"
    )
    assert row["display_name"] == NOMBRE


# --------------------------------------------------------------------------
# Llaves: misma identidad
# --------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.parametrize("kind", ENDPOINTS)
def test_braced_uuid_is_the_same_identity(env, kind):
    response = _post(env, kind, ENTRE_LLAVES)
    assert response.status_code == 201, response.text

    rows = env.rows()
    assert any(r["user_sub"] == CANONICO for r in rows)
    assert not any(r["user_sub"] == ENTRE_LLAVES for r in rows), (
        "No debe persistirse la forma entre llaves"
    )


# --------------------------------------------------------------------------
# Duplicados lógicos: canónico + representación alternativa
# --------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.parametrize("kind", ENDPOINTS)
def test_canonical_then_alternative_is_rejected_409(env, kind):
    first = _post(env, kind, CANONICO)
    assert first.status_code == 201, first.text
    before = len(env.rows())

    second = _post(env, kind, MAYUSCULAS)
    assert second.status_code == 409, second.text
    assert len(env.rows()) == before, "No debe crearse una segunda membresía"

    third = _post(env, kind, ENTRE_LLAVES)
    assert third.status_code == 409, third.text
    assert len(env.rows()) == before


@pytest.mark.integration
@pytest.mark.parametrize("kind", ENDPOINTS)
def test_alternative_then_canonical_is_rejected_409(env, kind):
    first = _post(env, kind, MAYUSCULAS)
    assert first.status_code == 201, first.text
    before = len(env.rows())

    second = _post(env, kind, CANONICO)
    assert second.status_code == 409, second.text
    assert len(env.rows()) == before

    # La membresía quedó en forma canónica
    assert any(r["user_sub"] == CANONICO for r in env.rows())
    assert not any(r["user_sub"] == MAYUSCULAS for r in env.rows())


@pytest.mark.integration
@pytest.mark.parametrize("kind", ENDPOINTS)
def test_braced_then_canonical_is_rejected_409(env, kind):
    assert _post(env, kind, ENTRE_LLAVES).status_code == 201
    before = len(env.rows())

    assert _post(env, kind, CANONICO).status_code == 409
    assert len(env.rows()) == before


# --------------------------------------------------------------------------
# Listado tras alta con representación alternativa
# --------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.parametrize("kind", ENDPOINTS)
def test_listing_after_alternative_onboarding_resolves_identity(env, kind):
    assert _post(env, kind, MAYUSCULAS).status_code == 201

    # Listado ordinario
    listed = env.client.get(
        f"/api/v1/groups/{env.group_id}/members", headers=env.mgr
    )
    assert listed.status_code == 200
    item = next(m for m in listed.json() if m["user_sub"] == CANONICO)
    assert item["identity_verified"] is True
    assert item["name"] == NOMBRE

    # Listado administrativo
    admin_listed = env.client.get(
        f"/api/v1/admin/groups/{env.group_id}/members", headers=env.admin
    )
    assert admin_listed.status_code == 200
    admin_item = next(m for m in admin_listed.json() if m["user_sub"] == CANONICO)
    assert admin_item["identity_verified"] is True
    assert admin_item["name"] == NOMBRE
    assert admin_item["legacy_display_name"] == NOMBRE


# --------------------------------------------------------------------------
# Valor persistido siempre canónico
# --------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.parametrize(
    "kind,representacion",
    [
        ("legacy", CANONICO),
        ("legacy", MAYUSCULAS),
        ("legacy", ENTRE_LLAVES),
        ("admin", CANONICO),
        ("admin", MAYUSCULAS),
        ("admin", ENTRE_LLAVES),
    ],
)
def test_persisted_user_sub_is_always_canonical(env, kind, representacion):
    response = _post(env, kind, representacion)
    assert response.status_code == 201, response.text

    # Respuesta y BD coinciden y son canónicas
    body = response.json()
    assert body["user_sub"] == CANONICO
    assert canonical_uuid(body["user_sub"]) == CANONICO

    for row in env.rows():
        assert row["user_sub"] == canonical_uuid(row["user_sub"]), (
            f"user_sub no canónico persistido: {row['user_sub']}"
        )


# --------------------------------------------------------------------------
# Auditoría con clave canónica
# --------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.parametrize("kind", ENDPOINTS)
def test_activity_log_uses_canonical_subject(env, kind):
    expected_actor = MGR if kind == "legacy" else ADMIN
    assert _post(env, kind, MAYUSCULAS).status_code == 201

    logs = env.logs()
    assert logs, "Debe registrarse la actividad del alta"
    entry = logs[-1]

    assert entry["event_type"] == "member_added"
    # El actor es la identidad autenticada que realiza el alta, no el destinatario
    assert entry["actor"] == expected_actor

    # El sujeto del registro se genera con el UUID canónico del destinatario:
    # aparece en minúsculas y nunca en la representación enviada (mayúsculas)
    assert CANONICO[:8] in entry["legacy_id"], entry["legacy_id"]
    assert MAYUSCULAS[:8] not in entry["legacy_id"], entry["legacy_id"]

    detail = json.loads(entry["detail_json"])
    assert detail["identity_verified_by"] == "osap-auth"
    if kind == "admin":
        assert detail["source"] == "admin_onboarding"


# --------------------------------------------------------------------------
# No se confía en el UUID original después de verificar
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_original_representation_not_reused_after_verification(env):
    """La identidad verificada es la fuente del user_id persistido."""
    env.client.post(
        env.admin_url, headers=env.admin, json={"user_sub": ENTRE_LLAVES}
    )

    # Se consultó Auth con la representación original...
    assert env.identity.calls, "Debe consultarse al proveedor"
    # ...pero lo persistido es canónico
    rows = env.rows()
    assert all(r["user_sub"] == CANONICO for r in rows if r["user_sub"] != MGR)


# --------------------------------------------------------------------------
# Ambos endpoints comparten comportamiento
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_both_endpoints_share_canonical_behaviour(env):
    """Mismo resultado para la misma representación en ambos endpoints."""
    legacy = _post(env, "legacy", MAYUSCULAS)
    assert legacy.status_code == 201
    legacy_body = legacy.json()

    # El segundo endpoint con la forma canónica debe detectar el duplicado
    admin = _post(env, "admin", CANONICO)
    assert admin.status_code == 409

    assert legacy_body["user_sub"] == CANONICO


@pytest.mark.integration
def test_no_logical_duplicates_after_mixed_representations(env):
    """Mezclar representaciones no genera duplicados lógicos."""
    for representacion in (MAYUSCULAS, ENTRE_LLAVES, CANONICO):
        _post(env, "legacy", representacion)

    rows = [r for r in env.rows() if r["user_sub"] != MGR]
    assert len(rows) == 1, f"Debe haber una sola membresía: {[r['user_sub'] for r in rows]}"
    assert rows[0]["user_sub"] == CANONICO

    # Y sin duplicados en la clave primaria lógica (group_id, user_sub)
    with db_connect(Settings.load()) as conn:
        duplicated = conn.execute(
            "SELECT group_id, user_sub, COUNT(*) AS c FROM group_members "
            "GROUP BY group_id, user_sub HAVING c > 1"
        ).fetchall()
    assert duplicated == []


@pytest.mark.unit
def test_canonical_uuid_normalises_all_representations():
    assert canonical_uuid(CANONICO) == CANONICO
    assert canonical_uuid(MAYUSCULAS) == CANONICO
    assert canonical_uuid(ENTRE_LLAVES) == CANONICO
    assert canonical_uuid(str(uuid.UUID(CANONICO))) == CANONICO


@pytest.mark.unit
def test_canonical_uuid_rejects_malformed():
    for bad in ("", "no-uuid", "123", "6666", None):
        with pytest.raises((ValueError, AttributeError, TypeError)):
            canonical_uuid(bad)