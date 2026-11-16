-- Chorus 0.9: comunicados internos (tablón y mensajes directos).
PRAGMA foreign_keys = ON;

ALTER TABLE group_members ADD COLUMN display_name TEXT;

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    sender_sub TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('group', 'managers', 'users')),
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_messages_group_created ON messages (group_id, created_at DESC);

CREATE TABLE message_recipients (
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_sub TEXT NOT NULL,
    read_at TEXT,
    PRIMARY KEY (message_id, user_sub)
);
CREATE INDEX idx_message_recipients_user ON message_recipients (user_sub, read_at);
