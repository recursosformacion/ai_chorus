"""Tests de esquema v6 (works/resources/files) contra MariaDB 10.4.32.

Réplica de test_v6_schema.py adaptada a restricciones reales de MySQL/MariaDB.
El esquema MySQL NO tiene FKs diferidas circulares (solo resources->works y files->resources).
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.main import initialise_database
from app.db import connect as db_connect


SCHEMA_SQL = """
-- Esquema base de 001_schema.sql (MySQL)
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS works (
    id VARCHAR(191) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    subtitle VARCHAR(500) NULL,
    catalogue VARCHAR(255) NULL,
    year VARCHAR(64) NULL,
    description LONGTEXT NULL,
    language VARCHAR(32) NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    required_resource_id VARCHAR(191) NOT NULL,
    owner_sub VARCHAR(191) NULL,
    UNIQUE KEY uq_works_resource (id, required_resource_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS resources (
    id VARCHAR(191) PRIMARY KEY,
    work_id VARCHAR(191) NOT NULL,
    resource_type VARCHAR(80) NOT NULL,
    title VARCHAR(500) NULL,
    description LONGTEXT NULL,
    provenance VARCHAR(255) NULL,
    rights_license VARCHAR(255) NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    required_file_id VARCHAR(191) NOT NULL,
    UNIQUE KEY uq_resources_work (work_id, id),
    CONSTRAINT fk_resources_work FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS files (
    id VARCHAR(191) PRIMARY KEY,
    resource_id VARCHAR(191) NOT NULL,
    name VARCHAR(500) NOT NULL,
    mime_type VARCHAR(191) NULL,
    size_bytes BIGINT NULL,
    status VARCHAR(32) NOT NULL,
    sha256 CHAR(64) NULL,
    storage_pointer VARCHAR(1000) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_files_resource (resource_id, id),
    CONSTRAINT fk_files_resource FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
"""


def _apply_schema(conn):
    """Aplica el esquema base directamente en la conexión de test."""
    import sqlparse
    from app.db import _execute_sql_script

    _execute_sql_script(conn, SCHEMA_SQL, is_mysql=True)


def _now():
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


def insert_chain(
    conn,
    *,
    work_id: str = "work-1",
    resource_id: str = "resource-1",
    file_id: str = "file-1",
) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO works
            (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (work_id, "Test work", now, now, resource_id),
    )
    conn.execute(
        """
        INSERT INTO resources
            (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (resource_id, work_id, "score", now, now, file_id),
    )
    conn.execute(
        """
        INSERT INTO files
            (id, resource_id, name, status, storage_pointer, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (file_id, resource_id, "score.musicxml", "registered", "private/object/1", now, now),
    )


@pytest.fixture(autouse=True)
def _schema(unit_db):
    """Aplica esquema base antes de cada test y limpia tablas."""
    _apply_schema(unit_db)
    # Limpiar datos de tests previos (DDL auto-commit en MySQL)
    unit_db.execute("DELETE FROM files")
    unit_db.execute("DELETE FROM resources")
    unit_db.execute("DELETE FROM works")


@pytest.mark.db
def test_complete_work_resource_file_chain_commits(unit_db):
    """Cadena completa work->resource->file se inserta correctamente."""
    insert_chain(unit_db)
    # No COMMIT - rollback fixture limpia
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM works").fetchone()["cnt"] == 1
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM resources").fetchone()["cnt"] == 1
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM files").fetchone()["cnt"] == 1


@pytest.mark.db
def test_resource_without_work_rejected_fk(unit_db):
    """Resource con work_id inexistente falla en INSERT (FK immediate)."""
    now = _now()
    # Insert work first
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-fk-1", "Test", now, now, "resource-dummy"),
    )
    # Now try to insert resource with non-existent work_id
    with pytest.raises(Exception) as exc_info:
        unit_db.execute(
            """
            INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("resource-fk-1", "non-existent-work", "score", now, now, "file-dummy"),
        )
    assert "foreign key" in str(exc_info.value).lower() or "1452" in str(exc_info.value)


@pytest.mark.db
def test_file_without_resource_rejected_fk(unit_db):
    """File con resource_id inexistente falla en INSERT (FK immediate)."""
    now = _now()
    # Insert work + resource
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-fk-2", "Test", now, now, "resource-fk-2"),
    )
    unit_db.execute(
        """
        INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        ("resource-fk-2", "work-fk-2", "score", now, now, "file-dummy"),
    )
    # Try to insert file with non-existent resource_id
    with pytest.raises(Exception) as exc_info:
        unit_db.execute(
            """
            INSERT INTO files (id, resource_id, name, status, storage_pointer, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("file-fk-1", "non-existent-resource", "score.musicxml", "registered", "private/obj", now, now),
        )
    assert "foreign key" in str(exc_info.value).lower() or "1452" in str(exc_info.value)


@pytest.mark.db
def test_unique_work_resource_pair(unit_db):
    """UNIQUE KEY uq_works_resource (id, required_resource_id) evita duplicados."""
    now = _now()
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-uq-1", "Test", now, now, "resource-uq-1"),
    )
    with pytest.raises(Exception) as exc_info:
        unit_db.execute(
            """
            INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("work-uq-1", "Test 2", now, now, "resource-uq-1"),
        )
    assert "duplicate" in str(exc_info.value).lower() or "1062" in str(exc_info.value)


@pytest.mark.db
def test_unique_resource_work_pair(unit_db):
    """UNIQUE KEY uq_resources_work (work_id, id) evita duplicados."""
    now = _now()
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-uq-2", "Test", now, now, "resource-uq-2"),
    )
    unit_db.execute(
        """
        INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        ("resource-uq-2", "work-uq-2", "score", now, now, "file-uq-1"),
    )
    with pytest.raises(Exception) as exc_info:
        unit_db.execute(
            """
            INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("resource-uq-2", "work-uq-2", "arrangement", now, now, "file-uq-2"),
        )
    assert "duplicate" in str(exc_info.value).lower() or "1062" in str(exc_info.value)


@pytest.mark.db
def test_unique_file_resource_pair(unit_db):
    """UNIQUE KEY uq_files_resource (resource_id, id) evita duplicados."""
    now = _now()
    # Setup
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-uq-3", "Test", now, now, "resource-uq-3"),
    )
    unit_db.execute(
        """
        INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        ("resource-uq-3", "work-uq-3", "score", now, now, "file-uq-3"),
    )
    unit_db.execute(
        """
        INSERT INTO files (id, resource_id, name, status, storage_pointer, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        ("file-uq-3", "resource-uq-3", "score.musicxml", "registered", "private/obj", now, now),
    )
    # Duplicate file id for same resource
    with pytest.raises(Exception) as exc_info:
        unit_db.execute(
            """
            INSERT INTO files (id, resource_id, name, status, storage_pointer, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("file-uq-3", "resource-uq-3", "score2.musicxml", "registered", "private/obj2", now, now),
        )
    assert "duplicate" in str(exc_info.value).lower() or "1062" in str(exc_info.value)


@pytest.mark.db
def test_cascade_delete_work_removes_resources_and_files(unit_db):
    """DELETE works CASCADE elimina resources y files asociados (cadena completa)."""
    now = _now()
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-cascade-1", "Test", now, now, "resource-cascade-1"),
    )
    unit_db.execute(
        """
        INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        ("resource-cascade-1", "work-cascade-1", "score", now, now, "file-cascade-1"),
    )
    unit_db.execute(
        """
        INSERT INTO files (id, resource_id, name, status, storage_pointer, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        ("file-cascade-1", "resource-cascade-1", "score.musicxml", "registered", "private/obj", now, now),
    )
    # Delete work - cascade: works -> resources -> files
    unit_db.execute("DELETE FROM works WHERE id = %s", ("work-cascade-1",))
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM works").fetchone()["cnt"] == 0
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM resources").fetchone()["cnt"] == 0
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM files").fetchone()["cnt"] == 0


@pytest.mark.db
def test_cascade_delete_resource_removes_files(unit_db):
    """DELETE resources CASCADE elimina files asociados."""
    now = _now()
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-cascade-2", "Test", now, now, "resource-cascade-2"),
    )
    unit_db.execute(
        """
        INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        ("resource-cascade-2", "work-cascade-2", "score", now, now, "file-cascade-2"),
    )
    unit_db.execute(
        """
        INSERT INTO files (id, resource_id, name, status, storage_pointer, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        ("file-cascade-2", "resource-cascade-2", "score.musicxml", "registered", "private/obj", now, now),
    )
    # Delete resource - should cascade to files
    unit_db.execute("DELETE FROM resources WHERE id = %s", ("resource-cascade-2",))
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM resources").fetchone()["cnt"] == 0
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM files").fetchone()["cnt"] == 0


@pytest.mark.db
def test_sha256_not_unique_identity(unit_db):
    """Mismo sha256 permitido en múltiples files (no es clave única)."""
    now = _now()
    # Chain 1
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-sha-1", "Test", now, now, "resource-sha-1"),
    )
    unit_db.execute(
        """
        INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        ("resource-sha-1", "work-sha-1", "score", now, now, "file-sha-1"),
    )
    unit_db.execute(
        """
        INSERT INTO files (id, resource_id, name, status, sha256, storage_pointer, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ("file-sha-1", "resource-sha-1", "score.musicxml", "registered", "a"*64, "private/obj1", now, now),
    )
    # Chain 2
    unit_db.execute(
        """
        INSERT INTO works (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("work-sha-2", "Test", now, now, "resource-sha-2"),
    )
    unit_db.execute(
        """
        INSERT INTO resources (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        ("resource-sha-2", "work-sha-2", "score", now, now, "file-sha-2"),
    )
    unit_db.execute(
        """
        INSERT INTO files (id, resource_id, name, status, sha256, storage_pointer, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ("file-sha-2", "resource-sha-2", "score2.musicxml", "registered", "a"*64, "private/obj2", now, now),
    )
    # Update first file to same sha
    unit_db.execute(
        "UPDATE files SET sha256 = %s WHERE id = %s",
        ("a"*64, "file-sha-1"),
    )
    cnt = unit_db.execute("SELECT COUNT(*) AS cnt FROM files WHERE sha256 = %s", ("a"*64,)).fetchone()["cnt"]
    assert cnt == 2