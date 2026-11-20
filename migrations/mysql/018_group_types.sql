-- Chorus 0.16: tabla de tipos de grupo (taxonomía).
-- Fuente: OSAP amigos_group_types (48 registros, SIN created_at/updated_at).
-- Base para groups.type_code (migración 019) y plantillas de roles/secciones.
-- Idempotente: verifica existencia antes de crear.

SET NAMES utf8mb4;

-- 1. Tabla group_types (estructura fiel a origen)
CREATE TABLE IF NOT EXISTS group_types (
    code VARCHAR(64) PRIMARY KEY,
    parent_code VARCHAR(64) NULL,
    name VARCHAR(160) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. FK autorreferenciada (idempotente: solo si no existe)
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_types'
      AND CONSTRAINT_NAME = 'fk_group_types_parent'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `group_types` ADD CONSTRAINT `fk_group_types_parent` FOREIGN KEY (`parent_code`) REFERENCES `group_types`(`code`) ON DELETE SET NULL'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. Índices (idempotentes con IF NOT EXISTS via creación condicional)
SET @idx_parent = (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'group_types' AND INDEX_NAME = 'idx_group_types_parent');
SET @sql = IF(@idx_parent = 0, 'CREATE INDEX idx_group_types_parent ON group_types (parent_code)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_kind = (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'group_types' AND INDEX_NAME = 'idx_group_types_kind');
SET @sql = IF(@idx_kind = 0, 'CREATE INDEX idx_group_types_kind ON group_types (kind)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_sort = (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'group_types' AND INDEX_NAME = 'idx_group_types_sort');
SET @sql = IF(@idx_sort = 0, 'CREATE INDEX idx_group_types_sort ON group_types (parent_code, sort_order)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;