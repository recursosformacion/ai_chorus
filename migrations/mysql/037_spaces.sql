-- Migration 037: spaces — tabla unificadora de espacios de trabajo
-- Soporta espacios personales, de grupo y de proyecto.
-- Un espacio personal no necesita fila en groups.
-- Los índices se crean de forma condicional (idempotencia en MariaDB 10.4).

CREATE TABLE IF NOT EXISTS spaces (
    id            VARCHAR(191) NOT NULL PRIMARY KEY,
    space_type    ENUM('personal','group','project') NOT NULL,
    owner_sub     VARCHAR(191) NOT NULL COMMENT 'user_id del propietario (osap-auth)',
    group_id      VARCHAR(191) NULL COMMENT 'FK a groups(id) para space_type group/project',
    name          VARCHAR(160) NOT NULL,
    description   TEXT NULL,
    created_at    VARCHAR(64) NOT NULL,
    updated_at    VARCHAR(64) NOT NULL,
    CONSTRAINT chk_space_group CHECK (
        (space_type IN ('group','project') AND group_id IS NOT NULL) OR
        (space_type = 'personal' AND group_id IS NULL)
    ),
    CONSTRAINT fk_space_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces' AND INDEX_NAME = 'idx_spaces_owner'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_spaces_owner ON spaces(owner_sub)',
    'SELECT ''idx_spaces_owner already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces' AND INDEX_NAME = 'idx_spaces_type'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_spaces_type ON spaces(space_type)',
    'SELECT ''idx_spaces_type already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spaces' AND INDEX_NAME = 'idx_spaces_group'
);
SET @sql = IF(@idx_exists = 0,
    'CREATE INDEX idx_spaces_group ON spaces(group_id)',
    'SELECT ''idx_spaces_group already present'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;