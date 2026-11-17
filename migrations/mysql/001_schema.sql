-- Esquema MySQL/MariaDB de Chorus (producción y desarrollo).
-- Los identificadores son cadenas; las fechas ISO se guardan como VARCHAR para
-- conservar exactamente el formato que ya usa la API.
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS chorus_schema_migrations (
    name VARCHAR(191) PRIMARY KEY,
    applied_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS works (
    id VARCHAR(191) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    subtitle VARCHAR(500) NULL,
    catalogue VARCHAR(255) NULL,
    year VARCHAR(64) NULL,
    description LONGTEXT NULL,
    language VARCHAR(32) NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    required_resource_id VARCHAR(191) NOT NULL,
    owner_sub VARCHAR(191) NULL,
    UNIQUE KEY uq_works_resource (id, required_resource_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS resources (
    id VARCHAR(191) PRIMARY KEY,
    work_id VARCHAR(191) NOT NULL,
    resource_type VARCHAR(80) NOT NULL,
    title VARCHAR(500) NULL,
    description LONGTEXT NULL,
    provenance VARCHAR(255) NULL,
    rights_license VARCHAR(255) NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    required_file_id VARCHAR(191) NOT NULL,
    UNIQUE KEY uq_resources_work (work_id, id),
    CONSTRAINT fk_resources_work FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS files (
    id VARCHAR(191) PRIMARY KEY,
    resource_id VARCHAR(191) NOT NULL,
    name VARCHAR(500) NOT NULL,
    mime_type VARCHAR(191) NULL,
    size_bytes BIGINT NULL,
    status VARCHAR(32) NOT NULL,
    sha256 CHAR(64) NULL,
    storage_pointer VARCHAR(1000) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_files_resource (resource_id, id),
    CONSTRAINT fk_files_resource FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS creation_drafts (
    id VARCHAR(191) PRIMARY KEY,
    owner_sub VARCHAR(191) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'editing',
    source_kind VARCHAR(32) NOT NULL DEFAULT 'blank',
    title VARCHAR(500) NULL,
    resource_type VARCHAR(80) NOT NULL DEFAULT 'score',
    source_work_id VARCHAR(191) NULL,
    source_representation_id VARCHAR(191) NULL,
    source_provider VARCHAR(80) NULL,
    source_format VARCHAR(80) NULL,
    source_file_name VARCHAR(500) NULL,
    source_file_pointer VARCHAR(1000) NULL,
    source_sha256 CHAR(64) NULL,
    source_rights_license VARCHAR(255) NULL,
    materialized_work_id VARCHAR(191) NULL UNIQUE,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    CONSTRAINT ck_draft_source CHECK (
        (source_kind='blank' AND source_work_id IS NULL AND source_representation_id IS NULL)
        OR (source_kind='osap' AND source_work_id IS NOT NULL AND source_representation_id IS NOT NULL)
        OR (source_kind='local' AND source_work_id IS NOT NULL)
    ),
    CONSTRAINT ck_draft_status CHECK (
        (status='materialized' AND materialized_work_id IS NOT NULL)
        OR (status<>'materialized' AND materialized_work_id IS NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS editor_source_tokens (
    token_hash CHAR(64) PRIMARY KEY,
    draft_id VARCHAR(191) NOT NULL,
    expires_at VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_source_token_draft FOREIGN KEY (draft_id) REFERENCES creation_drafts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS library_items (
    id VARCHAR(191) PRIMARY KEY,
    owner_sub VARCHAR(191) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    work_id VARCHAR(191) NULL,
    provider VARCHAR(80) NULL,
    external_work_id VARCHAR(191) NULL,
    external_resource_id VARCHAR(191) NULL,
    title VARCHAR(500) NOT NULL,
    subtitle VARCHAR(500) NULL,
    metadata_json LONGTEXT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    KEY idx_library_owner (owner_sub, created_at),
    CONSTRAINT fk_library_work FOREIGN KEY (work_id) REFERENCES works(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collections (
    id VARCHAR(191) PRIMARY KEY,
    owner_sub VARCHAR(191) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description LONGTEXT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_collection_owner_name (owner_sub, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collection_items (
    collection_id VARCHAR(191) NOT NULL,
    library_item_id VARCHAR(191) NOT NULL,
    position INT NOT NULL DEFAULT 0,
    added_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (collection_id, library_item_id),
    CONSTRAINT fk_collection_item_collection FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    CONSTRAINT fk_collection_item_library FOREIGN KEY (library_item_id) REFERENCES library_items(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS oidc_states (
    state VARCHAR(191) PRIMARY KEY,
    verifier VARCHAR(255) NOT NULL,
    nonce VARCHAR(255) NOT NULL,
    created_at DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS groups (
    id VARCHAR(191) PRIMARY KEY,
    entity_id VARCHAR(191) NOT NULL,
    name VARCHAR(255) NOT NULL,
    timezone VARCHAR(80) NOT NULL DEFAULT 'Europe/Madrid',
    created_by VARCHAR(191) NOT NULL,
    join_code VARCHAR(64) NOT NULL UNIQUE,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_group_entity_name (entity_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS group_members (
    id VARCHAR(191) PRIMARY KEY,
    group_id VARCHAR(191) NOT NULL,
    user_sub VARCHAR(191) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'member',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    voice_code VARCHAR(64) NULL,
    voice_label VARCHAR(128) NULL,
    section VARCHAR(128) NULL,
    joined_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    display_name VARCHAR(255) NULL,
    admin_role_id VARCHAR(191) NULL,
    musical_role_id VARCHAR(191) NULL,
    section_id VARCHAR(191) NULL,
    UNIQUE KEY uq_group_member (group_id, user_sub),
    CONSTRAINT fk_group_member_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS events (
    id VARCHAR(191) PRIMARY KEY,
    group_id VARCHAR(191) NULL,
    entity_id VARCHAR(191) NOT NULL,
    scope VARCHAR(32) NOT NULL DEFAULT 'groups',
    kind VARCHAR(32) NOT NULL,
    title VARCHAR(500) NOT NULL,
    starts_at VARCHAR(64) NOT NULL,
    ends_at VARCHAR(64) NULL,
    location VARCHAR(255) NULL,
    notes LONGTEXT NULL,
    created_by VARCHAR(191) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    cancelled_at VARCHAR(64) NULL,
    CONSTRAINT fk_events_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS event_groups (
    event_id VARCHAR(191) NOT NULL,
    group_id VARCHAR(191) NOT NULL,
    PRIMARY KEY (event_id, group_id),
    CONSTRAINT fk_event_groups_event FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    CONSTRAINT fk_event_groups_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS event_rsvps (
    event_id VARCHAR(191) NOT NULL,
    user_sub VARCHAR(191) NOT NULL,
    status VARCHAR(16) NOT NULL,
    comment LONGTEXT NULL,
    updated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (event_id, user_sub),
    CONSTRAINT fk_rsvp_event FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS entity_leads (
    id VARCHAR(191) PRIMARY KEY,
    entity_name VARCHAR(255) NOT NULL,
    entity_kind VARCHAR(64) NOT NULL,
    city VARCHAR(255) NULL,
    members INT NULL,
    contact_name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(320) NOT NULL,
    contact_phone VARCHAR(64) NULL,
    website VARCHAR(1000) NULL,
    interests LONGTEXT NOT NULL,
    message LONGTEXT NULL,
    consent TINYINT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'new',
    created_at VARCHAR(64) NOT NULL,
    manager_name VARCHAR(255) NULL,
    manager_email VARCHAR(320) NULL,
    manager_has_account TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(191) PRIMARY KEY,
    group_id VARCHAR(191) NOT NULL,
    sender_sub VARCHAR(191) NOT NULL,
    scope VARCHAR(16) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body LONGTEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_messages_group_created (group_id, created_at),
    CONSTRAINT fk_messages_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS event_targets (
    event_id VARCHAR(191) NOT NULL,
    target_type VARCHAR(16) NOT NULL,
    target_value VARCHAR(191) NOT NULL,
    PRIMARY KEY (event_id, target_type, target_value),
    CONSTRAINT fk_event_target_event FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS message_recipients (
    message_id VARCHAR(191) NOT NULL,
    user_sub VARCHAR(191) NOT NULL,
    read_at VARCHAR(64) NULL,
    PRIMARY KEY (message_id, user_sub),
    KEY idx_message_recipients_user (user_sub, read_at),
    CONSTRAINT fk_message_recipient_message FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;


