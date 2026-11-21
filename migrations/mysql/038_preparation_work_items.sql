-- Migration 038: preparation_work_items — items de trabajos de preparación
-- Relaciona trabajos de preparación con obras y recursos
-- Integridad: Resource debe pertenecer al Work indicado (FK compuesta)
-- Referencia: arquitectura definitiva v1.0

CREATE TABLE IF NOT EXISTS preparation_work_items (
    id                  VARCHAR(191) NOT NULL PRIMARY KEY,
    preparation_work_id VARCHAR(191) NOT NULL,
    work_id             VARCHAR(191) NOT NULL COMMENT 'FK → works(id) (obra canónica)',
    resource_id         VARCHAR(191) NOT NULL COMMENT 'FK → resources(id) (versión/arreglo)',
    voice_label         VARCHAR(64) NULL COMMENT 'Soprano, Tenor, Violín I, etc.',
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
    -- FK compuesta: Resource debe pertenecer a Work
    CONSTRAINT fk_pwi_work_resource FOREIGN KEY (work_id, resource_id)
        REFERENCES resources(work_id, id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Índices para búsquedas frecuentes
CREATE INDEX idx_pwi_prepwork ON preparation_work_items(preparation_work_id);
CREATE INDEX idx_pwi_work ON preparation_work_items(work_id);
CREATE INDEX idx_pwi_resource ON preparation_work_items(resource_id);