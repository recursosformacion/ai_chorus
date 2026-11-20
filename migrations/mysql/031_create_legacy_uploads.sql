-- Migration 031: Create legacy_uploads table for amigos_uploads (file_id incompatibility)
-- OSAP uses BIGINT file_id, Chorus uses VARCHAR(191) UUID for files.
-- No equivalences invented; preserve original references for traceability.
CREATE TABLE IF NOT EXISTS legacy_uploads (
    id VARCHAR(191) NOT NULL PRIMARY KEY,
    legacy_file_id BIGINT UNSIGNED NOT NULL UNIQUE COMMENT 'Original file_id from amigos_uploads',
    group_id VARCHAR(191) NULL COMMENT 'Empty string in source becomes NULL',
    mime_type VARCHAR(128) NOT NULL,
    size_bytes BIGINT UNSIGNED NOT NULL,
    created_by VARCHAR(191) NOT NULL COMMENT 'User UUID from osap-auth',
    created_at VARCHAR(64) NOT NULL,
    chorus_file_id VARCHAR(191) NULL COMMENT 'Future link to Chorus files if equivalence established',
    CONSTRAINT fk_legacy_uploads_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL,
    KEY idx_legacy_uploads_group (group_id),
    KEY idx_legacy_uploads_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;