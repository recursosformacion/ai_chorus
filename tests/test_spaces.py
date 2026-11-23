"""Espacios de trabajo (personal / grupo / proyecto) y trabajos de preparación.

Cubre:
  1.  Alta de espacio personal por un músico independiente.
  2.  Varios trabajos de preparación en el mismo espacio.
  3.  Obras y recursos en esos trabajos (integridad Work -> Resource).
  4.  Referencias a archivos: alta y baja sin tocar el archivo físico.
  5.  Aislamiento: otro usuario no ve ni modifica el espacio personal.
  6.  Conversión de espacio personal a grupo conservando datos.
  7.  Miembros del grupo acceden según su rol.
  8.  Un usuario ajeno no crea espacios en un grupo que no administra.
  9.  No se pueden asociar archivos privados de otro usuario.
  10. No se pueden manipular recursos de otra obra.
  11. Varios trabajos simultáneos en un grupo.
  12. Permiso de dirección musical (histórico) sigue funcionando.
  13. Accesos cruzados entre espacios y trabajos rechazados.
  14. Compatibilidad de las rutas antiguas de grupo.
"""

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


def _insert_chain(conn, *, work_id, resource_id, file_id, owner_sub=None, group_id=None):
    """Inserta Work -> Resource -> File respetando el modelo V6."""
    now = "2026-01-01 00:00:00"
    conn.execute(
        "INSERT INTO works (id, title, created_at, updated_at, required_resource_id, owner_sub) "
        "VALUES (?,?,?,?,?,?)",
        (work_id, f"Work {work_id}", now, now, resource_id, owner_sub),
    )
    conn.execute(
        "INSERT INTO resources "
        "(id, work_id, resource_type, created_at, updated_at, required_file_id, group_id) "
        "VALUES (?,?,?,?,?,?,?)",
        (resource_id, work_id, "score", now, now, file_id, group_id),
    )
    conn.execute(
        "INSERT INTO files "
        "(id, resource_id, name, status, storage_pointer, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (file_id, resource_id, f"{file_id}.musicxml", "registered", f"private/{file_id}", now, now),
    )
    conn.commit()


# --------------------------------------------------------------------------
# 1-5: espacio personal de un músico independiente
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_personal_space_lifecycle_and_isolation(integration_settings: Settings, monkeypatch):
    """Un músico independiente trabaja sin grupo y nadie más accede a su espacio."""
    profiles = {
        "token-owner": _profile("owner-1"),
        "token-other": _profile("other-1"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        own = {"Authorization": "Bearer token-owner"}
        other = {"Authorization": "Bearer token-other"}

        # 1. Alta de espacio personal (sin grupo)
        r = client.post(
            "/api/v1/spaces",
            headers=own,
            json={"space_type": "personal", "name": "Mi estudio"},
        )
        assert r.status_code == 201, r.text
        space_id = r.json()["id"]
        assert r.json()["space_type"] == "personal"
        assert r.json()["group_id"] is None

        # Un espacio personal no puede llevar group_id
        assert client.post(
            "/api/v1/spaces",
            headers=own,
            json={"space_type": "personal", "group_id": "x", "name": "malo"},
        ).status_code == 400

        # 2. Varios trabajos simultáneos en el mismo espacio
        work_ids = []
        for title in ("Concierto A", "Concierto B", "Audición"):
            rw = client.post(
                f"/api/v1/spaces/{space_id}/preparation-works",
                headers=own,
                json={"title": title, "destination_type": "program"},
            )
            assert rw.status_code == 201, rw.text
            work_ids.append(rw.json()["id"])
        assert len(set(work_ids)) == 3
        assert len(client.get(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=own
        ).json()) == 3

        # 3. Añadir obra + recurso propios
        settings = integration_settings
        with db_connect(settings) as conn:
            _insert_chain(
                conn,
                work_id="work-own",
                resource_id="res-own",
                file_id="file-own",
                owner_sub="owner-1",
            )

        r_item = client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_ids[0]}/items",
            headers=own,
            json={"work_id": "work-own", "resource_id": "res-own", "voice_label": "Soprano"},
        )
        assert r_item.status_code == 201, r_item.text
        item_id = r_item.json()["id"]
        assert len(client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_ids[0]}/items", headers=own
        ).json()) == 1

        # 4. Referencias a archivos: alta y baja
        r_ref = client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_ids[0]}/files",
            headers=own,
            json={"file_id": "file-own", "purpose": "score"},
        )
        assert r_ref.status_code == 201, r_ref.text
        ref_id = r_ref.json()["id"]

        # La baja elimina sólo la referencia: el archivo sigue existiendo
        assert client.delete(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_ids[0]}/files/{ref_id}",
            headers=own,
        ).status_code == 200
        with db_connect(settings) as conn:
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM preparation_work_files WHERE id = ?", (ref_id,)
            ).fetchone()["c"] == 0
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE id = ?", ("file-own",)
            ).fetchone()["c"] == 1

        # 5. Otro usuario no ve ni modifica el espacio personal
        assert client.get(f"/api/v1/spaces/{space_id}", headers=other).status_code == 403
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=other
        ).status_code == 403
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works",
            headers=other,
            json={"title": "intruso"},
        ).status_code == 403
        assert client.patch(
            f"/api/v1/spaces/{space_id}", headers=other, json={"name": "robado"}
        ).status_code == 403
        # El listado del otro usuario no incluye el espacio ajeno
        assert space_id not in [s["id"] for s in client.get("/api/v1/spaces", headers=other).json()]


