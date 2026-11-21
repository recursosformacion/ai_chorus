"""Modelo unificado de archivos de preparación y reglas de acceso a Resource/File."""

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
        "(id, resource_id, name, status, storage_pointer, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (file_id, resource_id, f"{file_id}.mxl", "registered", f"private/{file_id}", now, now),
    )
    conn.commit()


def _setup_group_space(client, headers, *, name="Grupo Archivos"):
    grp = client.post("/api/v1/groups", headers=headers, json={"name": name}).json()
    group_id, join_code = grp["id"], grp["join_code"]
    space_id = client.post(
        "/api/v1/spaces", headers=headers,
        json={"space_type": "group", "group_id": group_id, "name": "General"},
    ).json()["id"]
    work_id = client.post(
        f"/api/v1/spaces/{space_id}/preparation-works", headers=headers,
        json={"title": "Trabajo"},
    ).json()["id"]
    return group_id, join_code, space_id, work_id


# --------------------------------------------------------------------------
# §6 Modelo unificado
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_upload_creates_file_and_reference_records(integration_settings: Settings, monkeypatch):
    """La subida deja archivo físico, registro files y relación preparation_work_files."""
    profiles = {"token-mgr": _profile("file-mgr")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        group_id, join_code, space_id, work_id = _setup_group_space(client, mgr)

        r = client.post(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files",
            headers=mgr,
            files=[("files", ("score.pdf", b"%PDF contenido", "application/pdf"))],
            data={"parts": '[{"part_label": "Soprano", "purpose": "score"}]'},
        )
        assert r.status_code == 201, r.text
        entry = r.json()["files"][0]
        assert entry["id"], "La referencia debe tener identificador estable"
        assert entry["file_id"], "El File de Chorus debe tener identificador"

        with db_connect(integration_settings) as conn:
            ref = conn.execute(
                "SELECT file_id FROM preparation_work_files WHERE id = ?", (entry["id"],)
            ).fetchone()
            assert ref is not None and ref["file_id"] == entry["file_id"]

            file_row = conn.execute(
                "SELECT * FROM files WHERE id = ?", (entry["file_id"],)
            ).fetchone()
            assert file_row is not None
            assert file_row["original_name"] == "score.pdf"
            assert file_row["size_bytes"] == len(b"%PDF contenido")
            assert file_row["storage_pointer"], "Debe apuntar al almacenamiento privado"

            resource = conn.execute(
                "SELECT * FROM resources WHERE id = ?", (file_row["resource_id"],)
            ).fetchone()
            assert resource["group_id"] == group_id, (
                "La Resource debe quedar compartida con el grupo del espacio"
            )
            assert resource["part_label"] == "Soprano"

            # El archivo físico existe en el almacén privado
            from pathlib import Path
            pointer = Path(file_row["storage_pointer"])
            if not pointer.is_absolute():
                pointer = Path(integration_settings.storage_root) / pointer
            assert pointer.is_file(), "El archivo físico debe existir"


@pytest.mark.integration
def test_unified_list_download_and_remove_reference(integration_settings: Settings, monkeypatch):
    """Listar, descargar por id y retirar referencias sin destruir el archivo."""
    profiles = {"token-mgr": _profile("uni-mgr")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        group_id, join_code, space_id, work_id = _setup_group_space(client, mgr)

        up = client.post(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files",
            headers=mgr,
            files=[("files", ("partitura.mxl", b"<score/>", "application/vnd.recordare.musicxml"))],
            data={"parts": '[{"part_label": "Director", "purpose": "score"}]'},
        )
        assert up.status_code == 201, up.text
        entry = up.json()["files"][0]

        # Listado unificado (mismo contrato para ambas rutas)
        listed_new = client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files", headers=mgr
        ).json()
        listed_old = client.get(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files", headers=mgr
        ).json()
        assert len(listed_new) == len(listed_old) == 1
        for item in listed_new:
            assert item["name"] == "partitura.mxl"
            assert item["file_id"]
            assert item["part_label"] == "Director"

        # Descarga por id estable
        dl = client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}"
            f"/files/{entry['file_id']}/download",
            headers=mgr,
        )
        assert dl.status_code == 200, dl.text
        assert dl.content == b"<score/>"

        # Descarga por nombre (ruta histórica)
        dl_old = client.get(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}"
            f"/files/partitura.mxl/download",
            headers=mgr,
        )
        assert dl_old.status_code == 200, dl_old.text

        # Retirar la referencia: no borra el archivo físico ni el registro files
        rm = client.delete(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files/partitura.mxl",
            headers=mgr,
        )
        assert rm.status_code == 200

        with db_connect(integration_settings) as conn:
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM preparation_work_files WHERE file_id = ?",
                (entry["file_id"],),
            ).fetchone()["c"] == 0
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE id = ?", (entry["file_id"],)
            ).fetchone()["c"] == 1, "El File no debe destruirse"
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM resources WHERE work_id = ?",
                (f"pw-{work_id}",),
            ).fetchone()["c"] == 1, "La Resource no debe destruirse"

        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files", headers=mgr
        ).json() == []


