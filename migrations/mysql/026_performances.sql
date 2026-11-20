-- Chorus 0.16: performances (actuaciones desde amigos_actuaciones)
-- Separada de events (agenda/rehearsals). No depende de migraciones previas.
-- Registro único en OSAP pendiente de clasificación funcional.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS performances (
    id VARCHAR(191) PRIMARY KEY,
    slug VARCHAR(200) NOT NULL UNIQUE,
    title VARCHAR(512) NOT NULL,
    summary TEXT NULL,
    description LONGTEXT NULL,
    image_url VARCHAR(1024) NULL,
    kind VARCHAR(32) NOT NULL DEFAULT 'concert',
    modality VARCHAR(16) NOT NULL DEFAULT 'onsite',
    event_status VARCHAR(16) NOT NULL DEFAULT 'scheduled',
    editorial_status VARCHAR(16) NOT NULL DEFAULT 'draft',
    starts_on VARCHAR(64) NOT NULL,
    starts_at VARCHAR(64) NULL,
    ends_at VARCHAR(64) NULL,
    venue_address VARCHAR(512) NULL,
    latitude DECIMAL(10,8) NULL,
    longitude DECIMAL(11,8) NULL,
    map_url VARCHAR(1024) NULL,
    organizer_name VARCHAR(255) NULL,
    organizer_website VARCHAR(1024) NULL,
    event_url VARCHAR(1024) NULL,
    tickets_url VARCHAR(1024) NULL,
    price VARCHAR(128) NULL,
    access_info TEXT NULL,
    public_contact VARCHAR(255) NULL,
    registration_deadline VARCHAR(64) NULL,
    weight INT NULL,
    views INT NULL DEFAULT 0,
    expands INT NULL DEFAULT 0,
    buys INT NULL DEFAULT 0,
    source_email VARCHAR(254) NULL,
    source_note TEXT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    published_at VARCHAR(64) NULL,
    cancelled_at VARCHAR(64) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Índice starts (idempotente)
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'performances'
      AND INDEX_NAME = 'idx_performances_starts'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_performances_starts` ON `performances` (`starts_on`, `starts_at`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice status (idempotente)
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'performances'
      AND INDEX_NAME = 'idx_performances_status'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_performances_status` ON `performances` (`event_status`, `editorial_status`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;