-- Chorus 0.15: corrección de claves foráneas en group_articles.
-- Migración 017: elimina FKs incorrectas author_user_id, publisher_user_id, reviewed_by → groups.id.
-- Los identificadores de usuario proceden de osap-auth, no de groups.
-- Idempotente: comprueba existencia en information_schema antes de DROP.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Eliminar fk_group_articles_author si existe
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_articles'
      AND CONSTRAINT_NAME = 'fk_group_articles_author'
);
SET @sql = IF(@fk_exists > 0,
    'ALTER TABLE `group_articles` DROP FOREIGN KEY `fk_group_articles_author`',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Eliminar fk_group_articles_publisher si existe
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_articles'
      AND CONSTRAINT_NAME = 'fk_group_articles_publisher'
);
SET @sql = IF(@fk_exists > 0,
    'ALTER TABLE `group_articles` DROP FOREIGN KEY `fk_group_articles_publisher`',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Eliminar fk_group_articles_reviewed_by si existe
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_articles'
      AND CONSTRAINT_NAME = 'fk_group_articles_reviewed_by'
);
SET @sql = IF(@fk_exists > 0,
    'ALTER TABLE `group_articles` DROP FOREIGN KEY `fk_group_articles_reviewed_by`',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET FOREIGN_KEY_CHECKS = 1;