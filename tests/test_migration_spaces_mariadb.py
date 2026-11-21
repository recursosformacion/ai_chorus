"""Migración 040/041 sobre MariaDB real: conservación de datos y aborto seguro.

Cada test reconstruye el estado "antiguo" (preparation_works con group_id),
ejecuta las migraciones reales y verifica los datos antes y después. El
esquema canónico se restaura al terminar mediante rebuild_test_db.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from app.config import Settings
from app.db import _execute_sql_script, connect as db_connect

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "mysql"

OLD_SCHEMA_MIGRATIONS = ["037_spaces.sql", "038_preparation_work_items.sql",
                         "039_preparation_work_files.sql"]
FINAL_MIGRATIONS = ["040_migrate_preparation_works_to_spaces.sql",
                    "041_consolidate_spaces.sql"]


def _script(name: str) -> str:
    return (MIGRATIONS_DIR / name).read_text("utf-8")


def _run(conn, name: str) -> None:
    _execute_sql_script(conn, _script(name), is_mysql=True)
    conn.commit()


def _restore_canonical_schema(settings: Settings) -> None:
    """Devuelve la BD a su esquema canónico (silencioso)."""
    import scripts.rebuild_test_db as rebuild

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = rebuild.main()
    assert code == 0, f"rebuild falló: {buffer.getvalue()[-800:]}"


@pytest.fixture
def legacy_schema(integration_settings: Settings):
    """Deja la BD en estado antiguo y la restaura al terminar."""
    settings = integration_settings
    with db_connect(settings) as conn:
        conn.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in ("preparation_work_files", "preparation_work_items",
                      "preparation_works", "spaces"):
            conn.execute(f"DROP TABLE IF EXISTS `{table}`")
        conn.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()

    try:
        yield settings
    finally:
        _restore_canonical_schema(settings)


def _insert_chain(conn, *, work_id, resource_id, file_id, owner_sub=None, group_id=None):
    now = "2026-01-01 00:00:00"
    conn.execute(
        "INSERT INTO works (id, title, created_at, updated_at, required_resource_id, owner_sub) "
        "VALUES (?,?,?,?,?,?)",
        (work_id, f"Work {work_id}", now, now, resource_id, owner_sub),
    )
    conn.execute(
        "INSERT INTO resources "
        "(id, work_id, resource_type, created_at, updated_at, required_file_id, "
        " group_id, material_status) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (resource_id, work_id, "score", now, now, file_id, group_id, "registered"),
    )
    conn.execute(
        "INSERT INTO files "
        "(id, resource_id, name, status, storage_pointer, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (file_id, resource_id, f"{file_id}.mxl", "registered", f"private/{file_id}", now, now),
    )


def _insert_group(conn, group_id: str, name: str, owner: str = "mig-owner") -> None:
    now = "2026-01-01 00:00:00"
    conn.execute(
        "INSERT INTO groups (id, entity_id, name, timezone, created_by, join_code, "
        "created_at, updated_at, kind, slug, status, editorial_mode) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (group_id, owner, name, "Europe/Madrid", owner, f"JC{group_id[:6]}",
         now, now, "grupo", group_id, "active", "manual"),
    )


def _insert_legacy_work(conn, work_id: str, group_id: str, title: str,
                        folder: str, created_by: str = "mig-owner") -> None:
    now = "2026-01-01 00:00:00"
    conn.execute(
        "INSERT INTO preparation_works "
        "(id, group_id, title, composer, folder_path, status, destination_type, "
        " event_name, event_date, notes, created_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (work_id, group_id, title, "Compositor", folder, "preparing", "repertoire",
         "Evento", "2026-05-05", "nota", created_by, now, now),
    )


# --------------------------------------------------------------------------
@pytest.mark.integration
def test_migration_runs_on_empty_legacy_database(legacy_schema: Settings):
    """1. Base antigua vacía: las migraciones aplican sin datos."""
    settings = legacy_schema
    with db_connect(settings) as conn:
        _run(conn, "035_preparation_works.sql")
        for name in OLD_SCHEMA_MIGRATIONS + FINAL_MIGRATIONS:
            _run(conn, name)

        # Esquema final correcto
        row = conn.execute(
            "SELECT IS_NULLABLE AS n FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_works' "
            "AND COLUMN_NAME = 'space_id'"
        ).fetchone()
        assert row["n"] == "NO"
        leftover = conn.execute(
            "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_works' "
            "AND COLUMN_NAME = 'group_id'"
        ).fetchone()["c"]
        assert leftover == 0
        assert conn.execute("SELECT COUNT(*) AS c FROM preparation_works").fetchone()["c"] == 0


@pytest.mark.integration
def test_migration_preserves_work_data_across_groups(legacy_schema: Settings):
    """2 y 4. Varios grupos con varios trabajos: los datos se conservan."""
    settings = legacy_schema
    with db_connect(settings) as conn:
        _run(conn, "035_preparation_works.sql")

        _insert_group(conn, "g1", "Grupo Uno")
        _insert_group(conn, "g2", "Grupo Dos")
        _insert_legacy_work(conn, "pw1", "g1", "Misa en Do", "preparation/g1/pw1")
        _insert_legacy_work(conn, "pw2", "g1", "Requiem", "preparation/g1/pw2")
        _insert_legacy_work(conn, "pw3", "g2", "Stabat Mater", "preparation/g2/pw3")
        conn.commit()

        # Estado ANTES
        before = {
            row["id"]: (row["group_id"], row["title"], row["folder_path"],
                        row["composer"], row["status"], row["event_name"],
                        row["event_date"], row["notes"], row["created_by"])
            for row in conn.execute("SELECT * FROM preparation_works").fetchall()
        }
        assert set(before) == {"pw1", "pw2", "pw3"}

        for name in OLD_SCHEMA_MIGRATIONS + FINAL_MIGRATIONS:
            _run(conn, name)

        # Estado DESPUÉS
        rows = {row["id"]: row for row in conn.execute(
            "SELECT * FROM preparation_works"
        ).fetchall()}
        assert set(rows) == {"pw1", "pw2", "pw3"}, "No debe perderse ningún trabajo"

        for work_id, (old_group, title, folder, composer, status, ev_name, ev_date,
                      notes, created_by) in before.items():
            row = rows[work_id]
            # Metadatos intactos
            assert row["title"] == title
            assert row["folder_path"] == folder
            assert row["composer"] == composer
            assert row["status"] == status
            assert row["event_name"] == ev_name
            assert row["event_date"] == ev_date
            assert row["notes"] == notes
            assert row["created_by"] == created_by
            # space_id apunta al espacio general de su grupo original
            space = conn.execute(
                "SELECT space_type, group_id, owner_sub FROM spaces WHERE id = ?",
                (row["space_id"],),
            ).fetchone()
            assert space is not None
            assert space["space_type"] == "group"
            assert space["group_id"] == old_group, "El trabajo cambió de grupo"
            assert space["owner_sub"] is None

        # group_id eliminado
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_works' "
            "AND COLUMN_NAME = 'group_id'"
        ).fetchone()["c"] == 0

        # Un único espacio general por grupo
        for group_id in ("g1", "g2"):
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM spaces WHERE group_id = ? AND space_type = 'group'",
                (group_id,),
            ).fetchone()["c"]
            assert count == 1

        # Reejecución idempotente: no altera nada
        snapshot = {
            row["id"]: (row["space_id"], row["title"], row["folder_path"])
            for row in conn.execute("SELECT * FROM preparation_works").fetchall()
        }
        for name in FINAL_MIGRATIONS:
            _run(conn, name)
        after = {
            row["id"]: (row["space_id"], row["title"], row["folder_path"])
            for row in conn.execute("SELECT * FROM preparation_works").fetchall()
        }
        assert after == snapshot, "La reejecución alteró los datos"

        # Una segunda ejecución no crea espacios duplicados
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM spaces WHERE space_type = 'group'"
        ).fetchone()["c"] == 2


@pytest.mark.integration
def test_migration_preserves_items_and_file_references(legacy_schema: Settings):
    """3. Trabajos con items y archivos: se conservan tras la migración."""
    settings = legacy_schema
    with db_connect(settings) as conn:
        _run(conn, "035_preparation_works.sql")
        for name in ("037_spaces.sql", "038_preparation_work_items.sql",
                     "039_preparation_work_files.sql"):
            _run(conn, name)

        _insert_group(conn, "gi", "Grupo Items")
        _insert_legacy_work(conn, "pwi", "gi", "Trabajo con items", "preparation/gi/pwi")
        _insert_chain(conn, work_id="wi", resource_id="ri", file_id="fi", owner_sub="mig-owner")
        conn.commit()

        now = "2026-01-02 00:00:00"
        conn.execute(
            "INSERT INTO preparation_work_items "
            "(id, preparation_work_id, work_id, resource_id, voice_label, sort_order, "
            " status, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("itemi", "pwi", "wi", "ri", "Soprano", 1, "pending", "nota item", now, now),
        )
        conn.execute(
            "INSERT INTO preparation_work_files "
            "(id, preparation_work_id, file_id, purpose, sort_order, created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("refi", "pwi", "fi", "score", 1, now),
        )
        conn.commit()

        for name in FINAL_MIGRATIONS:
            _run(conn, name)

        # El trabajo conserva su id y ahora tiene espacio
        work = conn.execute(
            "SELECT * FROM preparation_works WHERE id = 'pwi'"
        ).fetchone()
        assert work is not None
        assert work["space_id"]

        item = conn.execute(
            "SELECT * FROM preparation_work_items WHERE id = 'itemi'"
        ).fetchone()
        assert item is not None
        assert item["preparation_work_id"] == "pwi"
        assert item["work_id"] == "wi"
        assert item["resource_id"] == "ri"
        assert item["voice_label"] == "Soprano"
        assert item["notes"] == "nota item"

        ref = conn.execute(
            "SELECT * FROM preparation_work_files WHERE id = 'refi'"
        ).fetchone()
        assert ref is not None
        assert ref["file_id"] == "fi"

        # Nada huérfano
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM preparation_works pw "
            "LEFT JOIN spaces s ON s.id = pw.space_id WHERE s.id IS NULL"
        ).fetchone()["c"] == 0
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM preparation_work_items i "
            "LEFT JOIN preparation_works w ON w.id = i.preparation_work_id WHERE w.id IS NULL"
        ).fetchone()["c"] == 0

        # Borrar el trabajo elimina sus items, no las obras
        conn.execute("DELETE FROM preparation_works WHERE id = 'pwi'")
        conn.commit()
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM preparation_work_items WHERE preparation_work_id = 'pwi'"
        ).fetchone()["c"] == 0
        assert conn.execute("SELECT COUNT(*) AS c FROM works WHERE id = 'wi'").fetchone()["c"] == 1
        assert conn.execute("SELECT COUNT(*) AS c FROM resources WHERE id = 'ri'").fetchone()["c"] == 1
        assert conn.execute("SELECT COUNT(*) AS c FROM files WHERE id = 'fi'").fetchone()["c"] == 1


@pytest.mark.integration
def test_migration_aborts_on_orphan_row(legacy_schema: Settings):
    """5. Un trabajo que no puede asociarse aborta la migración de forma explícita."""
    settings = legacy_schema
    with db_connect(settings) as conn:
        _run(conn, "035_preparation_works.sql")
        for name in OLD_SCHEMA_MIGRATIONS:
            _run(conn, name)

        _insert_group(conn, "go", "Grupo Orfano")
        _insert_legacy_work(conn, "pwo", "go", "Trabajo valido", "preparation/go/pwo")

        # Partir de un estado sin la migración registrada (el rebuild la registró)
        conn.execute(
            "DELETE FROM chorus_schema_migrations WHERE name IN "
            "('040_migrate_preparation_works_to_spaces.sql','041_consolidate_spaces.sql')"
        )

        # Registro INCONSISTENTE: referencia un grupo que no existe. Se fuerza
        # desactivando las FKs para reproducir un estado histórico corrupto.
        conn.execute("SET FOREIGN_KEY_CHECKS = 0")
        _insert_legacy_work(conn, "pwz", "grupo-inexistente", "Trabajo huerfano",
                            "preparation/gz/pwz")
        conn.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()

        orphans = conn.execute(
            "SELECT COUNT(*) AS c FROM preparation_works pw "
            "LEFT JOIN groups g ON g.id = pw.group_id WHERE g.id IS NULL"
        ).fetchone()["c"]
        assert orphans == 1, "Debe existir un trabajo huérfano de partida"

        # La migración debe fallar, no continuar en silencio
        with pytest.raises(Exception) as exc:
            _run(conn, "040_migrate_preparation_works_to_spaces.sql")
        message = str(exc.value)
        assert "1146" in message or "doesn't exist" in message.lower()

        # No queda registrada como aplicada
        registered = conn.execute(
            "SELECT COUNT(*) AS c FROM chorus_schema_migrations WHERE name = ?",
            ("040_migrate_preparation_works_to_spaces.sql",),
        ).fetchone()["c"]
        assert registered == 0

        # El esquema no quedó a medias: group_id sigue existiendo
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_works' "
            "AND COLUMN_NAME = 'group_id'"
        ).fetchone()["c"] == 1

        # Los datos originales permanecen intactos
        assert conn.execute(
            "SELECT title FROM preparation_works WHERE id = 'pwo'"
        ).fetchone()["title"] == "Trabajo valido"


@pytest.mark.integration
def test_migration_resolves_duplicate_general_spaces(legacy_schema: Settings):
    """Datos ambiguos: varios espacios generales por grupo se consolidan."""
    settings = legacy_schema
    with db_connect(settings) as conn:
        _run(conn, "035_preparation_works.sql")
        for name in OLD_SCHEMA_MIGRATIONS:
            _run(conn, name)

        _insert_group(conn, "gd", "Grupo Duplicado")
        # Dos espacios generales para el mismo grupo (estado histórico ambiguo)
        conn.execute(
            "INSERT INTO spaces (id, space_type, owner_sub, group_id, name, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("dup-a", "group", "gd", "gd", "General A",
             "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
        )
        conn.execute(
            "INSERT INTO spaces (id, space_type, owner_sub, group_id, name, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("dup-b", "group", "gd", "gd", "General B",
             "2026-02-01 00:00:00", "2026-02-01 00:00:00"),
        )
        _insert_legacy_work(conn, "pwd", "gd", "Trabajo en duplicado", "preparation/gd/pwd")
        conn.commit()

        for name in FINAL_MIGRATIONS:
            _run(conn, name)

        # Queda un único espacio general y conserva el trabajo
        spaces = conn.execute(
            "SELECT id FROM spaces WHERE group_id = 'gd' AND space_type = 'group'"
        ).fetchall()
        assert len(spaces) == 1
        keep_id = spaces[0]["id"]
        assert keep_id == "dup-a", "Debe conservarse el espacio general más antiguo"

        work = conn.execute(
            "SELECT space_id FROM preparation_works WHERE id = 'pwd'"
        ).fetchone()
        assert work["space_id"] == keep_id, "El trabajo debe reasignarse al espacio conservado"

        # owner_sub normalizado a NULL en espacios no personales
        row = conn.execute(
            "SELECT owner_sub FROM spaces WHERE id = ?", (keep_id,)
        ).fetchone()
        assert row["owner_sub"] is None