# --------------------------------------------------------------------------
# 6-7: conversión de personal a grupo
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_convert_personal_space_to_group_preserves_data(integration_settings: Settings, monkeypatch):
    """La conversión conserva trabajos, items y referencias; el grupo hereda la membresía."""
    profiles = {
        "token-owner": _profile("conv-owner"),
        "token-member": _profile("conv-member"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        own = {"Authorization": "Bearer token-owner"}
        member = {"Authorization": "Bearer token-member"}

        space_id = client.post(
            "/api/v1/spaces", headers=own,
            json={"space_type": "personal", "name": "Mi espacio"},
        ).json()["id"]

        work_id = client.post(
            f"/api/v1/spaces/{space_id}/preparation-works",
            headers=own, json={"title": "Programa"},
        ).json()["id"]

        with db_connect(integration_settings) as conn:
            _insert_chain(conn, work_id="w-conv", resource_id="r-conv", file_id="f-conv",
                          owner_sub="conv-owner")

        client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/items",
            headers=own, json={"work_id": "w-conv", "resource_id": "r-conv"},
        )
        ref_id = client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files",
            headers=own, json={"file_id": "f-conv"},
        ).json()["id"]

        # 6. Conversión a grupo
        rc = client.post(
            f"/api/v1/spaces/{space_id}/convert",
            headers=own,
            json={"target_type": "group", "name": "Coral Nuevo"},
        )
        assert rc.status_code == 201, rc.text
        converted = rc.json()
        assert converted["space_type"] == "group"
        assert converted["group_id"]

        # 7. Los datos se conservan tras la conversión
        assert len(client.get(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=own
        ).json()) == 1
        assert len(client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/items", headers=own
        ).json()) == 1
        assert len(client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files", headers=own
        ).json()) == 1
        # La referencia sigue apuntando al mismo archivo
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}/files", headers=own
        ).json()[0]["id"] == ref_id

        # El propietario es manager del nuevo grupo
        group_id = converted["group_id"]
        with db_connect(integration_settings) as conn:
            join_code = conn.execute(
                "SELECT join_code FROM groups WHERE id = ?", (group_id,)
            ).fetchone()["join_code"]

        # Un miembro puede unirse y entonces ve el espacio (permiso de consulta)
        assert client.post(
            "/api/v1/groups/join", headers=member, json={"code": join_code}
        ).status_code == 200
        assert client.get(f"/api/v1/spaces/{space_id}", headers=member).status_code == 200
        # Pero no puede crear trabajos (no es manager ni director)
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works",
            headers=member, json={"title": "nope"},
        ).status_code == 403


