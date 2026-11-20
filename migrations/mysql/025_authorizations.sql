-- Chorus 0.16: authorizations (permisos desde amigos_authorizations)
-- No depende de migraciones previas

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS authorizations (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(191) NOT NULL,
    scope VARCHAR(32) NOT NULL,
    direct_publish TINYINT(1) NOT NULL DEFAULT 0,
    granted_by VARCHAR(191) NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_authorizations_scope_user (scope, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Índice user_id + scope (idempotente)
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'authorizations'
      AND INDEX_NAME = 'idx_authorizations_user'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_authorizations_user` ON `authorizations` (`user_id`, `scope`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;