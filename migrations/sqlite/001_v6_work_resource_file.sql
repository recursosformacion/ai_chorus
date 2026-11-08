-- Chorus V6 pilot schema (SQLite reference implementation).
-- Not an OSAP Storage production migration or a decision on Chorus' final DB engine.
-- Each Work points to a required child Resource; each Resource points to a required File.
-- Deferred circular foreign keys allow atomic chain creation and reject incomplete chains at COMMIT.
PRAGMA foreign_keys = ON;

CREATE TABLE works (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subtitle TEXT,
    catalogue TEXT,
    year TEXT,
    description TEXT,
    language TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    required_resource_id TEXT NOT NULL,
    UNIQUE (id, required_resource_id),
    FOREIGN KEY (id, required_resource_id)
        REFERENCES resources (work_id, id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE resources (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    title TEXT,
    description TEXT,
    provenance TEXT,
    rights_license TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    required_file_id TEXT NOT NULL,
    UNIQUE (work_id, id),
    FOREIGN KEY (work_id)
        REFERENCES works (id)
        ON DELETE CASCADE
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (id, required_file_id)
        REFERENCES files (resource_id, id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE files (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    name TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    status TEXT NOT NULL,
    sha256 TEXT,
    storage_pointer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (resource_id, id),
    FOREIGN KEY (resource_id)
        REFERENCES resources (id)
        ON DELETE CASCADE
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (size_bytes IS NULL OR size_bytes >= 0),
    CHECK (sha256 IS NULL OR length(sha256) = 64)
);

CREATE INDEX idx_resources_work_id ON resources (work_id);
CREATE INDEX idx_files_resource_id ON files (resource_id);
CREATE INDEX idx_files_status ON files (status);
