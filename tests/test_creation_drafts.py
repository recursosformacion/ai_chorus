from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations" / "sqlite"


@pytest.fixture
def db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        (MIGRATIONS / "001_v6_work_resource_file.sql").read_text(encoding="utf-8")
    )
    connection.executescript(
        (MIGRATIONS / "002_creation_drafts.sql").read_text(encoding="utf-8")
    )
    yield connection
    connection.close()


def test_blank_draft_exists_without_creating_a_musical_work(db: sqlite3.Connection) -> None:
    db.execute(
        """
        INSERT INTO creation_drafts
            (id, owner_sub, title, created_at, updated_at)
        VALUES ('draft-1', 'oidc-subject-1', 'New score', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )

    assert db.execute("SELECT COUNT(*) FROM creation_drafts").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0


def test_osap_draft_records_external_work_and_representation(db: sqlite3.Connection) -> None:
    db.execute(
        """
        INSERT INTO creation_drafts
            (id, owner_sub, source_kind, source_work_id, source_representation_id,
             source_provider, source_format, created_at, updated_at)
        VALUES ('draft-2', 'oidc-subject-1', 'osap', 'work-42', 'rep-99',
                'omr', 'MusicXML', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )

    row = db.execute(
        "SELECT source_kind, source_work_id, source_representation_id FROM creation_drafts WHERE id='draft-2'"
    ).fetchone()
    assert row == ("osap", "work-42", "rep-99")
    assert db.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 0


def test_osap_draft_requires_both_external_identifiers(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, source_kind, source_work_id, created_at, updated_at)
            VALUES ('draft-3', 'oidc-subject-1', 'osap', 'work-42',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )


def test_blank_draft_cannot_smuggle_osap_identifiers(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, source_kind, source_work_id, source_representation_id,
                 created_at, updated_at)
            VALUES ('draft-4', 'oidc-subject-1', 'blank', 'work-42', 'rep-99',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )


def test_materialized_status_requires_a_work_id(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, status, created_at, updated_at)
            VALUES ('draft-5', 'oidc-subject-1', 'materialized',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )


def test_editor_source_token_is_scoped_to_a_draft_and_cascades(db: sqlite3.Connection) -> None:
    db.execute(
        """
        INSERT INTO creation_drafts
            (id, owner_sub, created_at, updated_at)
        VALUES ('draft-6', 'oidc-subject-1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
    )
    db.execute(
        """
        INSERT INTO editor_source_tokens (token_hash, draft_id, expires_at, created_at)
        VALUES ('hash-1', 'draft-6', '2099-01-01T00:00:00Z', CURRENT_TIMESTAMP)
        """
    )
    db.execute("DELETE FROM creation_drafts WHERE id='draft-6'")

    assert db.execute("SELECT COUNT(*) FROM editor_source_tokens").fetchone()[0] == 0
