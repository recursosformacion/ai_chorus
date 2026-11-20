-- Chorus 0.16: group_articles.scope (ámbito de visibilidad)
-- Depende de: 006_group_articles_tables.sql (group_articles table)

SET NAMES utf8mb4;

-- 1. Columna scope (condicional)
-- Valores: 'group' (solo miembros), 'entity' (entidad completa), 'public' (público)
SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_articles'
      AND COLUMN_NAME = 'scope'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `group_articles` ADD COLUMN `scope` VARCHAR(16) NOT NULL DEFAULT \'group\'',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. Check constraint para valores válidos (idempotente)
SET @ck_exists = (
    SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND CONSTRAINT_NAME = 'ck_group_articles_scope'
);
SET @sql = IF(@ck_exists = 0,
    'ALTER TABLE `group_articles` ADD CONSTRAINT `ck_group_articles_scope` CHECK (`scope` IN (\'group\', \'entity\', \'public\'))',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. Índice compuesto (scope, published_at) (idempotente)
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_articles'
      AND INDEX_NAME = 'idx_group_articles_scope_published'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_group_articles_scope_published` ON `group_articles` (`scope`, `published_at`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;