-- Chorus 0.16: group_history (auditoría de membresía desde amigos_group_history)
-- Depende de: 001_schema.sql (groups table con id VARCHAR(191) utf8mb4_unicode_ci)

SET NAMES utf8mb4;

-- 1. Tabla group_history (condicional, tipos exactos para FK)
CREATE TABLE IF NOT EXISTS group_history (
    id VARCHAR(191) PRIMARY KEY,
    group_id VARCHAR(191) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    member_user_id VARCHAR(191) NULL,
    person_name VARCHAR(255) NULL,
    role VARCHAR(32) NULL,
    start_date VARCHAR(64) NULL,
    end_date VARCHAR(64) NULL,
    notes LONGTEXT NULL,
    created_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. FK a groups (idempotente, ON DELETE CASCADE)
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_history'
      AND CONSTRAINT_NAME = 'fk_group_history_group'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `group_history` ADD CONSTRAINT `fk_group_history_group` FOREIGN KEY (`group_id`) REFERENCES `groups`(`id`) ON DELETE CASCADE'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. Índice group_id + created_at (idempotente)
SET @idx_group = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_history'
      AND INDEX_NAME = 'idx_group_history_group'
);
SET @sql = IF(@idx_group = 0,
    'CREATE INDEX `idx_group_history_group` ON `group_history` (`group_id`, `created_at`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4. Índice member_user_id (idempotente)
SET @idx_member = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_history'
      AND INDEX_NAME = 'idx_group_history_member'
);
SET @sql = IF(@idx_member = 0,
    'CREATE INDEX `idx_group_history_member` ON `group_history` (`member_user_id`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;