-- Chorus application drafts are intentionally outside the V6 musical catalogue.
-- A draft may exist before the first File. It becomes a V6 Work/Resource/File chain
-- only when a real MusicXML/MXL (or another accepted score file) is uploaded.
PRAGMA foreign_keys = ON;

CREATE TABLE creation_drafts (
    id TEXT PRIMARY KEY,
    owner_sub TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'editing'
        CHECK (status IN ('editing', 'materialized', 'cancelled')),
    source_kind TEXT NOT NULL DEFAULT 'blank'
        CHECK (source_kind IN ('blank', 'osap')),
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
    ),
    CHECK (
        (status = 'materialized' AND materialized_work_id IS NOT NULL)
        OR
        (status <> 'materialized' AND materialized_work_id IS NULL)
    )
);

CREATE INDEX idx_creation_drafts_owner_status
    ON creation_drafts (owner_sub, status, updated_at);

CREATE TABLE editor_source_tokens (
    token_hash TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (draft_id)
        REFERENCES creation_drafts (id)
        ON DELETE CASCADE
);

CREATE INDEX idx_editor_source_tokens_draft
    ON editor_source_tokens (draft_id);
