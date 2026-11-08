from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "sqlite"
    / "001_v6_work_resource_file.sql"
)


@pytest.fixture
def db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def insert_chain(
    db: sqlite3.Connection,
    *,
    work_id: str = "work-1",
    resource_id: str = "resource-1",
    file_id: str = "file-1",
) -> None:
    db.execute("BEGIN")
    db.execute(
        """
        INSERT INTO works
            (id, title, created_at, updated_at, required_resource_id)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """,
        (work_id, "Test work", resource_id),
    )
    db.execute(
        """
        INSERT INTO resources
            (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
        """,
        (resource_id, work_id, "score", file_id),
    )
    db.execute(
        """
        INSERT INTO files
            (id, resource_id, name, status, storage_pointer, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (file_id, resource_id, "score.musicxml", "registered", "private/object/1"),
    )


def test_complete_work_resource_file_chain_commits(db: sqlite3.Connection) -> None:
    insert_chain(db)
    db.commit()

    assert db.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 1


def test_work_without_resource_is_rejected_at_commit(db: sqlite3.Connection) -> None:
    db.execute("BEGIN")
    db.execute(
        """
        INSERT INTO works
            (id, title, created_at, updated_at, required_resource_id)
        VALUES ('work-1', 'Incomplete', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'missing')
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.commit()
    db.rollback()


def test_resource_without_file_is_rejected_at_commit(db: sqlite3.Connection) -> None:
    db.execute("BEGIN")
    db.execute(
        """
        INSERT INTO works
            (id, title, created_at, updated_at, required_resource_id)
        VALUES ('work-1', 'Test work', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'resource-1')
        """
    )
    db.execute(
        """
        INSERT INTO resources
            (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES ('resource-1', 'work-1', 'score', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'missing')
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.commit()
    db.rollback()


def test_each_resource_requires_its_own_file(db: sqlite3.Connection) -> None:
    insert_chain(db)
    db.execute(
        """
        INSERT INTO resources
            (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES ('resource-2', 'work-1', 'arrangement',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'missing-file')
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.commit()
    db.rollback()


def test_file_cannot_be_shared_by_two_resources(db: sqlite3.Connection) -> None:
    insert_chain(db)
    db.execute(
        """
        INSERT INTO resources
            (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES ('resource-2', 'work-1', 'arrangement',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'file-1')
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.commit()
    db.rollback()


def test_sha256_is_not_a_unique_identity(db: sqlite3.Connection) -> None:
    insert_chain(db)
    db.execute(
        """
        INSERT INTO resources
            (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES ('resource-2', 'work-1', 'alternate-edition',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'file-2')
        """
    )
    db.execute(
        """
        INSERT INTO files
            (id, resource_id, name, status, sha256, storage_pointer, created_at, updated_at)
        VALUES ('file-2', 'resource-2', 'same-bytes.musicxml', 'registered',
                ?, 'private/object/2', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("a" * 64,),
    )
    db.execute(
        "UPDATE files SET sha256 = ? WHERE id = 'file-1'",
        ("a" * 64,),
    )
    db.commit()

    assert db.execute("SELECT COUNT(*) FROM files WHERE sha256 = ?", ("a" * 64,)).fetchone()[0] == 2

# CI entrypoint: this module is run by the v6-schema-tests workflow.
