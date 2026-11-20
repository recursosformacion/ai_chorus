-- Chorus 0.16: group_members.granted_by (referencia a usuario externo osap-auth)
-- No depende de migraciones previas
-- joined_at ya existe; created_at NO se anade (se migrara amigos_members.created_at -> joined_at)
-- section (texto) se mantiene deprecated; section_id (FK) es la referencia canonica

SET NAMES utf8mb4;

-- 1. Columna granted_by (condicional)
SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND COLUMN_NAME = 'granted_by'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE `group_members` ADD COLUMN `granted_by` VARCHAR(191) NULL',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. Índice en granted_by (idempotente - útil para consultas "quién concedió membresías")
SET @idx_exists = (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'group_members'
      AND INDEX_NAME = 'idx_group_members_granted_by'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX `idx_group_members_granted_by` ON `group_members` (`granted_by`)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;