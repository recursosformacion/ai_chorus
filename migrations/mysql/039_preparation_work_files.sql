-- Migration 039: preparation_work_files — archivos adjuntos a trabajos de preparación
-- Referencia Files existentes en OSAP V6
-- No duplica archivos físicos
-- Referencia: arquitectura definitiva v1.0

CREATE TABLE IF NOT EXISTS preparation_work_files (
    id                  VARCHAR(191) NOT NULL PRIMARY KEY,
    preparation_work_id VARCHAR(191) NOT NULL,
    file_id             VARCHAR(191) NOT NULL COMMENT 'FK → files(id)',
    purpose             ENUM('score','part','audio','video','other') NOT NULL DEFAULT 'other',
    sort_order          INT NOT NULL DEFAULT 0,
    created_at          VARCHAR(64) NOT NULL,
    CONSTRAINT fk_pwf_prepwork FOREIGN KEY (preparation_work_id)
        REFERENCES preparation_works(id) ON DELETE CASCADE,
    CONSTRAINT fk_pwf_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Índices para búsquedas frecuentes
CREATE INDEX idx_pwf_prepwork ON preparation_work_files(preparation_work_id);
CREATE INDEX idx_pwf_file ON preparation_work_files(file_id);