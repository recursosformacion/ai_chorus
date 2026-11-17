ALTER TABLE resources ADD COLUMN version_label TEXT;
ALTER TABLE resources ADD COLUMN part_label TEXT;
ALTER TABLE resources ADD COLUMN material_status TEXT NOT NULL DEFAULT 'draft';
ALTER TABLE files ADD COLUMN folder_path TEXT;
ALTER TABLE files ADD COLUMN display_name TEXT;
ALTER TABLE files ADD COLUMN original_name TEXT;
CREATE INDEX IF NOT EXISTS idx_resources_material ON resources(work_id, material_status);
