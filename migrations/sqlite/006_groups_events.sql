-- Chorus 0.4: grupos, agenda y RSVP binario (Asisto / No asisto).
PRAGMA foreign_keys = ON;

CREATE TABLE groups (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',
    created_by TEXT NOT NULL,
    join_code TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (entity_id, name)
);

CREATE TABLE group_members (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_sub TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('manager', 'member')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'removed')),
    voice_code TEXT,
    voice_label TEXT,
    section TEXT,
    joined_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (group_id, user_sub)
);
CREATE INDEX idx_group_members_user ON group_members (user_sub, status);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    group_id TEXT REFERENCES groups(id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'groups' CHECK (scope IN ('groups', 'global')),
    kind TEXT NOT NULL CHECK (kind IN ('rehearsal', 'concert', 'note')),
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    location TEXT,
    notes TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    cancelled_at TEXT
);
CREATE INDEX idx_events_group_start ON events (group_id, starts_at);
CREATE INDEX idx_events_entity_start ON events (entity_id, starts_at);

CREATE TABLE event_groups (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    group_id TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, group_id)
);

CREATE TABLE event_rsvps (
    event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_sub TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('yes', 'no')),
    comment TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (event_id, user_sub)
);

