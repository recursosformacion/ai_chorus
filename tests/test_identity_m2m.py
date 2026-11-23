"""osap-auth como fuente única de identidad en el mantenimiento de grupos.

Cubre los once puntos exigidos, distinguiendo siempre:

- Identidad del **actor** autenticado (quien opera).
- Identidad del **destinatario** del alta (el usuario que se incorpora).

Las pruebas de contrato M2M usan un transport httpx real (sin red) para
ejercitar la serialización y el parseo reales; las de endpoints usan un
sustituto que registra llamadas.
"""
from __future__ import annotations

import uuid

import pytest
import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect as db_connect
from app.identity import IdentityClient, IdentityUnavailable
from app.main import create_app
from tests.m2m_fakes import (
    M2M_PATH,
    TOKEN_PATH,
    FakeM2MTransport,
    RecordingIdentityClient,
    install_identity,
)

ADMIN = "id-admin"
MGR = "id-mgr"
DESTINATARIO = "11111111-1111-1111-1111-111111111111"
DESCONOCIDO = "22222222-2222-2222-2222-222222222222"
MAL_FORMADO = "no-es-un-uuid"

DIRECTORIO = {DESTINATARIO: "Nombre Canonico"}

def _uid(name: str) -> str:
    """UUID determinista a partir de un nombre legible (los ids de Auth son UUID)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"chorus-test:{name}"))



# Usuarios de las pruebas de listado y permisos (UUID válidos)
for _i in range(4):
    DIRECTORIO[_uid(f"user-{_i}")] = f"Usuario {_i}"
    DIRECTORIO[_uid(f"batch-{_i}")] = f"Lote {_i}"
for _i in range(3):
    DIRECTORIO[_uid(f"p-{_i}")] = f"Permiso {_i}"
DIRECTORIO[_uid("otro")] = "Otro"
DIRECTORIO[_uid("otro-miembro")] = "Otro Miembro"


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


def _m2m_settings(**overrides) -> Settings:
    base = {
        "database_url": "mysql+pymysql://osap2027_test:testpass@127.0.0.1:3306/osap_chorus_test",
        "auth_base_url": "https://auth.test",
        "storage_root": "var/private-test",
        "auth_m2m_client_id": "11111111-aaaa-bbbb-cccc-111111111111",
        "auth_m2m_client_secret": "secreto-m2m",
        "auth_m2m_scope": "auth:read_public_names",
        "auth_m2m_audience": "osap-auth",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def app_client(integration_settings: Settings, monkeypatch):
    """App con Auth simulado e identidad M2M configurable por test."""
    profiles = {
        "token-admin": _profile(ADMIN, roles=["admin"]),
        "token-mgr": _profile(MGR),
        "token-member": _profile("id-member"),
    }
    settings = _m2m_settings(database_url=integration_settings.database_url)
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    identity = RecordingIdentityClient(DIRECTORIO)
    install_identity(monkeypatch, identity)

    client = TestClient(create_app(settings))
    group = client.post(
        "/api/v1/groups",
        headers={"Authorization": "Bearer token-mgr"},
        json={"name": "Grupo Identidad"},
    ).json()

    headers = {
        "admin": {"Authorization": "Bearer token-admin"},
        "mgr": {"Authorization": "Bearer token-mgr"},
        "member": {"Authorization": "Bearer token-member"},
    }

    class Ctx:
        def __init__(self):
            self.client = client
            self.group_id = group["id"]
            self.headers = headers
            self.identity = identity

        def set_identity(self, new_client):
            """Reemplaza el cliente de identidad de la app en caliente."""
            self.identity = new_client
            app_state = client.app.state
            app_state.identity_client = new_client
            return new_client

    try:
        yield Ctx()
    finally:
        client.close()


# --------------------------------------------------------------------------
# 1. El directorio local deja de existir
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_admin_users_directory_endpoint_is_gone(app_client):
    response = app_client.client.get(
        "/api/v1/admin/users", headers=app_client.headers["admin"]
    )
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.integration
def test_admin_users_directory_is_not_replaced_by_grouping(app_client):
    """Ninguna ruta agrupa group_members para simular un directorio."""
    paths = {
        route.path
        for route in app_client.client.app.routes
        if getattr(route, "path", "").startswith("/api/v1/admin")
    }
    assert "/api/v1/admin/users" not in paths
    # No hay rutas de usuarios en el mantenimiento administrativo
    assert not any(p.endswith("/users") or "/users/" in p for p in paths)


# --------------------------------------------------------------------------
# 2. El alta consulta realmente el contrato M2M
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_onboarding_consults_m2m_contract(app_client):
    response = app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": DESTINATARIO},
    )
    assert response.status_code == 201, response.text

    # Se consultó Auth para el DESTINATARIO (no para el actor)
    assert [DESTINATARIO] in app_client.identity.calls
    assert ADMIN not in app_client.identity.calls


@pytest.mark.unit
def test_m2m_client_uses_service_token_and_batched_lookup():
    """Contrato real: token de servicio + ids agrupados en una sola llamada."""
    otro = "55555555-5555-4555-8555-555555555555"
    transport = FakeM2MTransport(
        {DESTINATARIO: "Nombre Canonico", otro: "Tercero"}
    )
    client = IdentityClient(
        "https://auth.test",
        client_id="svc-client",
        client_secret="svc-secret",
        transport=transport,
    )

    resolved = client.resolve_public_names([DESTINATARIO, otro])

    assert resolved == {
        DESTINATARIO: "Nombre Canonico",
        otro: "Tercero",
    }
    # Una sola llamada de token y una sola de lookup para dos ids
    assert len(transport.token_calls) == 1
    assert len(transport.lookup_calls) == 1
    # El token se emitió con el contrato client_credentials
    assert transport.token_calls[0]["grant_type"] == "client_credentials"
    assert transport.token_calls[0]["audience"] == "osap-auth"
    assert transport.token_calls[0]["scope"] == "auth:read_public_names"
    # Y se presentó como Bearer del token de servicio, no del administrador
    assert transport.lookup_calls[0]["authorization"] == "Bearer service-token-1"


@pytest.mark.unit
def test_m2m_lookup_batches_in_chunks_of_500():
    """Los ids se agrupan en lotes de 500 (máximo del contrato)."""
    directory = {str(uuid.UUID(int=i)): f"Name {i}" for i in range(600)}
    transport = FakeM2MTransport(directory)
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )

    resolved = client.resolve_public_names(list(directory.keys()))

    assert len(resolved) == 600
    assert len(transport.lookup_calls) == 2, "600 ids -> 2 lotes"
    assert len(transport.lookup_calls[0]["ids"]) == 500
    assert len(transport.lookup_calls[1]["ids"]) == 100


@pytest.mark.unit
def test_m2m_token_is_cached_between_lookups():
    transport = FakeM2MTransport({DESTINATARIO: "Nombre"})
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )

    client.resolve_public_names([DESTINATARIO])
    client.resolve_public_names([DESTINATARIO])

    assert len(transport.token_calls) == 1, "El token de servicio se reutiliza"


@pytest.mark.unit
def test_m2m_token_endpoint_receives_expected_credentials():
    transport = FakeM2MTransport({})
    client = IdentityClient(
        "https://auth.test",
        client_id="mi-cliente",
        client_secret="mi-secreto",
        transport=transport,
    )

    client.resolve_public_names([DESTINATARIO])

    body = transport.token_calls[0]
    assert body["client_id"] == "mi-cliente"
    assert body["client_secret"] == "mi-secreto"
    assert body["grant_type"] == "client_credentials"


# --------------------------------------------------------------------------
# 3. Identidad inexistente: rechazada y sin filas
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_unknown_identity_is_rejected_and_persists_nothing(app_client):
    before = _count_members(app_client)

    response = app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": DESCONOCIDO},
    )
    assert response.status_code == 400, response.text
    assert "Unknown user_id" in response.text

    assert _count_members(app_client) == before, (
        "Una identidad no verificada no debe generar ninguna fila"
    )


@pytest.mark.integration
def test_malformed_identity_is_rejected(app_client):
    response = app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": MAL_FORMADO},
    )
    assert response.status_code == 400, response.text


# --------------------------------------------------------------------------
# 4. Indisponibilidad de Auth: impide el alta
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_auth_unavailable_blocks_onboarding(app_client):
    """Nunca se acepta la identidad por defecto si Auth no responde."""
    app_client.set_identity(RecordingIdentityClient({}, available=False))
    before = _count_members(app_client)

    response = app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": DESTINATARIO},
    )
    assert response.status_code == 503, response.text
    assert _count_members(app_client) == before


@pytest.mark.unit
def test_m2m_error_status_raises_unavailable():
    transport = FakeM2MTransport({DESTINATARIO: "X"}, lookup_status=500)
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )
    with pytest.raises(IdentityUnavailable):
        client.resolve_public_names([DESTINATARIO])


@pytest.mark.unit
def test_m2m_token_rejection_raises_unavailable():
    transport = FakeM2MTransport({DESTINATARIO: "X"}, token_status=401)
    client = IdentityClient(
        "https://auth.test", client_id="c", client_secret="s", transport=transport
    )
    with pytest.raises(IdentityUnavailable):
        client.resolve_public_names([DESTINATARIO])


@pytest.mark.unit
def test_unconfigured_identity_client_raises_unavailable():
    client = IdentityClient("https://auth.test")
    with pytest.raises(IdentityUnavailable):
        client.resolve_public_names([DESTINATARIO])


# --------------------------------------------------------------------------
# 5. El nombre mostrado procede de Auth
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_name_comes_from_auth_not_from_local_record(app_client):
    response = app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": DESTINATARIO, "display_name": "Nombre Falso Del Admin"},
    )
    assert response.status_code == 201, response.text

    listed = app_client.client.get(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
    ).json()
    item = next(m for m in listed if m["user_sub"] == DESTINATARIO)
    assert item["name"] == "Nombre Canonico"
    assert item["identity_verified"] is True
    # El nombre aportado por el administrador no se usa como identidad
    assert item["legacy_display_name"] != "Nombre Falso Del Admin"

    with db_connect(Settings.load()) as conn:
        row = conn.execute(
            "SELECT display_name FROM group_members WHERE group_id = ? AND user_sub = ?",
            (app_client.group_id, DESTINATARIO),
        ).fetchone()
        assert row["display_name"] == "Nombre Canonico"


@pytest.mark.integration
def test_unresolved_identity_is_not_invented(app_client):
    """Auth disponible pero sin ese id: name null y identity_verified false.

    El gestor inicial (id-mgr) no está en el directorio de Auth, así que se
    representa como identidad no resuelta, sin inventar nombre.
    """
    listed = app_client.client.get(
        f"/api/v1/groups/{app_client.group_id}/members",
        headers=app_client.headers["mgr"],
    )
    assert listed.status_code == 200
    item = next(m for m in listed.json() if m["user_sub"] == MGR)
    assert item["name"] is None
    assert item["identity_verified"] is False


def test_unavailable_auth_returns_503_on_member_listing(app_client):
    """Auth caído no se degrada a "nadie verificado": se responde 503."""
    app_client.set_identity(RecordingIdentityClient({}, available=False))

    ordinary = app_client.client.get(
        f"/api/v1/groups/{app_client.group_id}/members",
        headers=app_client.headers["mgr"],
    )
    assert ordinary.status_code == 503, ordinary.text

    administrative = app_client.client.get(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
    )
    assert administrative.status_code == 503, administrative.text


class _MalformedIdentity:
    """Doble que simula una respuesta de Auth que incumple el contrato."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def lookup(self, user_ids):
        from app.identity import IdentityUnavailable

        self.calls.append(list(user_ids))
        raise IdentityUnavailable(
            "osap-auth devolvió un elemento sin el campo obligatorio id"
        )

    def resolve_public_names(self, user_ids):
        return self.lookup(user_ids)

    def resolve_identity(self, user_id: str):
        from app.identity import IdentityUnavailable

        self.calls.append([user_id])
        raise IdentityUnavailable("respuesta malformada de osap-auth")

    def resolve_one(self, user_id: str):
        return self.resolve_identity(user_id)


