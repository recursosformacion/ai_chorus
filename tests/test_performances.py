"""Performances (actuaciones): lectura publicada y participacion de grupos.

Etapa 1 de la clasificacion de `performances` (plan AutoFree en
`docs/architecture/PLAN.md`): API de lectura para contenido publicado, acceso a
borradores para miembros de grupos participantes y vinculacion gestionada por el
gestor del grupo. La escritura editorial (alta/edicion/borrado) queda para la etapa 2.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect as db_connect
from app.main import create_app
from app.utils import utcnow


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


def _insert_performance(conn, *, status: str, title: str, starts_on: str = "2026-06-01") -> str:
    performance_id = uuid.uuid4().hex
    now = utcnow()
    conn.execute(
        "INSERT INTO performances (id, slug, title, summary, kind, modality, event_status, "
        "editorial_status, starts_on, starts_at, created_at, updated_at, views) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
        (
            performance_id,
            f"slug-{performance_id[:12]}",
            title,
            "Resumen de prueba",
            "concert",
            "onsite",
            "scheduled",
            status,
            starts_on,
            f"{starts_on}T20:00",
            now,
            now,
        ),
    )
    return performance_id


@pytest.mark.integration
def test_performances_public_read_and_group_participation(
    integration_settings: Settings, monkeypatch
):
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

        grp = client.post("/api/v1/groups", headers=mgr_h, json={"name": "Coro Performances"}).json()
        group_id = grp["id"]
        assert (
            client.post("/api/v1/groups/join", headers=mem_h, json={"code": grp["join_code"]}).status_code
            == 200
        )

        tag = uuid.uuid4().hex[:8]
        with db_connect(integration_settings) as conn:
            published = _insert_performance(
                conn, status="published", title=f"Concierto publico {tag}", starts_on="2026-06-01"
            )
            draft_linked = _insert_performance(
                conn, status="draft", title=f"Concierto borrador {tag}", starts_on="2026-07-01"
            )
            draft_free = _insert_performance(
                conn, status="draft", title=f"Concierto sin grupo {tag}", starts_on="2026-08-01"
            )
            conn.execute(
                "INSERT INTO performance_groups (performance_id, group_id, role) VALUES (?,?,?)",
                (published, group_id, "participant"),
            )
            conn.execute(
                "INSERT INTO performance_groups (performance_id, group_id, role) VALUES (?,?,?)",
                (draft_linked, group_id, "organizer"),
            )

        # ===== LECTURA PUBLICADA =====
        r = client.get("/api/v1/performances?limit=200", headers=adm_h)
        assert r.status_code == 200, r.text
        by_id = {item["id"]: item for item in r.json()}
        assert published in by_id
        assert by_id[published]["editorial_status"] == "published"
        assert by_id[published]["groups"][0]["group_id"] == group_id
        # Datos internos (email de origen) nunca se exponen
        assert "source_email" not in by_id[published]

        # Un externo no ve borradores
        r = client.get("/api/v1/performances?limit=200", headers=out_h)
        assert r.status_code == 200
        out_ids = {item["id"] for item in r.json()}
        assert published in out_ids
        assert draft_linked not in out_ids
        assert draft_free not in out_ids

        # Un miembro del grupo participante si ve el borrador vinculado
        r = client.get("/api/v1/performances?limit=200", headers=mem_h)
        assert r.status_code == 200
        mem_ids = {item["id"] for item in r.json()}
        assert draft_linked in mem_ids
        assert draft_free not in mem_ids

        # Detalle
        assert client.get(f"/api/v1/performances/{published}", headers=out_h).status_code == 200
        assert client.get(f"/api/v1/performances/{draft_linked}", headers=out_h).status_code == 404
        assert client.get(f"/api/v1/performances/{draft_linked}", headers=mem_h).status_code == 200
        assert client.get(f"/api/v1/performances/{draft_free}", headers=mem_h).status_code == 404
        assert client.get(f"/api/v1/performances/{uuid.uuid4().hex}", headers=adm_h).status_code == 404

        # Filtros y paginacion
        r = client.get("/api/v1/performances?kind=concert&limit=1&offset=0", headers=adm_h)
        assert r.status_code == 200
        assert len(r.json()) == 1
        r = client.get(f"/api/v1/performances?q={tag}&date_from=2026-07-01", headers=adm_h)
        assert r.status_code == 200
        assert {item["id"] for item in r.json()} >= {draft_linked, draft_free}
        assert client.get("/api/v1/performances?limit=0", headers=adm_h).status_code == 422

        # ===== PARTICIPACION EN EL GRUPO =====
        r = client.get(f"/api/v1/groups/{group_id}/performances", headers=mem_h)
        assert r.status_code == 200
        assert {item["id"] for item in r.json()} == {published}

        r = client.get(f"/api/v1/groups/{group_id}/performances?include_drafts=true", headers=mem_h)
        assert r.status_code == 200
        assert {item["id"] for item in r.json()} == {published}  # solo el gestor ve borradores

        r = client.get(f"/api/v1/groups/{group_id}/performances?include_drafts=true", headers=mgr_h)
        assert r.status_code == 200
        assert {item["id"] for item in r.json()} == {published, draft_linked}

        r = client.get(f"/api/v1/groups/{group_id}/performances", headers=out_h)
        assert r.status_code == 403

        # Candidatas: solo el gestor, y sin las ya vinculadas
        r = client.get(f"/api/v1/groups/{group_id}/performances/candidates", headers=mem_h)
        assert r.status_code == 403
        r = client.get(f"/api/v1/groups/{group_id}/performances/candidates", headers=mgr_h)
        assert r.status_code == 200
        candidate_ids = {item["id"] for item in r.json()}
        assert draft_free in candidate_ids
        assert published not in candidate_ids
        assert draft_linked not in candidate_ids

        # Vincular (solo gestor) y evitar duplicados
        member_link = f"/api/v1/groups/{group_id}/performances/{draft_free}"
        assert client.post(member_link, headers=mem_h, json={}).status_code == 403
        r = client.post(member_link, headers=mgr_h, json={"role": "guest"})
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "guest"
        assert client.post(member_link, headers=mgr_h, json={}).status_code == 409
        r = client.post(
            f"/api/v1/groups/{group_id}/performances/{published}",
            headers=mgr_h,
            json={"group_id": group_id},
        )
        assert r.status_code == 409

        # Desvincular
        assert client.delete(member_link, headers=mem_h).status_code == 403
        assert client.delete(member_link, headers=mgr_h).status_code == 200
        assert client.delete(member_link, headers=mgr_h).status_code == 404

        # Grupos inexistentes / actuaciones inexistentes
        missing_group = f"/api/v1/groups/{uuid.uuid4().hex}/performances"
        assert client.get(missing_group, headers=mgr_h).status_code == 404
        r = client.post(
            f"/api/v1/groups/{group_id}/performances/{uuid.uuid4().hex}", headers=mgr_h, json={}
        )
        assert r.status_code == 404
