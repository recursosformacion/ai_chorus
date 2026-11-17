ALTER TABLE resources ADD COLUMN group_id TEXT;
ALTER TABLE resources ADD COLUMN group_section_id TEXT;
CREATE INDEX IF NOT EXISTS idx_resources_group_status ON resources(group_id, material_status);
