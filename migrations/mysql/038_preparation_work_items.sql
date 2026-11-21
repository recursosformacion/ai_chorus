-- Migration 038: preparation_work_items — obras y recursos de un trabajo
-- Integridad: el Resource debe pertenecer al Work indicado, garantizado por la
-- FK compuesta (work_id, resource_id) -> resources(work_id, id).
-- Índices creados de forma condicional (idempotencia en MariaDB 10.4).

CREATE TABLE IF NOT EXISTS preparation_work_items (
    id                  VARCHAR(191) NOT NULL PRIMARY KEY,
    preparation_work_id VARCHAR(191) NOT NULL,
    work_id             VARCHAR(191) NOT NULL COMMENT 'FK -> works(id)',
    resource_id         VARCHAR(191) NOT NULL COMMENT 'FK -> resources(id)',
    voice_label         VARCHAR(64) NULL,
    instrument          VARCHAR(64) NULL,
    custom_title        VARCHAR(200) NULL,
    sort_order          INT NOT NULL DEFAULT 0,
    status              ENUM('pending','rehearsing','ready','archived') NOT NULL DEFAULT 'pending',
    notes               LONGTEXT NULL,
    created_at          VARCHAR(64) NOT NULL,
    updated_at          VARCHAR(64) NOT NULL,
    CONSTRAINT fk_pwi_prepwork FOREIGN KEY (preparation_work_id)
        REFERENCES preparation_works(id) ON DELETE CASCADE,
    CONSTRAINT fk_pwi_work FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE RESTRICT,
    CONSTRAINT fk_pwi_resource FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE RESTRICT,
    CONSTRAINT fk_pwi_work_resource FOREIGN KEY (work_id, resource_id)
        REFERENCES resources(work_id, id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_work_items' AND INDEX_NAME = 'idx_pwi_prepwork'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_pwi_prepwork ON preparation_work_items(preparation_work_id)',
    'SELECT ''idx_pwi_prepwork already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_work_items' AND INDEX_NAME = 'idx_pwi_work'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_pwi_work ON preparation_work_items(work_id)',
    'SELECT ''idx_pwi_work already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_work_items' AND INDEX_NAME = 'idx_pwi_resource'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_pwi_resource ON preparation_work_items(resource_id)',
    'SELECT ''idx_pwi_resource already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;