-- Chorus pilot: ownership of local works and the personal library.
PRAGMA foreign_keys = ON;

ALTER TABLE works ADD COLUMN owner_sub TEXT;
CREATE INDEX idx_works_owner_sub ON works (owner_sub);

CREATE TABLE library_items (
    id TEXT PRIMARY KEY,
    owner_sub TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('local_work', 'osap_reference')),
    work_id TEXT REFERENCES works(id) ON DELETE CASCADE,
    provider TEXT,
    external_work_id TEXT,
    external_resource_id TEXT,
    title TEXT NOT NULL,
    subtitle TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (kind = 'local_work' AND work_id IS NOT NULL)
        OR (kind = 'osap_reference' AND provider IS NOT NULL AND external_work_id IS NOT NULL)
    )
);
CREATE UNIQUE INDEX uq_library_local_work
    ON library_items (owner_sub, work_id) WHERE work_id IS NOT NULL;
CREATE UNIQUE INDEX uq_library_external
    ON library_items (owner_sub, provider, external_work_id, COALESCE(external_resource_id, ''));

CREATE TABLE collections (
    id TEXT PRIMARY KEY,
    owner_sub TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (owner_sub, name)
);

CREATE TABLE collection_items (
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    library_item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    PRIMARY KEY (collection_id, library_item_id)
);
