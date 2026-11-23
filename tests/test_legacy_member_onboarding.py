"""Alta ordinaria de miembros: la identidad del destinatario se verifica en Auth.

Complementa `test_identity_m2m.py` cubriendo el endpoint histórico
``POST /api/v1/groups/{group_id}/members``, que antes insertaba el
``user_sub`` sin consultar el proveedor de identidad.
"""
from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect as db_connect
from app.identity import IdentityClient
from app.main import create_app
from tests.m2m_fakes import (
    FakeM2MTransport,
    RecordingIdentityClient,
    install_identity,
)

ADMIN = "legacy-admin"
MGR = "legacy-mgr"
MEMBER = "legacy-member"

EXISTENTE = "33333333-3333-3333-3333-333333333333"
INEXISTENTE = "44444444-4444-4444-4444-444444444444"

DIRECTORIO = {EXISTENTE: "Nombre Canonico Auth"}


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


def _count(conn, sql, params):
    return int(conn.execute(sql, params).fetchone()["c"])


@pytest.fixture
def env(integration_settings: Settings, monkeypatch):
    """Grupo con gestor y cliente de identidad simulado."""
    profiles = {
        "token-admin": _profile(ADMIN, roles=["admin"]),
        "token-mgr": _profile(MGR),
        "token-member": _profile(MEMBER),
    }
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    identity = RecordingIdentityClient(DIRECTORIO)
    install_identity(monkeypatch, identity)

    client = TestClient(create_app(settings))
    group = client.post(
        "/api/v1/groups",
        headers={"Authorization": "Bearer token-mgr"},
        json={"name": "Grupo Alta Historica"},
    ).json()

    class Env:
        def __init__(self):
            self.client = client
            self.group_id = group["id"]
            self.identity = identity
            self.admin = {"Authorization": "Bearer token-admin"}
            self.mgr = {"Authorization": "Bearer token-mgr"}
            self.member = {"Authorization": "Bearer token-member"}
            self.url = f"/api/v1/groups/{group['id']}/members"

        def set_identity(self, new_client):
            self.identity = new_client
            client.app.state.identity_client = new_client
            return new_client

        def members(self):
            with db_connect(Settings.load()) as conn:
                return conn.execute(
                    "SELECT * FROM group_members WHERE group_id = ?",
                    (self.group_id,),
                ).fetchall()

    try:
        yield Env()
    finally:
        client.close()


