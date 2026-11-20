-- Fix: Make group_id nullable in group_articles for public scope articles
-- This allows articles with scope='public' (general) to have NULL group_id

ALTER TABLE group_articles MODIFY COLUMN group_id VARCHAR(191) NULL;