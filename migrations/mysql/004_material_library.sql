-- Chorus 0.15: biblioteca de material — columnas de versión, parte, estado y metadatos de archivo.
-- Migración desde SQLite 012_material_library.sql

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- resources: versión, parte, estado de material
ALTER TABLE resources
    ADD COLUMN version_label VARCHAR(191) NULL,
    ADD COLUMN part_label VARCHAR(191) NULL,
    ADD COLUMN material_status VARCHAR(32) NOT NULL DEFAULT 'draft';

-- files: ruta de carpeta, nombre para mostrar, nombre original
ALTER TABLE files
    ADD COLUMN folder_path VARCHAR(1000) NULL,
    ADD COLUMN display_name VARCHAR(500) NULL,
    ADD COLUMN original_name VARCHAR(500) NULL;

-- Índice para consultas de material por obra y estado
CREATE INDEX idx_resources_material ON resources (work_id, material_status);

SET FOREIGN_KEY_CHECKS = 1;