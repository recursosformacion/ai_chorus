-- Migration 037: spaces — tabla unificadora de espacios de trabajo
-- Soporta espacios personales, de grupo y de proyecto
-- Referencia: arquitectura definitiva v1.0

CREATE TABLE IF NOT EXISTS spaces (
    id            VARCHAR(191) NOT NULL PRIMARY KEY,
    space_type    ENUM('personal','group','project') NOT NULL,
    owner_sub     VARCHAR(191) NOT NULL COMMENT 'user_id del propietario (osap-auth)',
    group_id      VARCHAR(191) NULL COMMENT 'FK a groups(id) SOLO para space_type=group/project',
    name          VARCHAR(160) NOT NULL,
    description   TEXT NULL,
    created_at    VARCHAR(64) NOT NULL,
    updated_at    VARCHAR(64) NOT NULL,
    CONSTRAINT chk_space_group CHECK (
        (space_type = 'group' AND group_id IS NOT NULL) OR
        (space_type = 'project' AND group_id IS NOT NULL) OR
        (space_type = 'personal' AND group_id IS NULL)
    ),
    CONSTRAINT fk_space_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Índices para búsquedas frecuentes
CREATE INDEX idx_spaces_owner ON spaces(owner_sub);
CREATE INDEX idx_spaces_type ON spaces(space_type);
CREATE INDEX idx_spaces_group ON spaces(group_id);