def test_malformed_contract_returns_503_on_member_listing(app_client):
    """Una respuesta malformada es un error de contrato, no una omisión."""
    app_client.set_identity(_MalformedIdentity())

    ordinary = app_client.client.get(
        f"/api/v1/groups/{app_client.group_id}/members",
        headers=app_client.headers["mgr"],
    )
    assert ordinary.status_code == 503, ordinary.text

    administrative = app_client.client.get(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
    )
    assert administrative.status_code == 503, administrative.text


def test_malformed_contract_blocks_onboarding(app_client):
    """Con respuesta malformada no se puede dar de alta a nadie."""
    app_client.set_identity(_MalformedIdentity())
    before = _count_members(app_client)

    response = app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": DESTINATARIO},
    )
    assert response.status_code == 503, response.text
    assert _count_members(app_client) == before


# --------------------------------------------------------------------------
# 6 y 7. Nombres agrupados, sin consultas individuales
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_member_listing_resolves_names_in_one_batch_call(app_client):
    for index in range(4):
        created = app_client.client.post(
            f"/api/v1/admin/groups/{app_client.group_id}/members",
            headers=app_client.headers["admin"],
            json={"user_sub": _uid(f"user-{index}")},
        )
        assert created.status_code == 201, created.text

    app_client.identity.calls.clear()
    listed = app_client.client.get(
        f"/api/v1/groups/{app_client.group_id}/members",
        headers=app_client.headers["mgr"],
    )
    assert listed.status_code == 200

    # Una única llamada con todos los ids, no una por miembro
    assert len(app_client.identity.calls) == 1, app_client.identity.calls
    called_ids = set(app_client.identity.calls[0])
    assert {_uid(f"user-{i}") for i in range(4)} <= called_ids


