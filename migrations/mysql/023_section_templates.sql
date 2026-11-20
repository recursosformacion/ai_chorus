-- Chorus 0.16: section_templates (plantillas de sección desde amigos_section_templates)
-- Depende de: 018_group_types.sql (group_types.code VARCHAR(64) utf8mb4_unicode_ci)

SET NAMES utf8mb4;

-- 1. Tabla section_templates (condicional, tipos exactos para FK)
CREATE TABLE IF NOT EXISTS section_templates (
    id VARCHAR(191) PRIMARY KEY,
    type_code VARCHAR(64) NOT NULL,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_section_templates_type_code (type_code, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. FK a group_types (idempotente, ON DELETE CASCADE)
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'section_templates'
      AND CONSTRAINT_NAME = 'fk_section_templates_type'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `section_templates` ADD CONSTRAINT `fk_section_templates_type` FOREIGN KEY (`type_code`) REFERENCES `group_types`(`code`) ON DELETE CASCADE'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. Índice (type_code, sort_order) (idempotente)
-- Justificación: la restricción única (type_code, code) no cubre sort_order.
-- Consultas previstas: listar plantillas por tipo ordenadas por sort_order.
SET @idx_sort = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'section_templates'
      AND INDEX_NAME = 'idx_section_templates_type_sort'
);
SET @sql = IF(@idx_sort = 0,
    'CREATE INDEX `idx_section_templates_type_sort` ON `section_templates` (`type_code`, `sort_order`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;