# --------------------------------------------------------------------------
# 8-11: espacios de grupo, autorización y aislamiento
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_group_space_authorization_and_multiple_works(integration_settings: Settings, monkeypatch):
    """Sólo managers crean espacios de grupo; varios trabajos aislados; accesos cruzados."""
    profiles = {
        "token-mgr": _profile("g-mgr"),
        "token-mem": _profile("g-mem"),
        "token-out": _profile("g-out"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        mem = {"Authorization": "Bearer token-mem"}
        out = {"Authorization": "Bearer token-out"}

        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Test"}).json()
        group_id = grp["id"]
        join_code = grp["join_code"]
        assert client.post("/api/v1/groups/join", headers=mem,
                           json={"code": join_code}).status_code == 200

        # 8. Un usuario ajeno no crea espacios en un grupo que no administra
        assert client.post(
            "/api/v1/spaces", headers=out,
            json={"space_type": "group", "group_id": group_id, "name": "Intruso"},
        ).status_code == 403
        # Ni siquiera un miembro ordinario
        assert client.post(
            "/api/v1/spaces", headers=mem,
            json={"space_type": "group", "group_id": group_id, "name": "Miembro"},
        ).status_code == 403
        # El manager sí
        r_space = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "group", "group_id": group_id, "name": "Espacio grupo"},
        )
        assert r_space.status_code == 201, r_space.text
        space_id = r_space.json()["id"]

        # 11. Varios trabajos simultáneos, aislados entre sí
        wa = client.post(f"/api/v1/spaces/{space_id}/preparation-works",
                         headers=mgr, json={"title": "A"}).json()["id"]
        wb = client.post(f"/api/v1/spaces/{space_id}/preparation-works",
                         headers=mgr, json={"title": "B"}).json()["id"]

        with db_connect(integration_settings) as conn:
            _insert_chain(conn, work_id="w-a", resource_id="r-a", file_id="f-a", group_id=group_id)
            _insert_chain(conn, work_id="w-b", resource_id="r-b", file_id="f-b", group_id=group_id)

        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{wa}/items",
            headers=mgr, json={"work_id": "w-a", "resource_id": "r-a"},
        ).status_code == 201
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works/{wb}/items",
            headers=mgr, json={"work_id": "w-b", "resource_id": "r-b"},
        ).status_code == 201

        # Cada trabajo mantiene su propia selección
        assert len(client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{wa}/items", headers=mgr
        ).json()) == 1
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{wa}/items", headers=mgr
        ).json()[0]["work_id"] == "w-a"

        # Modificar B no afecta a A
        client.patch(
            f"/api/v1/spaces/{space_id}/preparation-works/{wb}",
            headers=mgr, json={"title": "B modificado", "status": "ready"},
        )
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{wa}", headers=mgr
        ).json()["title"] == "A"
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{wb}", headers=mgr
        ).json()["title"] == "B modificado"

        # Eliminar un trabajo no toca Works/Resources/Files
        assert client.delete(
            f"/api/v1/spaces/{space_id}/preparation-works/{wa}", headers=mgr
        ).status_code == 200
        with db_connect(integration_settings) as conn:
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM works WHERE id = 'w-a'"
            ).fetchone()["c"] == 1
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM resources WHERE id = 'r-a'"
            ).fetchone()["c"] == 1
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE id = 'f-a'"
            ).fetchone()["c"] == 1
            # El item en cascada sí desaparece
            assert conn.execute(
                "SELECT COUNT(*) AS c FROM preparation_work_items WHERE preparation_work_id = ?",
                (wa,),
            ).fetchone()["c"] == 0

        # 13. Accesos cruzados: el member no edita; el outsider no ve nada
        assert client.patch(
            f"/api/v1/spaces/{space_id}/preparation-works/{wb}",
            headers=mem, json={"title": "hack"},
        ).status_code == 403
        assert client.delete(
            f"/api/v1/spaces/{space_id}/preparation-works/{wb}", headers=mem
        ).status_code == 403
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{wb}", headers=out
        ).status_code == 403
        # El member sí puede consultar
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{wb}", headers=mem
        ).status_code == 200


