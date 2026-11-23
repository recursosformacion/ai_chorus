-- Migration 042: permitir proyectos personales independientes.
--
-- Los proyectos pueden ser privados (owner_sub, sin group_id) o compartidos
-- (group_id, sin owner_sub). Los espacios personales siguen siendo privados y
-- los espacios generales de grupo siguen asociados obligatoriamente a un grupo.
-- No mueve ni elimina datos.

SET @constraint_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'spaces'
      AND CONSTRAINT_NAME = 'chk_space_group'
      AND CONSTRAINT_TYPE = 'CHECK'
);
SET @sql = IF(@constraint_exists > 0,
    'ALTER TABLE spaces DROP CONSTRAINT chk_space_group',
    'SELECT ''chk_space_group already absent'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @constraint_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'spaces'
      AND CONSTRAINT_NAME = 'chk_space_ownership'
      AND CONSTRAINT_TYPE = 'CHECK'
);
SET @sql = IF(@constraint_exists = 0,
    'ALTER TABLE spaces ADD CONSTRAINT chk_space_ownership CHECK (
        (space_type = ''personal'' AND owner_sub IS NOT NULL AND group_id IS NULL)
        OR (space_type = ''group'' AND owner_sub IS NULL AND group_id IS NOT NULL)
        OR (space_type = ''project'' AND (
            (owner_sub IS NOT NULL AND group_id IS NULL)
            OR (owner_sub IS NULL AND group_id IS NOT NULL)
        ))
    )',
    'SELECT ''chk_space_ownership already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