@pytest.mark.integration
def test_upload_is_idempotent_for_container_work(integration_settings: Settings, monkeypatch):
    """Varias subidas reutilizan la Work contenedora en lugar de duplicarla."""
    profiles = {"token-mgr": _profile("idemf-mgr")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        group_id, join_code, space_id, work_id = _setup_group_space(client, mgr)

        for name in ("a.mxl", "b.mxl"):
            r = client.post(
                f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files",
                headers=mgr, files=[("files", (name, b"data", "application/xml"))],
            )
            assert r.status_code == 201, r.text

        with db_connect(integration_settings) as conn:
            works = conn.execute(
                "SELECT COUNT(*) AS c FROM works WHERE id = ?", (f"pw-{work_id}",)
            ).fetchone()["c"]
            assert works == 1, "La Work contenedora debe ser única por trabajo"
            resources = conn.execute(
                "SELECT COUNT(*) AS c FROM resources WHERE work_id = ?", (f"pw-{work_id}",)
            ).fetchone()["c"]
            assert resources == 2


# --------------------------------------------------------------------------
# §7 Reglas de acceso a Resource / File
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_private_work_of_another_user_cannot_be_added(integration_settings: Settings, monkeypatch):
    profiles = {"token-a": _profile("acc-a"), "token-b": _profile("acc-b")}
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        a = {"Authorization": "Bearer token-a"}
        b = {"Authorization": "Bearer token-b"}

        with db_connect(integration_settings) as conn:
            _insert_chain(conn, work_id="w-priv", resource_id="r-priv",
                          file_id="f-priv", owner_sub="acc-b")

        space_a = client.post("/api/v1/spaces", headers=a,
                              json={"space_type": "personal", "name": "A"}).json()["id"]
        work_a = client.post(f"/api/v1/spaces/{space_a}/preparation-works",
                             headers=a, json={"title": "t"}).json()["id"]

        r = client.post(
            f"/api/v1/spaces/{space_a}/preparation-works/{work_a}/items",
            headers=a, json={"work_id": "w-priv", "resource_id": "r-priv"},
        )
        assert r.status_code == 403, "Una Work privada ajena no puede incorporarse"
        assert client.post(
            f"/api/v1/spaces/{space_a}/preparation-works/{work_a}/files",
            headers=a, json={"file_id": "f-priv"},
        ).status_code == 403


@pytest.mark.integration
def test_group_shared_resource_usable_by_members(integration_settings: Settings, monkeypatch):
    """Una Resource compartida con el grupo se usa en sus espacios autorizados."""
    profiles = {
        "token-mgr": _profile("shr-mgr"),
        "token-mem": _profile("shr-mem"),
        "token-out": _profile("shr-out"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        mem = {"Authorization": "Bearer token-mem"}
        out = {"Authorization": "Bearer token-out"}

        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Shared"}).json()
        group_id, join_code = grp["id"], grp["join_code"]
        assert client.post("/api/v1/groups/join", headers=mem,
                           json={"code": join_code}).status_code == 200

        with db_connect(integration_settings) as conn:
            _insert_chain(conn, work_id="w-shr", resource_id="r-shr",
                          file_id="f-shr", group_id=group_id)

        space_id = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "group", "group_id": group_id, "name": "General"},
        ).json()["id"]
        work_id = client.post(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=mgr,
            json={"title": "programa"},
        ).json()["id"]

        # El manager (gestor) puede incorporarla
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/items",
            headers=mgr, json={"work_id": "w-shr", "resource_id": "r-shr"},
        ).status_code == 201
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files",
            headers=mgr, json={"file_id": "f-shr"},
        ).status_code == 201

        # Un outsider no puede usarla en su propio espacio personal
        out_space = client.post("/api/v1/spaces", headers=out,
                                json={"space_type": "personal", "name": "out"}).json()["id"]
        out_work = client.post(f"/api/v1/spaces/{out_space}/preparation-works",
                               headers=out, json={"title": "x"}).json()["id"]
        assert client.post(
            f"/api/v1/spaces/{out_space}/preparation-works/{out_work}/files",
            headers=out, json={"file_id": "f-shr"},
        ).status_code == 403


