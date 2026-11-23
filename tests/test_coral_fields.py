"""Fase 2: campos corales en `groups` (12 campos, JSON, orden, NULL, esquema)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class FakeAuthResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def install_fake_auth(monkeypatch, profiles, auth_base_url="https://auth.test"):
    class FakeAuthClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, json=None, headers=None):
            path = url.removeprefix(auth_base_url.rstrip("/"))
            token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
            if method == "GET" and path in ("/auth/me", "/auth/me/"):
                profile = profiles.get(token)
                return FakeAuthResponse(200, profile) if profile else FakeAuthResponse(401, {})
            return FakeAuthResponse(404, {})

    monkeypatch.setattr("app.main.httpx.Client", FakeAuthClient)


def _profile(user_id: str, roles=None):
    return {
        "user_id": user_id,
        "roles": roles if roles is not None else ["user"],
        "email_verified": True,
        "status": "active",
        "onboarding": {"required": False},
        "memberships": [],
    }


CORAL_FIELDS = {
    "foundation_date",
    "dissolution_date",
    "locality",
    "region",
    "country_code",
    "venue",
    "formation_type",
    "member_count",
    "public_email",
    "language",
    "repertoire",
    "venues",
}


@pytest.mark.integration
def test_coral_fields_roundtrip(integration_settings, monkeypatch):
    """Crea un grupo con los 12 campos y verifica su lectura exacta."""
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(
        monkeypatch,
        {"token-rep": _profile("rep-1")},
        settings.auth_base_url,
    )
    repertoire = [
        {"value": "Música sacra", "position": 1},
        {"value": "Música popular", "position": 2},
    ]
    venues = [
        {"value": "Auditorio municipal", "position": 1},
        {"value": "Iglesia parroquial", "position": 2},
    ]
    payload = {
        "entity_id": "coral-roundtrip",
        "name": "Coral Roundtrip",
        "foundation_date": "1984-09-01",
        "dissolution_date": None,
        "locality": "Llinars del Vallès",
        "region": "Barcelona",
        "country_code": "ES",
        "venue": "Mas Baga",
        "formation_type": "mixta",
        "member_count": 30,
        "public_email": "coro@example.org",
        "language": ["ca", "es", "en"],
        "repertoire": repertoire,
        "venues": venues,
    }
    with TestClient(create_app(settings)) as client:
        resp = client.post(
            "/api/v1/groups",
            headers={"Authorization": "Bearer token-rep"},
            json=payload,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()

    assert CORAL_FIELDS <= set(body.keys())
    assert body["foundation_date"] == "1984-09-01"
    assert body["dissolution_date"] is None
    assert body["locality"] == "Llinars del Vallès"
    assert body["region"] == "Barcelona"
    assert body["country_code"] == "ES"
    assert body["venue"] == "Mas Baga"
    assert body["formation_type"] == "mixta"
    assert body["member_count"] == 30
    assert body["public_email"] == "coro@example.org"
    assert body["language"] == ["ca", "es", "en"]
    assert body["repertoire"] == repertoire
    assert body["venues"] == venues


@pytest.mark.integration
def test_coral_json_order_preserved(integration_settings, monkeypatch):
    """Las colecciones conservan el orden de entrada y las posiciones."""
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(
        monkeypatch,
        {"token-rep": _profile("rep-1")},
        settings.auth_base_url,
    )
    # Orden intencionadamente NO alfabético y posiciones no contiguas
    repertoire = [
        {"value": "Zarzuela", "position": 3},
        {"value": "Gospel", "position": 1},
        {"value": "Bolero", "position": 2},
    ]
    with TestClient(create_app(settings)) as client:
        resp = client.post(
            "/api/v1/groups",
            headers={"Authorization": "Bearer token-rep"},
            json={
                "entity_id": "coral-order",
                "name": "Coral Order",
                "repertoire": repertoire,
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()

    # El orden del array se preserva tal cual (no se reordena)
    assert [r["value"] for r in body["repertoire"]] == ["Zarzuela", "Gospel", "Bolero"]
    assert [r["position"] for r in body["repertoire"]] == [3, 1, 2]


@pytest.mark.integration
def test_coral_fields_null_when_absent(integration_settings, monkeypatch):
    """Sin datos corales, todos los campos permanecen NULL (no valores ficticios)."""
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(
        monkeypatch,
        {"token-rep": _profile("rep-1")},
        settings.auth_base_url,
    )
    with TestClient(create_app(settings)) as client:
        resp = client.post(
            "/api/v1/groups",
            headers={"Authorization": "Bearer token-rep"},
            json={"entity_id": "coral-empty", "name": "Coral Vacío"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()

    for field in CORAL_FIELDS:
        assert body[field] is None, f"{field} debería ser NULL"


@pytest.mark.integration
def test_coral_update_roundtrip(integration_settings, monkeypatch):
    """PATCH actualiza los campos corales y devuelve JSON (no cadenas)."""
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(
        monkeypatch,
        {"token-rep": _profile("rep-1")},
        settings.auth_base_url,
    )
    with TestClient(create_app(settings)) as client:
        headers = {"Authorization": "Bearer token-rep"}
        created = client.post(
            "/api/v1/groups",
            headers=headers,
            json={"entity_id": "coral-update", "name": "Coral Update"},
        )
        group_id = created.json()["id"]

        patched = client.patch(
            f"/api/v1/groups/{group_id}",
            headers=headers,
            json={
                "language": ["fr"],
                "venues": [{"value": "Sala A", "position": 1}],
            },
        )
        assert patched.status_code == 200, patched.text
        body = patched.json()

    assert body["language"] == ["fr"]
    assert body["venues"] == [{"value": "Sala A", "position": 1}]
    # Los campos no enviados en PATCH permanecen NULL
    assert body["repertoire"] is None
    assert body["locality"] is None


@pytest.mark.integration
def test_coral_invalid_country_code_rejected(integration_settings, monkeypatch):
    """Validación: country_code debe ser ISO de 2 letras mayúsculas."""
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(
        monkeypatch,
        {"token-rep": _profile("rep-1")},
        settings.auth_base_url,
    )
    with TestClient(create_app(settings)) as client:
        resp = client.post(
            "/api/v1/groups",
            headers={"Authorization": "Bearer token-rep"},
            json={"entity_id": "coral-bad", "name": "Coral Bad", "country_code": "esp"},
        )
    assert resp.status_code == 422


@pytest.mark.migrations
def test_coral_columns_schema(migration_settings):
    """Esquema: los 12 campos existen, con tipos correctos y todos NULL-ables."""
    from app.db import connect as db_connect

    expected = {
        "foundation_date": "date",
        "dissolution_date": "date",
        "locality": "varchar",
        "region": "varchar",
        "country_code": "char",
        "venue": "varchar",
        "formation_type": "varchar",
        "member_count": "int",
        "public_email": "varchar",
        "language": "longtext",
        "repertoire": "longtext",
        "venues": "longtext",
    }
    with db_connect(migration_settings) as conn:
        rows = conn.execute(
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH "
            "FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'groups'"
        ).fetchall()
    cols = {r["COLUMN_NAME"]: r for r in rows}

    for name, dtype in expected.items():
        assert name in cols, f"Falta la columna {name}"
        assert cols[name]["DATA_TYPE"] == dtype, f"{name} tipo {cols[name]['DATA_TYPE']} != {dtype}"
        assert cols[name]["IS_NULLABLE"] == "YES", f"{name} debería admitir NULL"

    # Longitudes exactas para los campos con tamaño fijo
    assert int(cols["locality"]["CHARACTER_MAXIMUM_LENGTH"]) == 160
    assert int(cols["region"]["CHARACTER_MAXIMUM_LENGTH"]) == 160
    assert int(cols["country_code"]["CHARACTER_MAXIMUM_LENGTH"]) == 2
    assert int(cols["venue"]["CHARACTER_MAXIMUM_LENGTH"]) == 255
    assert int(cols["formation_type"]["CHARACTER_MAXIMUM_LENGTH"]) == 48
    assert int(cols["public_email"]["CHARACTER_MAXIMUM_LENGTH"]) == 254
