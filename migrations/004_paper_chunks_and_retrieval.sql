-- Migration 004: Paper Chunks, Vector Storage, and Full-Text Retrieval
-- Establishes semantic chunk storage and query history for grounded RAG.

-- 1. Paper Chunks Table
CREATE TABLE IF NOT EXISTS paper_chunks (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    paper_version_id INTEGER NOT NULL REFERENCES paper_versions(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    character_start INTEGER NOT NULL DEFAULT 0,
    character_end INTEGER NOT NULL DEFAULT 0,
    content_hash VARCHAR(64) NOT NULL,
    embedding JSONB, -- Stores the 384-dimensional dense semantic vector
    tsv_content tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_paper_chunks_version_idx UNIQUE (paper_version_id, chunk_index)
);

-- Performance indexes for project joins, page lookups, and keyword FTS
CREATE INDEX IF NOT EXISTS idx_paper_chunks_paper_id ON paper_chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_chunks_version_id ON paper_chunks(paper_version_id);
CREATE INDEX IF NOT EXISTS idx_paper_chunks_page ON paper_chunks(paper_id, page_number);
CREATE INDEX IF NOT EXISTS idx_paper_chunks_tsv ON paper_chunks USING GIN(tsv_content);

-- 2. Project Research Queries Table (History of Questions, Answers, and Evidence)
CREATE TABLE IF NOT EXISTS project_queries (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    retrieved_chunks JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_project_queries_project ON project_queries(project_id);
