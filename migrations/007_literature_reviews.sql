-- Migration 007: Literature Review Table
-- Stores continuous literature review drafts with target/actual word counts and reference metadata

CREATE TABLE IF NOT EXISTS project_literature_reviews (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    target_word_count INTEGER NOT NULL DEFAULT 350,
    actual_word_count INTEGER NOT NULL DEFAULT 0,
    review_text TEXT NOT NULL,
    paper_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_project_lit_reviews_project ON project_literature_reviews(project_id, created_at DESC);
