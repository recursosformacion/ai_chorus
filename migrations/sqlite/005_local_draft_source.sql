-- Allow drafts whose source is a local Work/Resource/File (opened from the library).
PRAGMA foreign_keys = OFF;

CREATE TABLE creation_drafts_new (
    id TEXT PRIMARY KEY,
    owner_sub TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'editing'
        CHECK (status IN ('editing', 'materialized', 'cancelled')),
    source_kind TEXT NOT NULL DEFAULT 'blank'
        CHECK (source_kind IN ('blank', 'osap', 'local')),
    title TEXT,
    resource_type TEXT NOT NULL DEFAULT 'score',
    source_work_id TEXT,
    source_representation_id TEXT,
    source_provider TEXT,
    source_format TEXT,
    source_file_name TEXT,
    source_file_pointer TEXT,
    source_sha256 TEXT,
    source_rights_license TEXT,
    materialized_work_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (source_kind = 'blank'
            AND source_work_id IS NULL
            AND source_representation_id IS NULL)
        OR
        (source_kind = 'osap'
            AND source_work_id IS NOT NULL
            AND source_representation_id IS NOT NULL)
        OR
        (source_kind = 'local' AND source_work_id IS NOT NULL)
    ),
    CHECK (
        (status = 'materialized' AND materialized_work_id IS NOT NULL)
        OR
        (status <> 'materialized' AND materialized_work_id IS NULL)
    )
);

INSERT INTO creation_drafts_new SELECT * FROM creation_drafts;
DROP TABLE creation_drafts;
ALTER TABLE creation_drafts_new RENAME TO creation_drafts;

CREATE INDEX idx_creation_drafts_owner_status
    ON creation_drafts (owner_sub, status, updated_at);

PRAGMA foreign_keys = ON;
