"""Tests de creation_drafts contra MariaDB 10.4.32.

Réplica exacta de test_creation_drafts.py pero usando fixture unit_db (MariaDB con transacción+rollback).
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.main import initialise_database
from app.db import connect as db_connect


DRAFTS_SQL = """
-- Esquema de creation_drafts (001_v6 + 002_creation_drafts)
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

CREATE TABLE IF NOT EXISTS creation_drafts (
    id VARCHAR(191) PRIMARY KEY,
    owner_sub VARCHAR(191) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'editing',
    source_kind VARCHAR(32) NOT NULL DEFAULT 'blank',
    title VARCHAR(500) NULL,
    resource_type VARCHAR(80) NOT NULL DEFAULT 'score',
    source_work_id VARCHAR(191) NULL,
    source_representation_id VARCHAR(191) NULL,
    source_provider VARCHAR(80) NULL,
    source_format VARCHAR(80) NULL,
    source_file_name VARCHAR(500) NULL,
    source_file_pointer VARCHAR(1000) NULL,
    source_sha256 CHAR(64) NULL,
    source_rights_license VARCHAR(255) NULL,
    materialized_work_id VARCHAR(191) NULL UNIQUE,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    CONSTRAINT ck_draft_source CHECK (
        (source_kind='blank' AND source_work_id IS NULL AND source_representation_id IS NULL)
        OR (source_kind='osap' AND source_work_id IS NOT NULL AND source_representation_id IS NOT NULL)
        OR (source_kind='local' AND source_work_id IS NOT NULL)
    ),
    CONSTRAINT ck_draft_status CHECK (
        (status='materialized' AND materialized_work_id IS NOT NULL)
        OR (status<>'materialized' AND materialized_work_id IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS editor_source_tokens (
    token_hash CHAR(64) PRIMARY KEY,
    draft_id VARCHAR(191) NOT NULL,
    expires_at VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_source_token_draft FOREIGN KEY (draft_id) REFERENCES creation_drafts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
"""


def _apply_schema(conn):
    import sqlparse
    from app.db import _execute_sql_script
    _execute_sql_script(conn, DRAFTS_SQL, is_mysql=True)


def _now():
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


@pytest.fixture(autouse=True)
def _schema(unit_db):
    """Aplica esquema base antes de cada test y limpia tablas."""
    _apply_schema(unit_db)
    # Limpiar datos de tests previos (DDL auto-commit en MySQL)
    unit_db.execute("DELETE FROM editor_source_tokens")
    unit_db.execute("DELETE FROM creation_drafts")
    unit_db.execute("DELETE FROM files")
    unit_db.execute("DELETE FROM resources")
    unit_db.execute("DELETE FROM works")


@pytest.mark.db
def test_blank_draft_exists_without_creating_a_musical_work(unit_db):
    now = _now()
    unit_db.execute(
        """
        INSERT INTO creation_drafts
            (id, owner_sub, title, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        ("draft-1", "oidc-subject-1", "New score", now, now),
    )

    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM creation_drafts").fetchone()["cnt"] == 1
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM works").fetchone()["cnt"] == 0
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM resources").fetchone()["cnt"] == 0
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM files").fetchone()["cnt"] == 0


@pytest.mark.db
def test_osap_draft_records_external_work_and_representation(unit_db):
    now = _now()
    unit_db.execute(
        """
        INSERT INTO creation_drafts
            (id, owner_sub, source_kind, source_work_id, source_representation_id,
             source_provider, source_format, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        ("draft-2", "oidc-subject-1", "osap", "work-42", "rep-99", "omr", "MusicXML", now, now),
    )

    row = unit_db.execute(
        "SELECT source_kind, source_work_id, source_representation_id FROM creation_drafts WHERE id=%s",
        ("draft-2",)
    ).fetchone()
    assert row == {"source_kind": "osap", "source_work_id": "work-42", "source_representation_id": "rep-99"}
    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM works").fetchone()["cnt"] == 0


@pytest.mark.db
def test_osap_draft_requires_both_external_identifiers(unit_db):
    now = _now()
    with pytest.raises(Exception) as exc_info:
        unit_db.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, source_kind, source_work_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("draft-3", "oidc-subject-1", "osap", "work-42", now, now),
        )
    # CHECK constraint violation
    assert "check" in str(exc_info.value).lower() or "constraint" in str(exc_info.value).lower()


@pytest.mark.db
def test_blank_draft_cannot_smuggle_osap_identifiers(unit_db):
    now = _now()
    with pytest.raises(Exception) as exc_info:
        unit_db.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, source_kind, source_work_id, source_representation_id,
                 created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("draft-4", "oidc-subject-1", "blank", "work-42", "rep-99", now, now),
        )
    assert "check" in str(exc_info.value).lower() or "constraint" in str(exc_info.value).lower()


@pytest.mark.db
def test_materialized_status_requires_a_work_id(unit_db):
    now = _now()
    with pytest.raises(Exception) as exc_info:
        unit_db.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("draft-5", "oidc-subject-1", "materialized", now, now),
        )
    assert "check" in str(exc_info.value).lower() or "constraint" in str(exc_info.value).lower()


@pytest.mark.db
def test_editor_source_token_is_scoped_to_a_draft_and_cascades(unit_db):
    now = _now()
    unit_db.execute(
        """
        INSERT INTO creation_drafts
            (id, owner_sub, created_at, updated_at)
        VALUES (%s, %s, %s, %s)
        """,
        ("draft-6", "oidc-subject-1", now, now),
    )
    unit_db.execute(
        """
        INSERT INTO editor_source_tokens (token_hash, draft_id, expires_at, created_at)
        VALUES (%s, %s, %s, %s)
        """,
        ("hash-1", "draft-6", "2099-01-01T00:00:00Z", now),
    )
    unit_db.execute("DELETE FROM creation_drafts WHERE id=%s", ("draft-6",))

    assert unit_db.execute("SELECT COUNT(*) AS cnt FROM editor_source_tokens").fetchone()["cnt"] == 0