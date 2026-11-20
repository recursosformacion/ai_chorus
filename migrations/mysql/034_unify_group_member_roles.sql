-- Migration 034: Add FKs from group_members to group_roles on existing columns
-- The existing columns admin_role_id and musical_role_id (from 001_schema.sql)
-- should reference group_roles(id). Migration 033 created duplicate columns
-- group_admin_role_id and group_musical_role_id which are not used by the API.

SET FOREIGN_KEY_CHECKS = 0;

-- Add FKs to existing columns
ALTER TABLE group_members ADD CONSTRAINT fk_group_members_admin_role FOREIGN KEY (admin_role_id) REFERENCES group_roles(id) ON DELETE SET NULL;
ALTER TABLE group_members ADD CONSTRAINT fk_group_members_musical_role FOREIGN KEY (musical_role_id) REFERENCES group_roles(id) ON DELETE SET NULL;

-- Add indexes for FK columns
ALTER TABLE group_members ADD INDEX idx_group_members_admin_role (admin_role_id);
ALTER TABLE group_members ADD INDEX idx_group_members_musical_role (musical_role_id);

-- Drop duplicate columns from migration 033 if they exist (drop FKs first)
ALTER TABLE group_members DROP FOREIGN KEY IF EXISTS fk_group_members_group_admin_role;
ALTER TABLE group_members DROP FOREIGN KEY IF EXISTS fk_group_members_group_musical_role;
ALTER TABLE group_members DROP INDEX IF EXISTS idx_group_members_group_admin_role;
ALTER TABLE group_members DROP INDEX IF EXISTS idx_group_members_group_musical_role;
ALTER TABLE group_members DROP COLUMN IF EXISTS group_admin_role_id;
ALTER TABLE group_members DROP COLUMN IF EXISTS group_musical_role_id;

SET FOREIGN_KEY_CHECKS = 1;