-- Migration 032: Create activity_log table for amigos_events (operational audit, not agenda)
-- Distinct from: events (agenda), group_history (membership), group_articles (content)
CREATE TABLE IF NOT EXISTS activity_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    legacy_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Original ID from amigos_events',
    group_id VARCHAR(191) NULL COMMENT 'Empty string or NULL in source becomes NULL',
    article_id VARCHAR(191) NULL,
    event_type VARCHAR(64) NOT NULL,
    actor VARCHAR(191) NOT NULL COMMENT 'User UUID from osap-auth',
    from_status VARCHAR(64) NULL,
    to_status VARCHAR(64) NULL,
    detail_json JSON NULL,
    created_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_activity_log_group FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL,
    CONSTRAINT fk_activity_log_article FOREIGN KEY (article_id) REFERENCES group_articles(id) ON DELETE SET NULL,
    KEY idx_activity_log_group (group_id),
    KEY idx_activity_log_actor (actor),
    KEY idx_activity_log_event_type (event_type),
    KEY idx_activity_log_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;