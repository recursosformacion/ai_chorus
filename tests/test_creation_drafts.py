from __future__ import annotations

import pytest
import pymysql.err

from app.config import Settings
from app.db import connect as db_connect


@pytest.fixture
def settings(integration_settings: Settings, tmp_path):
    """Settings con MariaDB de integración y storage_root en tmp_path."""
    return Settings(
        auth_base_url="https://auth.test",
        osap_api_base_url="http://osap.test",
        editor_base_url="http://editor.test",
        editor_origin="http://editor.test",
        public_base_url="http://chorus.test",
        database_url=integration_settings.database_url,
        storage_root=str(tmp_path / "private"),
        cors_origins=integration_settings.cors_origins,
        max_upload_bytes=integration_settings.max_upload_bytes,
        source_token_ttl_seconds=integration_settings.source_token_ttl_seconds,
        oidc_issuer="https://auth.test",
        oidc_authorize_url="https://auth.test/auth/authorize",
        oidc_token_url="https://auth.test/oauth/token",
        oidc_client_id="chorus-web",
        oidc_client_secret="secret",
        oidc_redirect_uri="http://chorus.test/api/v1/auth/oidc/callback",
        oidc_scope="openid profile email",
        auth_timeout_seconds=15.0,
        osap_timeout_seconds=45.0,
        secure_cookies=False,
    )


@pytest.mark.db
def test_blank_draft_exists_without_creating_a_musical_work(settings):
    with db_connect(settings) as conn:
        conn.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, title, created_at, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("draft-1", "oidc-subject-1", "New score"),
        )

        count_drafts = conn.execute("SELECT COUNT(*) AS cnt FROM creation_drafts").fetchone()["cnt"]
        count_works = conn.execute("SELECT COUNT(*) AS cnt FROM works").fetchone()["cnt"]
        count_resources = conn.execute("SELECT COUNT(*) AS cnt FROM resources").fetchone()["cnt"]
        count_files = conn.execute("SELECT COUNT(*) AS cnt FROM files").fetchone()["cnt"]

    assert count_drafts == 1
    assert count_works == 0
    assert count_resources == 0
    assert count_files == 0


@pytest.mark.db
def test_osap_draft_records_external_work_and_representation(settings):
    with db_connect(settings) as conn:
        conn.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, source_kind, source_work_id, source_representation_id,
                 source_provider, source_format, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("draft-2", "oidc-subject-1", "osap", "work-42", "rep-99", "omr", "MusicXML"),
        )

        row = conn.execute(
            "SELECT source_kind, source_work_id, source_representation_id FROM creation_drafts WHERE id=%s",
            ("draft-2",)
        ).fetchone()
        count_works = conn.execute("SELECT COUNT(*) AS cnt FROM works").fetchone()["cnt"]

    assert row["source_kind"] == "osap"
    assert row["source_work_id"] == "work-42"
    assert row["source_representation_id"] == "rep-99"
    assert count_works == 0


@pytest.mark.db
def test_osap_draft_requires_both_external_identifiers(settings):
    with db_connect(settings) as conn:
        with pytest.raises(pymysql.err.OperationalError):
            conn.execute(
                """
                INSERT INTO creation_drafts
                    (id, owner_sub, source_kind, source_work_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                ("draft-3", "oidc-subject-1", "osap", "work-42"),
            )


@pytest.mark.db
def test_blank_draft_cannot_smuggle_osap_identifiers(settings):
    with db_connect(settings) as conn:
        with pytest.raises(pymysql.err.OperationalError):
            conn.execute(
                """
                INSERT INTO creation_drafts
                    (id, owner_sub, source_kind, source_work_id, source_representation_id,
                     created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                ("draft-4", "oidc-subject-1", "blank", "work-42", "rep-99"),
            )


@pytest.mark.db
def test_materialized_status_requires_a_work_id(settings):
    with db_connect(settings) as conn:
        with pytest.raises(pymysql.err.OperationalError):
            conn.execute(
                """
                INSERT INTO creation_drafts
                    (id, owner_sub, status, created_at, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                ("draft-5", "oidc-subject-1", "materialized"),
            )


@pytest.mark.db
def test_editor_source_token_is_scoped_to_a_draft_and_cascades(settings):
    with db_connect(settings) as conn:
        conn.execute(
            """
            INSERT INTO creation_drafts
                (id, owner_sub, created_at, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("draft-6", "oidc-subject-1"),
        )
        conn.execute(
            """
            INSERT INTO editor_source_tokens (token_hash, draft_id, expires_at, created_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            """,
            ("hash-1", "draft-6", "2099-01-01T00:00:00Z"),
        )
        conn.execute("DELETE FROM creation_drafts WHERE id=%s", ("draft-6",))

        count = conn.execute("SELECT COUNT(*) AS cnt FROM editor_source_tokens").fetchone()["cnt"]
    assert count == 0