-- Chorus 0.16: groups.type_code FK + join_code_expires_at
-- Depende de: 018 (group_types)
-- Temporal type: VARCHAR(64) ISO (coherente con created_at/updated_at)

SET NAMES utf8mb4;

-- 1. Columna type_code (condicional)
SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'groups'
      AND COLUMN_NAME = 'type_code'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `groups` ADD COLUMN `type_code` VARCHAR(64) NULL',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. Columna join_code_expires_at (condicional, tipo temporal VARCHAR(64))
SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'groups'
      AND COLUMN_NAME = 'join_code_expires_at'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `groups` ADD COLUMN `join_code_expires_at` VARCHAR(64) NULL',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. FK groups.type_code -> group_types.code (idempotente)
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'groups'
      AND CONSTRAINT_NAME = 'fk_groups_type_code'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `groups` ADD CONSTRAINT `fk_groups_type_code` FOREIGN KEY (`type_code`) REFERENCES `group_types`(`code`) ON DELETE SET NULL'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4. Índice en type_code (idempotente)
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'groups'
      AND INDEX_NAME = 'idx_groups_type_code'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_groups_type_code` ON `groups` (`type_code`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;