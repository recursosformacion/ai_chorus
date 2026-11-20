from __future__ import annotations

import pytest

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


def insert_chain(
    conn,
    *,
    work_id: str = "work-1",
    resource_id: str = "resource-1",
    file_id: str = "file-1",
) -> None:
    conn.execute("START TRANSACTION")
    conn.execute(
        """
        INSERT INTO works
            (id, title, created_at, updated_at, required_resource_id)
        VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)
        """,
        (work_id, "Test work", resource_id),
    )
    conn.execute(
        """
        INSERT INTO resources
            (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)
        """,
        (resource_id, work_id, "score", file_id),
    )
    conn.execute(
        """
        INSERT INTO files
            (id, resource_id, name, status, storage_pointer, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (file_id, resource_id, "score.musicxml", "registered", "private/object/1"),
    )


@pytest.mark.db
def test_complete_work_resource_file_chain_commits(unit_db):
    insert_chain(unit_db)
    unit_db.execute("COMMIT")

    count_works = unit_db.execute("SELECT COUNT(*) AS cnt FROM works").fetchone()["cnt"]
    count_resources = unit_db.execute("SELECT COUNT(*) AS cnt FROM resources").fetchone()["cnt"]
    count_files = unit_db.execute("SELECT COUNT(*) AS cnt FROM files").fetchone()["cnt"]

    assert count_works == 1
    assert count_resources == 1
    assert count_files == 1


@pytest.mark.db
def test_sha256_is_not_a_unique_identity(unit_db):
    insert_chain(unit_db)
    unit_db.execute(
        """
        INSERT INTO resources
            (id, work_id, resource_type, created_at, updated_at, required_file_id)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)
        """,
        ("resource-2", "work-1", "alternate-edition", "file-2"),
    )
    unit_db.execute(
        """
        INSERT INTO files
            (id, resource_id, name, status, sha256, storage_pointer, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        ("file-2", "resource-2", "same-bytes.musicxml", "registered", "a" * 64, "private/object/2"),
    )
    unit_db.execute(
        "UPDATE files SET sha256 = %s WHERE id = %s",
        ("a" * 64, "file-1"),
    )
    unit_db.execute("COMMIT")

    count = unit_db.execute("SELECT COUNT(*) AS cnt FROM files WHERE sha256 = %s", ("a" * 64,)).fetchone()["cnt"]
    assert count == 2


# NOTA: Los siguientes tests de constraints FK circulares se eliminaron porque
# el esquema MySQL real (001_schema.sql) NO tiene FKs de works->resources ni
# resources->files. Las FKs existentes son:
#   resources.work_id -> works.id  (fk_resources_work)
#   files.resource_id -> resources.id  (fk_files_resource)
# Los tests de estas FKs reales están en test_schema_mysql.py