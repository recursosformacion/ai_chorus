"""Autorización de archivos de preparación restringidos a una sección.

Cubre listado y descarga (ruta canónica por id y ruta histórica por nombre),
incluyendo que el contenido no se entrega en los casos denegados.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect as db_connect
from app.main import create_app

FILE_CONTENT = b"CONTENIDO-RESTRINGIDO"
FREE_CONTENT = b"CONTENIDO-LIBRE"


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


def _insert_chain(conn, *, work_id, resource_id, file_id,
                  owner_sub=None, group_id=None, section_id=None):
    now = "2026-01-01 00:00:00"
    conn.execute(
        "INSERT INTO works (id, title, created_at, updated_at, required_resource_id, owner_sub) "
        "VALUES (?,?,?,?,?,?)",
        (work_id, f"Work {work_id}", now, now, resource_id, owner_sub),
    )
    conn.execute(
        "INSERT INTO resources "
        "(id, work_id, resource_type, created_at, updated_at, required_file_id, "
        " group_id, group_section_id, material_status) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (resource_id, work_id, "score", now, now, file_id, group_id, section_id, "registered"),
    )
    conn.execute(
        "INSERT INTO files "
        "(id, resource_id, name, original_name, status, storage_pointer, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (file_id, resource_id, f"{file_id}.mxl", f"{file_id}.mxl", "registered",
         f"private/{file_id}", now, now),
    )
    conn.commit()


@pytest.fixture
def scenario(integration_settings: Settings, monkeypatch):
    """Grupo con dos secciones, un archivo restringido y otro sin restringir."""
    profiles = {
        "token-mgr": _profile("sec-mgr"),
        "token-s1": _profile("sec-one"),
        "token-s2": _profile("sec-two"),
        "token-out": _profile("sec-out"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    client = TestClient(create_app(integration_settings))
    mgr = {"Authorization": "Bearer token-mgr"}
    s1 = {"Authorization": "Bearer token-s1"}
    s2 = {"Authorization": "Bearer token-s2"}
    out = {"Authorization": "Bearer token-out"}

    grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Secciones"}).json()
    group_id, join_code = grp["id"], grp["join_code"]

    # group_sections no tiene FK a groups: se usan ids únicos por grupo y se
    # limpian explícitamente para que el test sea repetible.
    sec1_id = f"sec1-{group_id[:10]}"
    sec2_id = f"sec2-{group_id[:10]}"

    with db_connect(integration_settings) as conn:
        for section_id, name, code in ((sec1_id, "Soprano", "soprano"),
                                       (sec2_id, "Tenor", "tenor")):
            conn.execute(
                "INSERT INTO group_sections "
                "(id, group_id, name, code, active, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (section_id, group_id, name, code, 1,
                 "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
            )
        conn.commit()

    for headers in (s1, s2):
        assert client.post("/api/v1/groups/join", headers=headers,
                           json={"code": join_code}).status_code == 200

    # s1 en sección 1, s2 en sección 2
    assert client.patch(f"/api/v1/groups/{group_id}/members/sec-one", headers=mgr,
                        json={"section_id": sec1_id}).status_code == 200
    assert client.patch(f"/api/v1/groups/{group_id}/members/sec-two", headers=mgr,
                        json={"section_id": sec2_id}).status_code == 200

    space_id = client.post(
        "/api/v1/spaces", headers=mgr,
        json={"space_type": "group", "group_id": group_id, "name": "General"},
    ).json()["id"]
    work_id = client.post(
        f"/api/v1/spaces/{space_id}/preparation-works", headers=mgr,
        json={"title": "Trabajo con archivos"},
    ).json()["id"]

    # Archivo restringido a la sección 1 y archivo sin restricción
    with db_connect(integration_settings) as conn:
        _insert_chain(conn, work_id="w-sec", resource_id="r-sec", file_id="f-sec",
                      group_id=group_id, section_id=sec1_id)
        _insert_chain(conn, work_id="w-free", resource_id="r-free", file_id="f-free",
                      group_id=group_id, section_id=None)

    # El manager incorpora ambos (tiene autoridad sobre todas las secciones)
    r1 = client.post(
        f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files",
        headers=mgr, json={"file_id": "f-sec", "purpose": "score"},
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files",
        headers=mgr, json={"file_id": "f-free", "purpose": "part"},
    )
    assert r2.status_code == 201, r2.text

    # El contenido real de los archivos debe existir en el almacén privado
    from pathlib import Path

    with db_connect(integration_settings) as conn:
        pointers = {
            row["id"]: row["storage_pointer"]
            for row in conn.execute(
                "SELECT id, storage_pointer FROM files WHERE id IN ('f-sec','f-free')"
            ).fetchall()
        }
    contents = {"f-sec": FILE_CONTENT, "f-free": FREE_CONTENT}
    for file_id, pointer in pointers.items():
        stored = Path(pointer)
        if not stored.is_absolute():
            stored = Path(integration_settings.storage_root) / stored
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_bytes(contents[file_id])

    yield {
        "client": client, "mgr": mgr, "s1": s1, "s2": s2, "out": out,
        "group_id": group_id, "space_id": space_id, "work_id": work_id,
        "sec_file_id": "f-sec", "free_file_id": "f-free",
    }
    client.close()


def _list(client, headers, space_id, work_id):
    return client.get(
        f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files", headers=headers
    )


def _download_by_id(client, headers, space_id, work_id, file_id):
    return client.get(
        f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files/{file_id}/download",
        headers=headers,
    )


def _download_by_name(client, headers, group_id, work_id, file_name):
    return client.get(
        f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files/{file_name}/download",
        headers=headers,
    )


# --------------------------------------------------------------------------
# 1. Manager: lista y descarga el archivo restringido
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_manager_can_list_and_download_section_file(scenario):
    ctx = scenario
    listed = _list(ctx["client"], ctx["mgr"], ctx["space_id"], ctx["work_id"])
    assert listed.status_code == 200
    ids = {item["file_id"] for item in listed.json()}
    assert "f-sec" in ids and "f-free" in ids

    dl = _download_by_id(ctx["client"], ctx["mgr"], ctx["space_id"],
                         ctx["work_id"], "f-sec")
    assert dl.status_code == 200
    assert dl.content == FILE_CONTENT


# --------------------------------------------------------------------------
# 2. Miembro de la sección autorizada: lista y descarga
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_authorized_section_member_can_list_and_download(scenario):
    ctx = scenario
    listed = _list(ctx["client"], ctx["s1"], ctx["space_id"], ctx["work_id"])
    assert listed.status_code == 200
    ids = {item["file_id"] for item in listed.json()}
    assert "f-sec" in ids

    dl = _download_by_id(ctx["client"], ctx["s1"], ctx["space_id"],
                         ctx["work_id"], "f-sec")
    assert dl.status_code == 200
    assert dl.content == FILE_CONTENT


# --------------------------------------------------------------------------
# 3. Miembro de otra sección: no lista el archivo restringido
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_other_section_member_cannot_list_restricted_file(scenario):
    ctx = scenario
    listed = _list(ctx["client"], ctx["s2"], ctx["space_id"], ctx["work_id"])
    assert listed.status_code == 200
    ids = {item["file_id"] for item in listed.json()}
    assert "f-sec" not in ids, "No debe ver el archivo restringido a otra sección"


# --------------------------------------------------------------------------
# 4. Miembro de otra sección: no descarga por identificador
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_other_section_member_cannot_download_by_id(scenario):
    ctx = scenario
    dl = _download_by_id(ctx["client"], ctx["s2"], ctx["space_id"],
                         ctx["work_id"], "f-sec")
    assert dl.status_code == 403
    assert dl.content != FILE_CONTENT, "No debe entregarse el contenido"


# --------------------------------------------------------------------------
# 5. Miembro de otra sección: no descarga por la ruta histórica (nombre)
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_other_section_member_cannot_download_by_legacy_name(scenario):
    ctx = scenario
    dl = _download_by_name(ctx["client"], ctx["s2"], ctx["group_id"],
                           ctx["work_id"], "f-sec.mxl")
    assert dl.status_code == 403
    assert dl.content != FILE_CONTENT, "No debe entregarse el contenido"

    # La ruta histórica no puede ser más permisiva que la canónica
    dl_id = _download_by_id(ctx["client"], ctx["s2"], ctx["space_id"],
                            ctx["work_id"], "f-sec")
    assert dl.status_code == dl_id.status_code


# --------------------------------------------------------------------------
# 6. Archivo sin restricción: visibilidad normal del espacio
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_unrestricted_file_keeps_space_visibility(scenario):
    ctx = scenario

    # Un miembro de otra sección sigue viendo el archivo sin restricción
    listed = _list(ctx["client"], ctx["s2"], ctx["space_id"], ctx["work_id"])
    assert listed.status_code == 200
    ids = {item["file_id"] for item in listed.json()}
    assert "f-free" in ids
    assert "f-sec" not in ids

    dl = _download_by_id(ctx["client"], ctx["s2"], ctx["space_id"],
                         ctx["work_id"], "f-free")
    assert dl.status_code == 200
    assert dl.content == FREE_CONTENT

    # Un extraño al grupo no ve nada
    listed_out = _list(ctx["client"], ctx["out"], ctx["space_id"], ctx["work_id"])
    assert listed_out.status_code == 403


# --------------------------------------------------------------------------
# 7. La revocación de membresía impide el acceso posterior
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_membership_revocation_blocks_access(scenario):
    ctx = scenario
    client, mgr = ctx["client"], ctx["mgr"]

    # Antes: el miembro de la sección 1 accede
    assert _download_by_id(client, ctx["s1"], ctx["space_id"],
                           ctx["work_id"], "f-sec").status_code == 200

    # El manager lo expulsa del grupo
    removed = client.delete(
        f"/api/v1/groups/{ctx['group_id']}/members/sec-one", headers=mgr
    )
    assert removed.status_code in (200, 204)

    # Después: ni listado ni descarga
    listed = _list(client, ctx["s1"], ctx["space_id"], ctx["work_id"])
    assert listed.status_code == 403

    dl_id = _download_by_id(client, ctx["s1"], ctx["space_id"],
                            ctx["work_id"], "f-sec")
    assert dl_id.status_code == 403
    assert dl_id.content != FILE_CONTENT

    dl_name = _download_by_name(client, ctx["s1"], ctx["group_id"],
                                ctx["work_id"], "f-sec.mxl")
    assert dl_name.status_code == 403
    assert dl_name.content != FILE_CONTENT


# --------------------------------------------------------------------------
# 8. Un usuario ajeno no accede aunque conozca el identificador
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_outsider_cannot_access_known_file_id(scenario):
    ctx = scenario
    client, out = ctx["client"], ctx["out"]

    # Sin pertenencia, el listado responde 403
    assert _list(client, out, ctx["space_id"], ctx["work_id"]).status_code == 403

    # Conociendo el identificador del File tampoco accede
    dl_id = _download_by_id(client, out, ctx["space_id"], ctx["work_id"], "f-sec")
    assert dl_id.status_code == 403
    assert dl_id.content != FILE_CONTENT

    dl_name = _download_by_name(client, out, ctx["group_id"], ctx["work_id"], "f-sec.mxl")
    assert dl_name.status_code == 403
    assert dl_name.content != FILE_CONTENT