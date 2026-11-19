-- Chorus 0.15: índice faltante para series de eventos recurrentes.
-- Las columnas ya existen en 001_schema.sql (equivalente a SQLite 014), solo falta el índice.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Índice para consultas eficientes de eventos por serie
CREATE INDEX idx_events_series ON events (series_id, starts_at);

SET FOREIGN_KEY_CHECKS = 1;