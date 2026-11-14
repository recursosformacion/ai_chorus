-- Chorus 0.5: solicitudes públicas de alta de entidades (corales, bandas, grupos…).
CREATE TABLE entity_leads (
    id TEXT PRIMARY KEY,
    entity_name TEXT NOT NULL,
    entity_kind TEXT NOT NULL,
    city TEXT,
    members INTEGER,
    contact_name TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    contact_phone TEXT,
    website TEXT,
    interests TEXT NOT NULL DEFAULT '[]',
    message TEXT,
    consent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE INDEX idx_entity_leads_status ON entity_leads (status, created_at);
