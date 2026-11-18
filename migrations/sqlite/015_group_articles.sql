-- Chorus 0.14: grupos nativos y artículos de grupo.
ALTER TABLE groups ADD COLUMN slug VARCHAR(191);
ALTER TABLE groups ADD COLUMN kind VARCHAR(32) NOT NULL DEFAULT 'grupo';
ALTER TABLE groups ADD COLUMN description TEXT;
ALTER TABLE groups ADD COLUMN image_url VARCHAR(1024);
ALTER TABLE groups ADD COLUMN website VARCHAR(1024);
ALTER TABLE groups ADD COLUMN email VARCHAR(254);
ALTER TABLE groups ADD COLUMN logo_url VARCHAR(1024);
ALTER TABLE groups ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'active';
ALTER TABLE groups ADD COLUMN editorial_mode VARCHAR(16) NOT NULL DEFAULT 'moderated';
ALTER TABLE groups ADD COLUMN technical_description TEXT;

CREATE TABLE IF NOT EXISTS group_sections (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT 'section',
  parent_id TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(group_id, code, scope)
);

CREATE TABLE IF NOT EXISTS group_articles (
  id TEXT PRIMARY KEY,
  legacy_id TEXT UNIQUE,
  group_id TEXT NOT NULL,
  title TEXT NOT NULL,
  slug TEXT NOT NULL,
  summary TEXT,
  body TEXT,
  cover_url TEXT,
  event_date TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  author_user_id TEXT NOT NULL,
  publisher_user_id TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT,
  review_note TEXT,
  published_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(group_id, slug)
);
CREATE INDEX IF NOT EXISTS idx_group_articles_group ON group_articles(group_id, event_date);
CREATE INDEX IF NOT EXISTS idx_group_articles_status ON group_articles(status, published_at);

CREATE TABLE IF NOT EXISTS group_article_media (
  id TEXT PRIMARY KEY,
  legacy_id TEXT UNIQUE,
  article_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  url TEXT NOT NULL,
  provider TEXT,
  video_id TEXT,
  caption TEXT,
  credit TEXT,
  position INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_group_article_media_article ON group_article_media(article_id, position);