# --------------------------------------------------------------------------
# 1. Gestor incorpora una identidad existente: éxito
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_manager_can_add_verified_identity(env):
    response = env.client.post(
        env.url, headers=env.mgr, json={"user_sub": EXISTENTE}
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "member"
    assert response.json()["status"] == "active"

    # Se consultó al proveedor de identidad para el destinatario
    assert [EXISTENTE] in env.identity.calls


# --------------------------------------------------------------------------
# 2. Identidad inexistente: rechazo y ninguna fila
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_manager_cannot_add_unknown_identity(env):
    before = len(env.members())

    response = env.client.post(
        env.url, headers=env.mgr, json={"user_sub": INEXISTENTE}
    )
    assert response.status_code == 400, response.text
    assert "Unknown user_id" in response.text
    assert len(env.members()) == before, "No debe insertarse ninguna fila"


@pytest.mark.integration
def test_unknown_identity_does_not_write_activity_log(env):
    with db_connect(Settings.load()) as conn:
        before = _count(
            conn,
            "SELECT COUNT(*) AS c FROM activity_log WHERE group_id = ? "
            "AND event_type = 'member_added'",
            (env.group_id,),
        )

    response = env.client.post(
        env.url, headers=env.mgr, json={"user_sub": INEXISTENTE}
    )
    assert response.status_code == 400

    with db_connect(Settings.load()) as conn:
        after = _count(
            conn,
            "SELECT COUNT(*) AS c FROM activity_log WHERE group_id = ? "
            "AND event_type = 'member_added'",
            (env.group_id,),
        )
    assert after == before, "Tampoco debe registrarse actividad"


# --------------------------------------------------------------------------
# 3. Auth no disponible: 503 y ninguna fila
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_unavailable_auth_blocks_legacy_onboarding(env):
    env.set_identity(RecordingIdentityClient({}, available=False))
    before = len(env.members())

    response = env.client.post(
        env.url, headers=env.mgr, json={"user_sub": EXISTENTE}
    )
    assert response.status_code == 503, response.text
    assert len(env.members()) == before


# --------------------------------------------------------------------------
# 4. Se ignora el nombre del cliente y se usa el canónico de Auth
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_client_display_name_is_ignored(env):
    response = env.client.post(
        env.url,
        headers=env.mgr,
        json={"user_sub": EXISTENTE, "display_name": "Nombre Falso"},
    )
    assert response.status_code == 201, response.text

    with db_connect(Settings.load()) as conn:
        row = conn.execute(
            "SELECT display_name FROM group_members WHERE group_id = ? AND user_sub = ?",
            (env.group_id, EXISTENTE),
        ).fetchone()
    assert row["display_name"] == "Nombre Canonico Auth", (
        "El display_name enviado por el gestor no debe usarse como identidad"
    )


# --------------------------------------------------------------------------
# 5. El gestor puede conceder manager al destinatario verificado
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_manager_can_grant_manager_to_verified_user(env):
    created = env.client.post(
        env.url, headers=env.mgr, json={"user_sub": EXISTENTE}
    )
    assert created.status_code == 201, created.text

    promoted = env.client.patch(
        f"{env.url}/{EXISTENTE}", headers=env.mgr, json={"role": "manager"}
    )
    assert promoted.status_code == 200, promoted.text

    with db_connect(Settings.load()) as conn:
        row = conn.execute(
            "SELECT role FROM group_members WHERE group_id = ? AND user_sub = ?",
            (env.group_id, EXISTENTE),
        ).fetchone()
    assert row["role"] == "manager"


def test_manager_can_create_verified_manager_directly(env):
    """El alta histórica permite role=manager si la identidad está verificada."""
    response = env.client.post(
        env.url,
        headers=env.mgr,
        json={"user_sub": EXISTENTE, "role": "manager"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "manager"


# --------------------------------------------------------------------------
# 6. El administrador global sigue sin poder conceder manager
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_global_admin_cannot_grant_manager_in_legacy_endpoint(env):
    response = env.client.post(
        env.url,
        headers=env.admin,
        json={"user_sub": EXISTENTE, "role": "manager"},
    )
    assert response.status_code == 403, response.text

    # Ni siquiera crea la membresía
    assert len(env.members()) == 1, "Sólo debe existir el gestor inicial"


@pytest.mark.integration
def test_global_admin_can_add_ordinary_member_in_legacy_endpoint(env):
    """El admin global sí puede incorporar miembros ordinarios verificados."""
    response = env.client.post(
        env.url, headers=env.admin, json={"user_sub": EXISTENTE}
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "member"


# --------------------------------------------------------------------------
# 7. Un miembro ordinario no puede incorporar personas
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_ordinary_member_cannot_add_people(env):
    env.client.post(env.url, headers=env.mgr, json={"user_sub": EXISTENTE})

    before = len(env.members())
    response = env.client.post(
        env.url, headers=env.member, json={"user_sub": INEXISTENTE}
    )
    assert response.status_code == 403, response.text
    assert len(env.members()) == before

    # La identidad del destinatario ni siquiera se consulta
    assert [INEXISTENTE] not in env.identity.calls


# --------------------------------------------------------------------------
# Extra: resolve_one rechaza mal formados sin llamar a Auth
# --------------------------------------------------------------------------
@pytest.mark.unit
def test_resolve_one_rejects_malformed_without_calling_auth():
    transport = FakeM2MTransport({EXISTENTE: "Nombre"})
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )

    for value in ("", "no-es-uuid", "123", "33333333-3333-3333-3333", None):
        assert client.resolve_one(value) is None

    assert transport.lookup_calls == [], "No debe llamarse a Auth con ids mal formados"
    assert transport.token_calls == [], "No debe emitirse token de servicio"


@pytest.mark.unit
def test_resolve_one_accepts_valid_uuid_and_calls_auth():
    transport = FakeM2MTransport({EXISTENTE: "Nombre Canonico"})
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )

    assert client.resolve_one(EXISTENTE) == "Nombre Canonico"
    assert len(transport.lookup_calls) == 1
    assert transport.lookup_calls[0]["ids"] == [EXISTENTE]


@pytest.mark.unit
def test_resolve_one_uses_real_uuid_format():
    """La prueba no usa identificadores arbitrarios: el contrato exige UUID."""
    value = str(uuid.uuid4())
    transport = FakeM2MTransport({value: "Nombre"})
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )

    assert client.resolve_one(value) == "Nombre"
    uuid.UUID(transport.lookup_calls[0]["ids"][0])