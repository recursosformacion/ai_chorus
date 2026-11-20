-- Chorus 0.16: performance_groups (M:N actuaciones ↔ grupos)
-- Depende de: 026 (performances), 001_schema.sql (groups)

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS performance_groups (
    performance_id VARCHAR(191) NOT NULL,
    group_id VARCHAR(191) NOT NULL,
    role VARCHAR(16) NOT NULL DEFAULT 'participant',
    PRIMARY KEY (performance_id, group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- FK a performances (idempotente)
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'performance_groups'
      AND CONSTRAINT_NAME = 'fk_perf_groups_performance'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `performance_groups` ADD CONSTRAINT `fk_perf_groups_performance` FOREIGN KEY (`performance_id`) REFERENCES `performances`(`id`) ON DELETE CASCADE'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- FK a groups (idempotente)
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'performance_groups'
      AND CONSTRAINT_NAME = 'fk_perf_groups_group'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `performance_groups` ADD CONSTRAINT `fk_perf_groups_group` FOREIGN KEY (`group_id`) REFERENCES `groups`(`id`) ON DELETE CASCADE'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Índice group_id (idempotente)
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'performance_groups'
      AND INDEX_NAME = 'idx_perf_groups_group'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_perf_groups_group` ON `performance_groups` (`group_id`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;