@pytest.mark.integration
def test_section_restricted_resource_respects_section_membership(
    integration_settings: Settings, monkeypatch
):
    """Un miembro de otra sección no accede a una Resource restringida."""
    profiles = {
        "token-mgr": _profile("sec-mgr"),
        "token-s1": _profile("sec-one"),
        "token-s2": _profile("sec-two"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        s1 = {"Authorization": "Bearer token-s1"}
        s2 = {"Authorization": "Bearer token-s2"}

        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Sec"}).json()
        group_id, join_code = grp["id"], grp["join_code"]

        # Las secciones se crean directamente (no hay endpoint público de alta)
        for headers in (s1, s2):
            assert client.post("/api/v1/groups/join", headers=headers,
                               json={"code": join_code}).status_code == 200

        with db_connect(integration_settings) as conn:
            conn.execute(
                "INSERT INTO group_sections (id, group_id, name, code, active, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                ("sec-1", group_id, "Soprano", "soprano", 1,
                 "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
            )
            conn.execute(
                "INSERT INTO group_sections (id, group_id, name, code, active, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                ("sec-2", group_id, "Tenor", "tenor", 1,
                 "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
            )
            conn.commit()
        sec1 = {"id": "sec-1"}
        sec2 = {"id": "sec-2"}

        # s1 -> sección 1, s2 -> sección 2
        assert client.patch(f"/api/v1/groups/{group_id}/members/sec-one", headers=mgr,
                            json={"section_id": sec1["id"]}).status_code == 200
        assert client.patch(f"/api/v1/groups/{group_id}/members/sec-two", headers=mgr,
                            json={"section_id": sec2["id"]}).status_code == 200

        # Resource restringida a la sección 1
        with db_connect(integration_settings) as conn:
            _insert_chain(conn, work_id="w-sec", resource_id="r-sec", file_id="f-sec",
                          group_id=group_id, section_id=sec1["id"])

        space_id = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "group", "group_id": group_id, "name": "General"},
        ).json()["id"]
        work_id = client.post(f"/api/v1/spaces/{space_id}/preparation-works",
                              headers=mgr, json={"title": "p"}).json()["id"]

        # El manager accede a todas las secciones
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files",
            headers=mgr, json={"file_id": "f-sec"},
        ).status_code == 201

        # El miembro de la sección 2 no puede
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files",
            headers=s2, json={"file_id": "f-sec"},
        ).status_code == 403

        # El miembro de la sección 1 sí (sólo si puede gestionar preparación,
        # que es lo que exige este endpoint)
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files",
            headers=s1, json={"file_id": "f-sec"},
        ).status_code == 403, "Un miembro sin rol de gestión no añade archivos"


@pytest.mark.integration
def test_download_rechecks_authorization(integration_settings: Settings, monkeypatch):
    """La descarga valida permisos aunque el usuario conozca el identificador."""
    profiles = {
        "token-mgr": _profile("dl-mgr"),
        "token-out": _profile("dl-out"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        out = {"Authorization": "Bearer token-out"}

        group_id, join_code, space_id, work_id = _setup_group_space(client, mgr)
        up = client.post(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}/files",
            headers=mgr,
            files=[("files", ("privado.mxl", b"secreto", "application/xml"))],
        )
        file_id = up.json()["files"][0]["file_id"]

        # El propietario descarga
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}"
            f"/files/{file_id}/download",
            headers=mgr,
        ).status_code == 200

        # Un tercero no, ni siquiera conociendo file_id y work_id
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}"
            f"/files/{file_id}/download",
            headers=out,
        ).status_code == 403

        # Un trabajo de otro espacio no sirve para descargarlo
        other_space = client.post("/api/v1/spaces", headers=out,
                                  json={"space_type": "personal", "name": "otro"}).json()["id"]
        other_work = client.post(f"/api/v1/spaces/{other_space}/preparation-works",
                                 headers=out, json={"title": "ow"}).json()["id"]
        assert client.get(
            f"/api/v1/spaces/{other_space}/preparation-works/{other_work}"
            f"/files/{file_id}/download",
            headers=out,
        ).status_code == 404