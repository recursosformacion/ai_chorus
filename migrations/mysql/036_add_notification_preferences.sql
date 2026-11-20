-- Migration: Add notification preferences to group_members
-- Allows users to configure their notification channels per group

ALTER TABLE group_members
    ADD COLUMN notify_email BOOLEAN NOT NULL DEFAULT TRUE AFTER granted_by,
    ADD COLUMN notify_osap BOOLEAN NOT NULL DEFAULT TRUE AFTER notify_email,
    ADD COLUMN notify_whatsapp BOOLEAN NOT NULL DEFAULT FALSE AFTER notify_osap,
    ADD COLUMN notify_sms BOOLEAN NOT NULL DEFAULT FALSE AFTER notify_whatsapp;

-- Add index for notification queries
ALTER TABLE group_members ADD INDEX idx_group_members_notifications (notify_email, notify_osap, notify_whatsapp, notify_sms);