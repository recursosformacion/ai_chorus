-- Migration 040: Migrar preparation_works de group_id a space_id
--
-- Pasos:
--   1. Añadir space_id (nullable temporalmente) si no existe.
--   2. Crear un espacio de grupo por cada grupo existente.
--   3. Asociar cada trabajo de preparación a su espacio.
--   4. ABORTAR de forma inequívoca si queda algún trabajo sin asociar.
--   5. Añadir FK space_id -> spaces(id) ON DELETE RESTRICT.
--   6. Dejar space_id NOT NULL.
--   7. Eliminar la dependencia antigua group_id (FK, índice y columna).
--   8. Crear índices de apoyo.
--
-- Notas MariaDB 10.4.32:
--   - SIGNAL no está soportado en el protocolo de sentencias preparadas (error 1295),
--     por lo que el aborto del paso 4 se fuerza con una referencia a una tabla
--     inexistente cuyo nombre explica el motivo. Así la migración falla, no se
--     registra como aplicada y el runner se detiene.
--   - ADD/DROP CONSTRAINT e IF NOT EXISTS no están disponibles para FKs: se
--     comprueba information_schema antes de cada operación (patrón idempotente).

-- =====================================================
-- PASO 1: Añadir columna space_id (nullable temporalmente)
-- =====================================================
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND COLUMN_NAME = 'space_id'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE preparation_works ADD COLUMN space_id VARCHAR(191) NULL AFTER id',
    'SELECT ''space_id already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- =====================================================
-- PASO 2: Crear un espacio por cada grupo existente
-- =====================================================
INSERT IGNORE INTO spaces (id, space_type, owner_sub, group_id, name, created_at, updated_at)
SELECT g.id, 'group', g.created_by, g.id, g.name, g.created_at, g.updated_at
FROM groups g
LEFT JOIN spaces s ON s.group_id = g.id AND s.space_type = 'group'
WHERE s.id IS NULL;

-- =====================================================
-- PASO 3: Asociar los trabajos existentes a su espacio
-- =====================================================
-- Sólo aplica si group_id todavía existe ( BD no migrada ). En una BD ya
-- migrada la columna no está, por lo que el paso se omite (idempotencia ).
SET @group_col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND COLUMN_NAME = 'group_id'
);
SET @sql = IF(@group_col_exists > 0,
    'UPDATE preparation_works pw JOIN spaces s ON s.group_id = pw.group_id AND s.space_type = ''group'' SET pw.space_id = s.id WHERE pw.space_id IS NULL',
    'SELECT ''group_id absent: nothing to migrate'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- =====================================================
-- PASO 4: ABORTAR si queda algún trabajo sin migrar
-- =====================================================
-- Si unmigrated_count > 0 se ejecuta un SELECT sobre una tabla inexistente,
-- lo que provoca el error 1146 y detiene la migración sin registrarla.
-- >>> BEGIN ABORT CHECK 040
SET @unmigrated_count = (
    SELECT COUNT(*) FROM preparation_works WHERE space_id IS NULL
);
SET @sql = IF(@unmigrated_count > 0,
    'SELECT * FROM `migration_040_abort_unmigrated_preparation_works`',
    'SELECT ''all preparation_works migrated'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
-- <<< END ABORT CHECK 040

-- =====================================================
-- PASO 5: FK space_id -> spaces(id)
-- =====================================================
SET @fk_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND CONSTRAINT_NAME = 'fk_prepworks_space'
);
SET @sql = IF(@fk_exists = 0,
    'ALTER TABLE preparation_works ADD CONSTRAINT fk_prepworks_space FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE RESTRICT',
    'SELECT ''fk_prepworks_space already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- =====================================================
-- PASO 6: space_id NOT NULL
-- =====================================================
ALTER TABLE preparation_works MODIFY COLUMN space_id VARCHAR(191) NOT NULL;

-- =====================================================
-- PASO 7: Eliminar dependencia antigua group_id
-- =====================================================
SET FOREIGN_KEY_CHECKS = 0;

SET @fk_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND CONSTRAINT_NAME = 'fk_preparation_works_group'
);
SET @sql = IF(@fk_exists > 0,
    'ALTER TABLE preparation_works DROP FOREIGN KEY fk_preparation_works_group',
    'SELECT ''fk_preparation_works_group absent'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND INDEX_NAME = 'idx_preparation_works_group'
);
SET @sql = IF(@idx_exists > 0,
    'DROP INDEX idx_preparation_works_group ON preparation_works',
    'SELECT ''idx_preparation_works_group absent'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND COLUMN_NAME = 'group_id'
);
SET @sql = IF(@col_exists > 0,
    'ALTER TABLE preparation_works DROP COLUMN group_id',
    'SELECT ''group_id absent'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================
-- PASO 8: Índices de apoyo
-- =====================================================
SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND INDEX_NAME = 'idx_preparation_works_space'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_preparation_works_space ON preparation_works(space_id)',
    'SELECT ''idx_preparation_works_space already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;