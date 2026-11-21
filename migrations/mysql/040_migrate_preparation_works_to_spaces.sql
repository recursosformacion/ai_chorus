-- Migration 040: Migrar preparation_works de group_id a space_id
-- 1. Añadir columna space_id (nullable temporalmente)
-- 2. Crear espacios para grupos existentes
-- 3. Migrar datos
-- 4. Hacer space_id NOT NULL
-- 5. Eliminar dependencia de group_id (cuando el código esté listo)
-- Referencia: arquitectura definitiva v1.0

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
    'SELECT "Column space_id already exists"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- =====================================================
-- PASO 2: Crear espacios para grupos existentes
-- =====================================================
INSERT IGNORE INTO spaces (id, space_type, owner_sub, group_id, name, created_at, updated_at)
SELECT g.id, 'group', g.created_by, g.id, g.name, g.created_at, g.updated_at
FROM groups g
LEFT JOIN spaces s ON s.group_id = g.id AND s.space_type = 'group'
WHERE s.id IS NULL;

-- =====================================================
-- PASO 3: Migrar preparation_works existentes
-- =====================================================
UPDATE preparation_works pw
JOIN spaces s ON s.group_id = pw.group_id AND s.space_type = 'group'
SET pw.space_id = s.id
WHERE pw.space_id IS NULL;

-- =====================================================
-- PASO 4: Verificar que no quedan NULLs
-- =====================================================
-- Este SELECT debe devolver 0 filas. Si devuelve >0, hay trabajos sin migrar.
SELECT COUNT(*) AS unmigrated_count
FROM preparation_works
WHERE space_id IS NULL;

-- =====================================================
-- PASO 5: Añadir FK y hacer NOT NULL
-- =====================================================
SET @fk_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND CONSTRAINT_NAME = 'fk_prepworks_space'
);
SET @sql = IF(@fk_exists = 0,
    'ALTER TABLE preparation_works ADD CONSTRAINT fk_prepworks_space FOREIGN KEY (space_id) REFERENCES spaces(id) ON DELETE RESTRICT',
    'SELECT "FK fk_prepworks_space already exists"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Hacer space_id NOT NULL (solo si no hay NULLs)
SET @null_count = (
    SELECT COUNT(*) FROM preparation_works WHERE space_id IS NULL
);
SET @sql = IF(@null_count = 0,
    'ALTER TABLE preparation_works MODIFY COLUMN space_id VARCHAR(191) NOT NULL',
    'SELECT "Cannot make space_id NOT NULL: there are NULL values"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- =====================================================
-- PASO 6: Eliminar dependencia antigua de group_id
-- NOTA: Este paso se ejecuta DESPUÉS de que el código esté adaptado
-- Por ahora, comentamos las siguientes líneas para mantener compatibilidad
-- =====================================================

-- Descomentar cuando el código esté completamente adaptado:
-- SET @fk_exists = (
--     SELECT COUNT(*) FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
--     WHERE CONSTRAINT_SCHEMA = DATABASE()
--       AND TABLE_NAME = 'preparation_works'
--       AND CONSTRAINT_NAME = 'fk_preparation_works_group'
-- );
-- SET @sql = IF(@fk_exists > 0,
--     'ALTER TABLE preparation_works DROP FOREIGN KEY fk_preparation_works_group',
--     'SELECT "FK fk_preparation_works_group does not exist"'
-- );
-- PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- SET @idx_exists = (
--     SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
--     WHERE TABLE_SCHEMA = DATABASE()
--       AND TABLE_NAME = 'preparation_works'
--       AND INDEX_NAME = 'idx_preparation_works_group'
-- );
-- SET @sql = IF(@idx_exists > 0,
--     'DROP INDEX idx_preparation_works_group ON preparation_works',
--     'SELECT "Index idx_preparation_works_group does not exist"'
-- );
-- PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- SET @col_exists = (
--     SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
--     WHERE TABLE_SCHEMA = DATABASE()
--       AND TABLE_NAME = 'preparation_works'
--       AND COLUMN_NAME = 'group_id'
-- );
-- SET @sql = IF(@col_exists > 0,
--     'ALTER TABLE preparation_works DROP COLUMN group_id',
--     'SELECT "Column group_id does not exist"'
-- );
-- PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- =====================================================
-- PASO 7: Crear índices para búsquedas frecuentes
-- =====================================================
SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'preparation_works'
      AND INDEX_NAME = 'idx_preparation_works_space'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_preparation_works_space ON preparation_works(space_id)',
    'SELECT "Index idx_preparation_works_space already exists"'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;