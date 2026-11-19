-- Chorus 0.15: campos específicos de agrupaciones corales.
-- Migración 016: 12 campos adicionales en la tabla groups.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

ALTER TABLE groups
    ADD COLUMN foundation_date DATE NULL,
    ADD COLUMN dissolution_date DATE NULL,
    ADD COLUMN locality VARCHAR(160) NULL,
    ADD COLUMN region VARCHAR(160) NULL,
    ADD COLUMN country_code CHAR(2) NULL,
    ADD COLUMN venue VARCHAR(255) NULL,
    ADD COLUMN formation_type VARCHAR(48) NULL,
    ADD COLUMN member_count INT NULL,
    ADD COLUMN public_email VARCHAR(254) NULL,
    ADD COLUMN language JSON NULL,
    ADD COLUMN repertoire JSON NULL,
    ADD COLUMN venues JSON NULL;

SET FOREIGN_KEY_CHECKS = 1;