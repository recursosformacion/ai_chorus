-- Chorus 0.16: role_templates (plantillas de rol desde amigos_role_templates)
-- Depende de: 018_group_types.sql (group_types.code VARCHAR(64) utf8mb4_unicode_ci)

SET NAMES utf8mb4;

-- 1. Tabla role_templates (condicional, tipos exactos para FK)
CREATE TABLE IF NOT EXISTS role_templates (
    id VARCHAR(191) PRIMARY KEY,
    type_code VARCHAR(64) NOT NULL,
    scope VARCHAR(16) NOT NULL,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_role_templates_type_scope_code (type_code, scope, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. FK a group_types (idempotente, ON DELETE CASCADE)
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'role_templates'
      AND CONSTRAINT_NAME = 'fk_role_templates_type'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `role_templates` ADD CONSTRAINT `fk_role_templates_type` FOREIGN KEY (`type_code`) REFERENCES `group_types`(`code`) ON DELETE CASCADE'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. Índice (idempotente) para consultas ordenadas
SET @idx = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'role_templates'
      AND INDEX_NAME = 'idx_role_templates_type_sort'
);
SET @sql = IF(@idx = 0,
    'CREATE INDEX `idx_role_templates_type_sort` ON `role_templates` (`type_code`, `scope`, `sort_order`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;