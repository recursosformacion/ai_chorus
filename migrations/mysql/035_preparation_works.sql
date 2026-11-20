-- Migration 035: preparation_works — obras de preparación para «Lo que estamos preparando»
CREATE TABLE IF NOT EXISTS preparation_works (
    id VARCHAR(191) NOT NULL PRIMARY KEY,
    group_id VARCHAR(191) NOT NULL,
    title VARCHAR(500) NOT NULL,
    composer VARCHAR(500) NULL,
    folder_path VARCHAR(1000) NOT NULL COMMENT 'Ruta relativa dentro del almacenamiento privado',
    status VARCHAR(32) NOT NULL DEFAULT 'preparing' COMMENT 'preparing, ready, published, archived',
    destination_type VARCHAR(16) NOT NULL DEFAULT 'repertoire' COMMENT 'repertoire o program',
    event_name VARCHAR(500) NULL COMMENT 'Nombre del programa/concierto si destination_type=program',
    event_date VARCHAR(64) NULL COMMENT 'Fecha prevista de actuación (ISO)',
    notes LONGTEXT NULL,
    created_by VARCHAR(191) NOT NULL COMMENT 'user_sub del creador (osap-auth)',
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_preparation_works_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    KEY idx_preparation_works_group (group_id),
    KEY idx_preparation_works_status (status),
    KEY idx_preparation_works_destination (destination_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;