@pytest.mark.integration
def test_admin_member_listing_also_batches_names(app_client):
    for index in range(3):
        app_client.client.post(
            f"/api/v1/admin/groups/{app_client.group_id}/members",
            headers=app_client.headers["admin"],
            json={"user_sub": _uid(f"batch-{index}")},
        )

    app_client.identity.calls.clear()
    listed = app_client.client.get(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
    ).json()

    assert len(app_client.identity.calls) == 1, app_client.identity.calls
    assert {_uid(f"batch-{i}") for i in range(3)} <= set(app_client.identity.calls[0])
    assert len(listed) >= 3


# --------------------------------------------------------------------------
# 8. No se crea un catálogo local de usuarios
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_no_local_user_catalog_is_created(app_client):
    """El alta sólo crea la pertenencia; no persiste nombres como catálogo."""
    app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": DESTINATARIO},
    )

    with db_connect(Settings.load()) as conn:
        rows = conn.execute(
            "SELECT COUNT(*) AS c FROM group_members WHERE group_id = ? AND user_sub = ?",
            (app_client.group_id, DESTINATARIO),
        ).fetchone()
        assert rows["c"] == 1

    # No existe tabla de usuarios en el esquema de Chorus
    with db_connect(Settings.load()) as conn:
        tables = {
            row["TABLE_NAME"]
            for row in conn.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            ).fetchall()
        }
    assert "users" not in tables
    assert "user_directory" not in tables


