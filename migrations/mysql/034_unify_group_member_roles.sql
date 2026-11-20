-- Migration 034: FK de group_members.admin_role_id y musical_role_id -> group_roles(id)
-- Las columnas ya existen desde 001_schema.sql; 033 creo columnas duplicadas
-- (group_admin_role_id / group_musical_role_id) que la API no usa y que 034 retira.
--
-- Nota: ADD CONSTRAINT / ADD INDEX no admiten IF NOT EXISTS en MariaDB 10.4, asi que
-- las comprobaciones se hacen contra information_schema para que el script sea idempotente.
SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND CONSTRAINT_NAME = 'fk_group_members_admin_role'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `group_members` ADD CONSTRAINT `fk_group_members_admin_role` FOREIGN KEY (`admin_role_id`) REFERENCES `group_roles`(`id`) ON DELETE SET NULL'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND CONSTRAINT_NAME = 'fk_group_members_musical_role'
);
SET @sql = IF(@fk_exists > 0,
    'SELECT 1',
    'ALTER TABLE `group_members` ADD CONSTRAINT `fk_group_members_musical_role` FOREIGN KEY (`musical_role_id`) REFERENCES `group_roles`(`id`) ON DELETE SET NULL'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Indices de apoyo a las FK (MariaDB crea uno por FK, se asegura por nombre)
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND INDEX_NAME = 'idx_group_members_admin_role'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_group_members_admin_role` ON `group_members` (`admin_role_id`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND INDEX_NAME = 'idx_group_members_musical_role'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_group_members_musical_role` ON `group_members` (`musical_role_id`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Retirada de las columnas duplicadas de 033 (si llegaron a crearse con su FK)
SET FOREIGN_KEY_CHECKS = 0;

SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND CONSTRAINT_NAME = 'fk_group_members_group_admin_role'
);
SET @sql = IF(@fk_exists > 0,
    'ALTER TABLE `group_members` DROP FOREIGN KEY `fk_group_members_group_admin_role`',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists = (
    SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND CONSTRAINT_NAME = 'fk_group_members_group_musical_role'
);
SET @sql = IF(@fk_exists > 0,
    'ALTER TABLE `group_members` DROP FOREIGN KEY `fk_group_members_group_musical_role`',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND INDEX_NAME = 'idx_group_members_group_admin_role'
);
SET @sql = IF(@idx_exists > 0,
    'DROP INDEX `idx_group_members_group_admin_role` ON `group_members`',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND INDEX_NAME = 'idx_group_members_group_musical_role'
);
SET @sql = IF(@idx_exists > 0,
    'DROP INDEX `idx_group_members_group_musical_role` ON `group_members`',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND COLUMN_NAME = 'group_admin_role_id'
);
SET @sql = IF(@col_exists > 0,
    'ALTER TABLE `group_members` DROP COLUMN `group_admin_role_id`',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND COLUMN_NAME = 'group_musical_role_id'
);
SET @sql = IF(@col_exists > 0,
    'ALTER TABLE `group_members` DROP COLUMN `group_musical_role_id`',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET FOREIGN_KEY_CHECKS = 1;
