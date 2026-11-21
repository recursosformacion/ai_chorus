-- Migration 039: preparation_work_files — referencias a archivos existentes
-- file_id referencia files(id) del modelo V6. No duplica archivos físicos:
-- eliminar la referencia no toca el fichero ni su propiedad.
-- Índices creados de forma condicional (idempotencia en MariaDB 10.4).

CREATE TABLE IF NOT EXISTS preparation_work_files (
    id                  VARCHAR(191) NOT NULL PRIMARY KEY,
    preparation_work_id VARCHAR(191) NOT NULL,
    file_id             VARCHAR(191) NOT NULL COMMENT 'FK -> files(id)',
    purpose             ENUM('score','part','audio','video','other') NOT NULL DEFAULT 'other',
    sort_order          INT NOT NULL DEFAULT 0,
    created_at          VARCHAR(64) NOT NULL,
    CONSTRAINT fk_pwf_prepwork FOREIGN KEY (preparation_work_id)
        REFERENCES preparation_works(id) ON DELETE CASCADE,
    CONSTRAINT fk_pwf_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_work_files' AND INDEX_NAME = 'idx_pwf_prepwork'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_pwf_prepwork ON preparation_work_files(preparation_work_id)',
    'SELECT ''idx_pwf_prepwork already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'preparation_work_files' AND INDEX_NAME = 'idx_pwf_file'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_pwf_file ON preparation_work_files(file_id)',
    'SELECT ''idx_pwf_file already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;