-- Chorus 0.14: grupos nativos y artículos de grupo.
ALTER TABLE groups
    ADD COLUMN slug VARCHAR(191) NULL,
    ADD COLUMN kind VARCHAR(32) NOT NULL DEFAULT 'grupo',
    ADD COLUMN description TEXT NULL,
    ADD COLUMN image_url VARCHAR(1024) NULL,
    ADD COLUMN website VARCHAR(1024) NULL,
    ADD COLUMN email VARCHAR(254) NULL,
    ADD COLUMN logo_url VARCHAR(1024) NULL,
    ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'active',
    ADD COLUMN editorial_mode VARCHAR(16) NOT NULL DEFAULT 'moderated',
    ADD COLUMN technical_description TEXT NULL;

CREATE TABLE IF NOT EXISTS group_sections (
    id VARCHAR(191) PRIMARY KEY,
    group_id VARCHAR(191) NOT NULL,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    scope VARCHAR(16) NOT NULL DEFAULT 'section',
    parent_id VARCHAR(191) NULL,
    sort_order INT NOT NULL DEFAULT 0,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_group_sections_code (group_id, code, scope)
);

CREATE TABLE IF NOT EXISTS group_articles (
    id VARCHAR(191) PRIMARY KEY,
    legacy_id VARCHAR(64) NULL UNIQUE,
    group_id VARCHAR(191) NOT NULL,
    title VARCHAR(512) NOT NULL,
    slug VARCHAR(200) NOT NULL,
    summary TEXT NULL,
    body LONGTEXT NULL,
    cover_url VARCHAR(1024) NULL,
    event_date VARCHAR(32) NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'draft',
    author_user_id VARCHAR(191) NOT NULL,
    publisher_user_id VARCHAR(191) NULL,
    reviewed_by VARCHAR(191) NULL,
    reviewed_at VARCHAR(64) NULL,
    review_note VARCHAR(512) NULL,
    published_at VARCHAR(64) NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_group_articles_slug (group_id, slug),
    KEY idx_group_articles_group (group_id, event_date),
    KEY idx_group_articles_status (status, published_at)
);

CREATE TABLE IF NOT EXISTS group_article_media (
    id VARCHAR(191) PRIMARY KEY,
    legacy_id VARCHAR(64) NULL UNIQUE,
    article_id VARCHAR(191) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    url VARCHAR(1024) NOT NULL,
    provider VARCHAR(32) NULL,
    video_id VARCHAR(64) NULL,
    caption VARCHAR(512) NULL,
    credit VARCHAR(512) NULL,
    position INT NOT NULL DEFAULT 0,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_group_article_media_article (article_id, position)
);
