-- Chorus 0.15: tablas de artículos de grupo — secciones, artículos y medios.
-- Migración desde SQLite 015_group_articles.sql (solo CREATE TABLE, los ALTER TABLE groups ya están en 001_schema.sql)

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Secciones de grupo (para organizar miembros y material)
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Artículos de grupo (noticias, anuncios, actas, etc.)
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
    KEY idx_group_articles_status (status, published_at),
    CONSTRAINT fk_group_articles_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    CONSTRAINT fk_group_articles_author FOREIGN KEY (author_user_id) REFERENCES groups(id) ON DELETE RESTRICT,
    CONSTRAINT fk_group_articles_publisher FOREIGN KEY (publisher_user_id) REFERENCES groups(id) ON DELETE SET NULL,
    CONSTRAINT fk_group_articles_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES groups(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Medios adjuntos a artículos (imágenes, vídeos, enlaces, documentos)
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
    KEY idx_group_article_media_article (article_id, position),
    CONSTRAINT fk_group_article_media_article FOREIGN KEY (article_id) REFERENCES group_articles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;