# --------------------------------------------------------------------------
# 9. Se conservan los permisos
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_permissions_are_preserved(app_client):
    admin_url = f"/api/v1/admin/groups/{app_client.group_id}/members"
    group_url = f"/api/v1/groups/{app_client.group_id}/members"

    # Admin global: puede dar de alta por el contrato administrativo
    assert app_client.client.post(
        admin_url, headers=app_client.headers["admin"], json={"user_sub": _uid("p-1")}
    ).status_code == 201

    # Gestor: da de alta por el mantenimiento normal del grupo
    assert app_client.client.post(
        group_url, headers=app_client.headers["mgr"], json={"user_sub": _uid("p-2")}
    ).status_code == 201

    # Un gestor NO puede usar el contrato administrativo global
    assert app_client.client.post(
        admin_url, headers=app_client.headers["mgr"], json={"user_sub": _uid("p-4")}
    ).status_code == 403

    # Miembro ordinario: no puede dar de alta
    assert app_client.client.post(
        group_url, headers=app_client.headers["member"], json={"user_sub": _uid("p-3")}
    ).status_code == 403

    # El gestor puede consultar los grupos de Chorus
    assert app_client.client.get(
        f"/api/v1/groups/{app_client.group_id}/members",
        headers=app_client.headers["mgr"],
    ).status_code == 200
    # El miembro ordinario no puede
    assert app_client.client.get(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["member"],
    ).status_code == 403


# --------------------------------------------------------------------------
# 10. El administrador global no puede conceder manager
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_global_admin_cannot_grant_manager_role(app_client):
    # Alta administrativa: no existe forma de pedir rol manager
    response = app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": DESTINATARIO, "role": "manager"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "member"

    # Ruta histórica de alta: el admin global no puede
    blocked = app_client.client.post(
        f"/api/v1/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": _uid("otro"), "role": "manager"},
    )
    assert blocked.status_code == 403, blocked.text

    # Modificación: tampoco puede ascender ni degradar
    assert app_client.client.patch(
        f"/api/v1/groups/{app_client.group_id}/members/{DESTINATARIO}",
        headers=app_client.headers["admin"],
        json={"role": "manager"},
    ).status_code == 403

    # El gestor del grupo sí puede
    assert app_client.client.patch(
        f"/api/v1/groups/{app_client.group_id}/members/{DESTINATARIO}",
        headers=app_client.headers["mgr"],
        json={"role": "manager"},
    ).status_code == 200


# --------------------------------------------------------------------------
# 11. Se registra el actor real
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_activity_log_records_real_actor(app_client):
    app_client.client.post(
        f"/api/v1/admin/groups/{app_client.group_id}/members",
        headers=app_client.headers["admin"],
        json={"user_sub": DESTINATARIO},
    )

    with db_connect(Settings.load()) as conn:
        log = conn.execute(
            "SELECT actor, event_type, detail_json FROM activity_log "
            "WHERE group_id = ? AND event_type = 'member_added' "
            "ORDER BY id DESC LIMIT 1",
            (app_client.group_id,),
        ).fetchone()

    assert log is not None
    assert log["actor"] == ADMIN, "El actor debe ser el admin autenticado, no el alta"
    assert "identity_verified_by" in (log["detail_json"] or "")


def _count_members(ctx) -> int:
    with db_connect(Settings.load()) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?",
                (ctx.group_id,),
            ).fetchone()["c"]
        )