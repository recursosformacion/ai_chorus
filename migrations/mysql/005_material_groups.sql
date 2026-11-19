-- Chorus 0.15: material por grupo — columnas de grupo y sección en recursos.
-- Migración desde SQLite 013_material_groups.sql

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- resources: grupo y sección del grupo
ALTER TABLE resources
    ADD COLUMN group_id VARCHAR(191) NULL,
    ADD COLUMN group_section_id VARCHAR(191) NULL;

-- Índice para consultas de material por grupo y estado
CREATE INDEX idx_resources_group_status ON resources (group_id, material_status);

SET FOREIGN_KEY_CHECKS = 1;