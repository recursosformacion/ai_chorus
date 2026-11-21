-- Migration 041: consolidar la identidad de los espacios
--
-- 1. owner_sub pasa a NULLABLE: sólo los espacios personales tienen
--    propietario. Un espacio de grupo/proyecto no pertenece a un usuario, y
--    meter ahí el id del grupo sería una relación semánticamente incorrecta.
-- 2. Normaliza datos históricos: owner_sub de espacios no personales que
--    contenga el id del grupo (o cualquier valor) pasa a NULL, porque no
--    interviene en la autorización (que deriva de la membresía del grupo).
-- 3. Un grupo tiene UN ÚNICO espacio general (space_type='group') y puede
--    tener varios proyectos. Se fuerza con una columna generada que sólo toma
--    valor para el espacio general, más un índice único: NULL se repite sin
--    problema, así que personal y proyectos no se ven afectados.
-- 4. Resuelve duplicados históricos conservando el espacio con más trabajos
--    (desempate: el más antiguo) y reasignando los trabajos sobrantes.
--
-- Idempotente: comprueba information_schema antes de cada operación.

-- =====================================================
-- PASO 1: owner_sub NULLABLE
-- =====================================================
SET @sql = IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces'
        AND COLUMN_NAME = 'owner_sub' AND IS_NULLABLE = 'NO') > 0,
    'ALTER TABLE spaces MODIFY COLUMN owner_sub VARCHAR(191) NULL',
    'SELECT ''spaces.owner_sub already nullable'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- =====================================================
-- PASO 2: normalizar owner_sub de espacios no personales
-- =====================================================
UPDATE spaces
SET owner_sub = NULL
WHERE space_type IN ('group', 'project') AND owner_sub IS NOT NULL;

-- =====================================================
-- PASO 3: resolver duplicados del espacio general
-- =====================================================
-- Regla determinista: de cada grupo se conserva el espacio general MAS
-- ANTIGUO (created_at, luego id) y se eliminan los posteriores, reasignando
-- antes sus trabajos. Es determinista porque created_at no cambia durante la
-- operacion, asi que el resultado no depende del orden de ejecucion.
--
-- No se usan tablas temporales: el usuario de prueba no tiene el privilegio
-- CREATE TEMPORARY TABLES.

-- 3a. Reasignar los trabajos de los espacios duplicados al mas antiguo
UPDATE preparation_works pw
JOIN spaces s ON s.id = pw.space_id
SET pw.space_id = (
        SELECT k.id
          FROM spaces k
         WHERE k.group_id = s.group_id
           AND k.space_type = 'group'
         ORDER BY k.created_at ASC, k.id ASC
         LIMIT 1
    )
WHERE s.space_type = 'group'
  AND s.id <> (
        SELECT k2.id
          FROM spaces k2
         WHERE k2.group_id = s.group_id
           AND k2.space_type = 'group'
         ORDER BY k2.created_at ASC, k2.id ASC
         LIMIT 1
  );

-- 3b. Eliminar los espacios generales duplicados (ya sin trabajos)
DELETE s FROM spaces s
JOIN spaces keep
  ON keep.group_id = s.group_id
 AND keep.space_type = 'group'
 AND (keep.created_at < s.created_at
      OR (keep.created_at = s.created_at AND keep.id < s.id))
WHERE s.space_type = 'group';

-- =====================================================
-- PASO 4: columna generada + índice único del espacio general
-- =====================================================
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces'
      AND COLUMN_NAME = 'general_group_id'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE spaces ADD COLUMN general_group_id VARCHAR(191) GENERATED ALWAYS AS (IF(space_type = ''group'', group_id, NULL)) STORED',
    'SELECT ''spaces.general_group_id already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces'
      AND INDEX_NAME = 'uq_spaces_general_group'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE UNIQUE INDEX uq_spaces_general_group ON spaces(general_group_id)',
    'SELECT ''uq_spaces_general_group already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;