-- Migration 033: Add group-specific role references to group_members
-- These reference group_roles (group-specific catalog), not role_templates (global templates)
ALTER TABLE group_members
    ADD COLUMN group_admin_role_id VARCHAR(191) NULL AFTER section_id,
    ADD COLUMN group_musical_role_id VARCHAR(191) NULL AFTER group_admin_role_id,
    ADD CONSTRAINT fk_group_members_group_admin_role FOREIGN KEY (group_admin_role_id) REFERENCES group_roles(id) ON DELETE SET NULL,
    ADD CONSTRAINT fk_group_members_group_musical_role FOREIGN KEY (group_musical_role_id) REFERENCES group_roles(id) ON DELETE SET NULL,
    ADD KEY idx_group_members_group_admin_role (group_admin_role_id),
    ADD KEY idx_group_members_group_musical_role (group_musical_role_id);