-- Chorus 0.13: agenda recurrente, series y autoría.
PRAGMA foreign_keys = ON;

ALTER TABLE events ADD COLUMN recurrence TEXT NOT NULL DEFAULT 'none';
ALTER TABLE events ADD COLUMN recurrence_until TEXT;
ALTER TABLE events ADD COLUMN series_id TEXT;
ALTER TABLE events ADD COLUMN creator_badge TEXT;
CREATE INDEX idx_events_series ON events (series_id, starts_at);
