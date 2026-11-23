"""Semántica PATCH de trabajos de preparación (omitido vs null explícito)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
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


@pytest.fixture
def space_with_work(integration_settings: Settings, monkeypatch):
    """Devuelve (client, headers, space_id, work) con un trabajo completo."""
    profiles = {"token-mgr": _profile("patch-mgr")}
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    client = TestClient(create_app(settings))
    headers = {"Authorization": "Bearer token-mgr"}

    space_id = client.post(
        "/api/v1/spaces",
        headers=headers,
        json={"space_type": "personal", "name": "Patch space"},
    ).json()["id"]

    work = client.post(
        f"/api/v1/spaces/{space_id}/preparation-works",
        headers=headers,
        json={
            "title": "Titulo original",
            "composer": "Compositor original",
            "destination_type": "program",
            "event_name": "Evento original",
            "event_date": "2026-06-01",
            "notes": "Notas originales",
        },
    ).json()

    yield client, headers, space_id, work
    client.close()


def _patch(client, headers, space_id, work_id, payload):
    return client.patch(
        f"/api/v1/spaces/{space_id}/preparation-works/{work_id}",
        headers=headers,
        json=payload,
    )


def _get(client, headers, space_id, work_id):
    return client.get(
        f"/api/v1/spaces/{space_id}/preparation-works/{work_id}", headers=headers
    ).json()


@pytest.mark.integration
def test_patch_status_preserves_name_and_event_date(space_with_work):
    """1. Actualizar sólo status no altera nombre ni fecha del evento."""
    client, headers, space_id, work = space_with_work
    work_id = work["id"]

    r = _patch(client, headers, space_id, work_id, {"status": "ready"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["status"] == "ready"
    assert body["title"] == "Titulo original"
    assert body["event_date"] == "2026-06-01"
    assert body["event_name"] == "Evento original"
    assert body["composer"] == "Compositor original"
    assert body["notes"] == "Notas originales"
    assert body["destination_type"] == "program"

    # Persistido, no sólo en la respuesta
    assert _get(client, headers, space_id, work_id)["title"] == "Titulo original"


@pytest.mark.integration
def test_patch_title_preserves_everything_else(space_with_work):
    """2. Actualizar únicamente title conserva el resto de campos."""
    client, headers, space_id, work = space_with_work
    work_id = work["id"]

    r = _patch(client, headers, space_id, work_id, {"title": "Titulo nuevo"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["title"] == "Titulo nuevo"
    assert body["composer"] == "Compositor original"
    assert body["destination_type"] == "program"
    assert body["event_name"] == "Evento original"
    assert body["event_date"] == "2026-06-01"
    assert body["notes"] == "Notas originales"
    assert body["status"] == "preparing"


@pytest.mark.integration
def test_patch_explicit_null_clears_event_name(space_with_work):
    """3. Enviar event_name: null limpia el nombre del evento."""
    client, headers, space_id, work = space_with_work
    work_id = work["id"]

    r = _patch(client, headers, space_id, work_id, {"event_name": None})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["event_name"] is None
    # El resto permanece intacto
    assert body["event_date"] == "2026-06-01"
    assert body["title"] == "Titulo original"


@pytest.mark.integration
def test_patch_explicit_null_clears_event_date(space_with_work):
    """4. Enviar event_date: null limpia la fecha del evento."""
    client, headers, space_id, work = space_with_work
    work_id = work["id"]

    r = _patch(client, headers, space_id, work_id, {"event_date": None})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["event_date"] is None
    assert body["event_name"] == "Evento original"
    assert body["title"] == "Titulo original"


@pytest.mark.integration
def test_empty_patch_is_defined_and_safe(space_with_work):
    """5. Una actualización vacía no cambia nada y responde el estado actual."""
    client, headers, space_id, work = space_with_work
    work_id = work["id"]

    before = _get(client, headers, space_id, work_id)
    r = _patch(client, headers, space_id, work_id, {})
    assert r.status_code == 200, r.text
    after = r.json()

    for field in ("title", "composer", "destination_type", "event_name",
                  "event_date", "notes", "status"):
        assert after[field] == before[field], f"{field} cambió con un PATCH vacío"


@pytest.mark.integration
def test_patch_null_on_non_nullable_field_is_rejected(space_with_work):
    """Un null explícito sobre una columna NOT NULL se rechaza con 400."""
    client, headers, space_id, work = space_with_work
    work_id = work["id"]

    for field in ("title", "status", "destination_type"):
        r = _patch(client, headers, space_id, work_id, {field: None})
        assert r.status_code == 400, f"{field} debería rechazarse: {r.text}"
        assert "cannot be null" in r.text

    # No se ha modificado nada
    body = _get(client, headers, space_id, work_id)
    assert body["title"] == "Titulo original"
    assert body["status"] == "preparing"
    assert body["destination_type"] == "program"


@pytest.mark.integration
def test_patch_nullable_fields_can_all_be_cleared(space_with_work):
    """Los campos opcionales admite limpieza explícita sin tocar los demás."""
    client, headers, space_id, work = space_with_work
    work_id = work["id"]

    r = _patch(
        client, headers, space_id, work_id,
        {"composer": None, "notes": None, "event_name": None, "event_date": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["composer"] is None
    assert body["notes"] is None
    assert body["event_name"] is None
    assert body["event_date"] is None
    # Obligatorios intactos
    assert body["title"] == "Titulo original"
    assert body["destination_type"] == "program"
    assert body["status"] == "preparing"


@pytest.mark.integration
def test_space_patch_distinguishes_omitted_and_null(integration_settings: Settings, monkeypatch):
    """Mismo criterio aplicado al PATCH de espacios."""
    profiles = {"token-mgr": _profile("space-patch-mgr")}
    settings = replace(integration_settings, auth_base_url="https://auth.test")
    install_fake_auth(monkeypatch, profiles, settings.auth_base_url)

    with TestClient(create_app(settings)) as client:
        headers = {"Authorization": "Bearer token-mgr"}
        space_id = client.post(
            "/api/v1/spaces", headers=headers,
            json={"space_type": "personal", "name": "Original", "description": "Desc"},
        ).json()["id"]

        # Sólo name: description se conserva
        r = client.patch(f"/api/v1/spaces/{space_id}", headers=headers,
                         json={"name": "Cambiado"})
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Cambiado"
        assert r.json()["description"] == "Desc"

        # description: null explícito la limpia
        r = client.patch(f"/api/v1/spaces/{space_id}", headers=headers,
                         json={"description": None})
        assert r.status_code == 200, r.text
        assert r.json()["description"] is None
        assert r.json()["name"] == "Cambiado"

        # name: null se rechaza (NOT NULL)
        r = client.patch(f"/api/v1/spaces/{space_id}", headers=headers,
                         json={"name": None})
        assert r.status_code == 400

        # PATCH vacío: sin cambios
        r = client.patch(f"/api/v1/spaces/{space_id}", headers=headers, json={})
        assert r.status_code == 200
        assert r.json()["name"] == "Cambiado"