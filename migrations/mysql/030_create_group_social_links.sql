-- Migration 030: Create group_social_links table for amigos_group_links
CREATE TABLE IF NOT EXISTS group_social_links (
    id VARCHAR(191) NOT NULL PRIMARY KEY,
    legacy_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Original ID from amigos_group_links',
    group_id VARCHAR(191) NOT NULL,
    kind VARCHAR(32) NOT NULL COMMENT 'instagram, facebook, twitter, youtube, website, other',
    label VARCHAR(160) NULL,
    url VARCHAR(1024) NOT NULL,
    position INT NOT NULL DEFAULT 0,
    created_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_group_social_links_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    KEY idx_group_social_links_group (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;