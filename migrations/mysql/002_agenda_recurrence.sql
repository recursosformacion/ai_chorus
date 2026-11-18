-- Chorus 0.13: agenda recurrente, series y autoría.
ALTER TABLE events
    ADD COLUMN recurrence VARCHAR(16) NOT NULL DEFAULT 'none',
    ADD COLUMN recurrence_until VARCHAR(64) NULL,
    ADD COLUMN series_id VARCHAR(191) NULL,
    ADD COLUMN creator_badge VARCHAR(8) NULL;

CREATE INDEX idx_events_series ON events (series_id, starts_at);
