-- Migration 029: Create group_roles table for group-specific admin/musical roles from amigos_group_catalog
CREATE TABLE IF NOT EXISTS group_roles (
    id VARCHAR(191) NOT NULL PRIMARY KEY,
    legacy_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Original ID from amigos_group_catalog',
    group_id VARCHAR(191) NOT NULL,
    scope VARCHAR(16) NOT NULL COMMENT 'admin or musical',
    code VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    parent_id VARCHAR(191) NULL COMMENT 'Self-reference for hierarchy',
    sort_order INT NOT NULL DEFAULT 0,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_group_roles_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    CONSTRAINT fk_group_roles_parent FOREIGN KEY (parent_id) REFERENCES group_roles(id) ON DELETE SET NULL,
    UNIQUE KEY uq_group_roles_group_scope_code (group_id, scope, code),
    KEY idx_group_roles_group (group_id),
    KEY idx_group_roles_scope (scope)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;