-- Chorus 0.7: el formulario de alta identifica al gestor de la entidad.
ALTER TABLE entity_leads ADD COLUMN manager_name TEXT;
ALTER TABLE entity_leads ADD COLUMN manager_email TEXT;
ALTER TABLE entity_leads ADD COLUMN manager_has_account INTEGER NOT NULL DEFAULT 0;