# --------------------------------------------------------------------------
# 9-10: integridad de recursos y archivos ajenos
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_cross_user_resources_and_files_are_rejected(integration_settings: Settings, monkeypatch):
    """No se usan recursos ajenos ni archivos privados de otro usuario."""
    profiles = {
        "token-a": _profile("own-a"),
        "token-b": _profile("own-b"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        a = {"Authorization": "Bearer token-a"}
        b = {"Authorization": "Bearer token-b"}

        with db_connect(integration_settings) as conn:
            # Cadena perteneciente a B (privada)
            _insert_chain(conn, work_id="wb", resource_id="rb", file_id="fb", owner_sub="own-b")
            # Cadena perteneciente a A
            _insert_chain(conn, work_id="wa", resource_id="ra", file_id="fa", owner_sub="own-a")
            # Otra obra con otro recurso (para probar coherencia Work/Resource)
            _insert_chain(conn, work_id="wa2", resource_id="ra2", file_id="fa2", owner_sub="own-a")

        space_a = client.post("/api/v1/spaces", headers=a,
                              json={"space_type": "personal", "name": "A"}).json()["id"]
        work_a = client.post(f"/api/v1/spaces/{space_a}/preparation-works",
                             headers=a, json={"title": "trabajo A"}).json()["id"]

        # 9. B no puede adjuntar su archivo privado al espacio de A
        #    (B además no tiene acceso al espacio, así que se prueba con A
        #     intentando usar un archivo que no le pertenece)
        assert client.post(
            f"/api/v1/spaces/{space_a}/preparation-works/{work_a}/files",
            headers=a, json={"file_id": "fb"},
        ).status_code == 403
        # Su propio archivo sí
        assert client.post(
            f"/api/v1/spaces/{space_a}/preparation-works/{work_a}/files",
            headers=a, json={"file_id": "fa"},
        ).status_code == 201

        # 10. No se puede asociar un recurso de otra obra
        assert client.post(
            f"/api/v1/spaces/{space_a}/preparation-works/{work_a}/items",
            headers=a, json={"work_id": "wa", "resource_id": "ra2"},
        ).status_code == 400
        # Combinación coherente sí
        assert client.post(
            f"/api/v1/spaces/{space_a}/preparation-works/{work_a}/items",
            headers=a, json={"work_id": "wa", "resource_id": "ra"},
        ).status_code == 201
        # Recurso ajeno (de B) rechazado
        assert client.post(
            f"/api/v1/spaces/{space_a}/preparation-works/{work_a}/items",
            headers=a, json={"work_id": "wb", "resource_id": "rb"},
        ).status_code == 403


# --------------------------------------------------------------------------
# 12: permiso de dirección musical
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_musical_director_can_manage_preparation(integration_settings: Settings, monkeypatch):
    """El director musical mantiene su permiso histórico de preparación."""
    profiles = {
        "token-mgr": _profile("dir-mgr"),
        "token-dir": _profile("dir-1"),
        "token-mem": _profile("dir-mem"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        director = {"Authorization": "Bearer token-dir"}
        member = {"Authorization": "Bearer token-mem"}

        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Coral Director"}).json()
        group_id, join_code = grp["id"], grp["join_code"]

        # Rol musical de dirección creado por el manager
        role = client.post(
            f"/api/v1/groups/{group_id}/roles",
            headers=mgr,
            json={"scope": "musical", "code": "director", "name": "Director"},
        ).json()

        assert client.post("/api/v1/groups/join", headers=director,
                           json={"code": join_code}).status_code == 200
        assert client.post("/api/v1/groups/join", headers=member,
                           json={"code": join_code}).status_code == 200

        # Asignar el rol de director
        assert client.patch(
            f"/api/v1/groups/{group_id}/members/dir-1",
            headers=mgr,
            json={"musical_role_id": role["id"]},
        ).status_code == 200

        space_id = client.post(
            "/api/v1/spaces", headers=mgr,
            json={"space_type": "group", "group_id": group_id, "name": "Espacio"},
        ).json()["id"]

        # El director crea y edita trabajos
        rw = client.post(f"/api/v1/spaces/{space_id}/preparation-works",
                         headers=director, json={"title": "Programa del director"})
        assert rw.status_code == 201, rw.text
        work_id = rw.json()["id"]
        assert client.patch(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}",
            headers=director, json={"status": "ready"},
        ).status_code == 200

        # Pero NO gestiona el espacio (nombre) ni a los miembros
        assert client.patch(
            f"/api/v1/spaces/{space_id}", headers=director, json={"name": "reescrito"}
        ).status_code == 403

        # Un miembro ordinario no puede crear trabajos
        assert client.post(
            f"/api/v1/spaces/{space_id}/preparation-works",
            headers=member, json={"title": "no"},
        ).status_code == 403


# --------------------------------------------------------------------------
# 14: compatibilidad de las rutas antiguas de grupo
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_legacy_group_routes_use_same_space(integration_settings: Settings, monkeypatch):
    """Las rutas /groups/{id}/preparation-works operan sobre el mismo espacio."""
    profiles = {
        "token-mgr": _profile("leg-mgr"),
        "token-mem": _profile("leg-mem"),
        "token-out": _profile("leg-out"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        mgr = {"Authorization": "Bearer token-mgr"}
        mem = {"Authorization": "Bearer token-mem"}
        out = {"Authorization": "Bearer token-out"}

        grp = client.post("/api/v1/groups", headers=mgr, json={"name": "Grupo Legacy"}).json()
        group_id, join_code = grp["id"], grp["join_code"]
        assert client.post("/api/v1/groups/join", headers=mem,
                           json={"code": join_code}).status_code == 200

        # Crear por la ruta antigua
        legacy = client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mgr, json={"title": "Ruta antigua"},
        )
        assert legacy.status_code == 201, legacy.text
        work_id = legacy.json()["id"]
        space_id = legacy.json()["space_id"]
        assert space_id

        # Visible por la ruta nueva (mismo espacio)
        assert len(client.get(
            f"/api/v1/spaces/{space_id}/preparation-works", headers=mgr
        ).json()) == 1
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}", headers=mgr
        ).status_code == 200

        # Permisos idénticos en ambas rutas
        assert client.post(
            f"/api/v1/groups/{group_id}/preparation-works",
            headers=mem, json={"title": "no"},
        ).status_code == 403
        assert client.get(
            f"/api/v1/groups/{group_id}/preparation-works", headers=out
        ).status_code == 403
        assert client.get(
            f"/api/v1/groups/{group_id}/preparation-works", headers=mem
        ).status_code == 200

        # Borrado por la ruta antigua
        assert client.delete(
            f"/api/v1/groups/{group_id}/preparation-works/{work_id}", headers=mgr
        ).status_code == 200
        assert client.get(
            f"/api/v1/spaces/{space_id}/preparation-works/{work_id}", headers=mgr
        ).status_code == 404


# --------------------------------------------------------------------------
# Migración 040: debe abortar si quedan trabajos sin asociar
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_migration_040_aborts_when_rows_cannot_be_migrated(integration_settings: Settings):
    """Con un trabajo sin `space_id`, el paso de aborto de la migración 040 falla.

    Se extrae el bloque real de la migración (entre los marcadores BEGIN/END
    ABORT CHECK) y se ejecuta: debe lanzar error y no completarse.
    """
    from pathlib import Path

    from app.db import _execute_sql_script

    settings = integration_settings
    work_id = "orphan-prep-1"

    # Estado previo: un trabajo sin espacio asociable (space_id NULL)
    with db_connect(settings) as conn:
        conn.execute(
            "INSERT INTO spaces (id, space_type, owner_sub, group_id, name, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("space-orphan-test", "personal", "mig-user", None, "huerfano",
             "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
        )
        conn.execute("ALTER TABLE preparation_works MODIFY COLUMN space_id VARCHAR(191) NULL")
        conn.execute(
            "INSERT INTO preparation_works "
            "(id, space_id, title, folder_path, status, destination_type, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (work_id, None, "Sin espacio", "preparation/x/y", "preparing",
             "repertoire", "mig-user", "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
        )
        conn.commit()

    # Extraer el bloque de aborto real de la migración
    migration = Path("migrations/mysql/040_migrate_preparation_works_to_spaces.sql").read_text("utf-8")
    begin = migration.index("-- >>> BEGIN ABORT CHECK 040")
    end = migration.index("-- <<< END ABORT CHECK 040")
    abort_block = migration[begin:end]
    assert "PREPARE stmt" in abort_block, "El bloque de aborto debe preparar y ejecutar la sentencia"

    raised = False
    try:
        with db_connect(settings) as conn:
            _execute_sql_script(conn, abort_block, is_mysql=True)
            conn.commit()
    except Exception as exc:  # se espera error 1146 (tabla inexistente)
        raised = True
        assert "1146" in str(exc) or "doesn't exist" in str(exc).lower()

    assert raised, "La migración 040 debe abortar si quedan trabajos sin migrar"

    # Restaurar el esquema y los datos para no contaminar otros tests
    with db_connect(settings) as conn:
        conn.execute("DELETE FROM preparation_work_items WHERE preparation_work_id = ?", (work_id,))
        conn.execute("DELETE FROM preparation_works WHERE id = ?", (work_id,))
        conn.execute("DELETE FROM spaces WHERE id = ?", ("space-orphan-test",))
        conn.execute("ALTER TABLE preparation_works MODIFY COLUMN space_id VARCHAR(191) NOT NULL")
        conn.commit()

# --------------------------------------------------------------------------
# Proyectos personales independientes (sin crear un grupo)
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_user_can_create_multiple_private_projects(integration_settings: Settings, monkeypatch):
    """Un particular puede mantener varios proyectos privados y aislados."""
    profiles = {
        "token-owner": _profile("project-owner"),
        "token-other": _profile("project-other"),
    }
    install_fake_auth(monkeypatch, profiles, integration_settings.auth_base_url)

    with TestClient(create_app(integration_settings)) as client:
        own = {"Authorization": "Bearer token-owner"}
        other = {"Authorization": "Bearer token-other"}

        created = []
        for name in ("Misa de Navidad", "Cuarteto de cuerda", "Estudio personal"):
            response = client.post(
                "/api/v1/spaces",
                headers=own,
                json={"space_type": "project", "name": name},
            )
            assert response.status_code == 201, response.text
            project = response.json()
            assert project["space_type"] == "project"
            assert project["owner_sub"] == "project-owner"
            assert project["group_id"] is None
            created.append(project)

        listed = client.get("/api/v1/spaces", headers=own)
        assert listed.status_code == 200
        listed_ids = {space["id"] for space in listed.json()}
        assert {space["id"] for space in created} <= listed_ids

        # Cada proyecto admite su propio trabajo de preparación.
        response = client.post(
            f"/api/v1/spaces/{created[0]['id']}/preparation-works",
            headers=own,
            json={"title": "Programa de Navidad", "destination_type": "program"},
        )
        assert response.status_code == 201, response.text
        work_id = response.json()["id"]

        # Los archivos de preparación se guardan en el espacio privado,
        # no se incorporan a la biblioteca personal.
        upload = client.post(
            f"/api/v1/spaces/{created[0]['id']}/preparation-works/{work_id}/uploads",
            headers=own,
            files=[("files", ("partitura.pdf", b"%PDF-1.4 test", "application/pdf"))],
            data={"parts": '[{"purpose":"score","part_label":"Soprano"}]'},
        )
        assert upload.status_code == 201, upload.text
        listed_files = client.get(
            f"/api/v1/spaces/{created[0]['id']}/preparation-works/{work_id}/files",
            headers=own,
        )
        assert listed_files.status_code == 200
        assert len(listed_files.json()) == 1

        # Otro usuario no puede descubrir ni abrir los proyectos privados.
        other_spaces = client.get("/api/v1/spaces", headers=other)
        assert other_spaces.status_code == 200
        assert not ({space["id"] for space in created} & {
            space["id"] for space in other_spaces.json()
        })
        assert client.get(
            f"/api/v1/spaces/{created[0]['id']}", headers=other
        ).status_code == 403
        assert client.post(
            f"/api/v1/spaces/{created[0]['id']}/preparation-works",
            headers=other,
            json={"title": "No autorizado"},
        ).status_code == 403
