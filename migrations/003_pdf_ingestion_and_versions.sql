-- Migration 003: PDF Ingestion and Versions
-- Establishes paper versions with SHA-256 checksums and page-by-page text extraction storage.

-- Paper versions track binary PDF files associated with a canonical paper record
CREATE TABLE IF NOT EXISTS paper_versions (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    file_path VARCHAR(1024) NOT NULL,
    file_checksum VARCHAR(64) UNIQUE NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    extraction_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Extracted text per page with character counts for provenance and reading
CREATE TABLE IF NOT EXISTS paper_pages (
    id SERIAL PRIMARY KEY,
    paper_version_id INTEGER NOT NULL REFERENCES paper_versions(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    character_count INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_paper_pages_version_page UNIQUE (paper_version_id, page_number)
);

-- Performance indexes for lookup and joins
CREATE INDEX IF NOT EXISTS idx_paper_versions_paper_id ON paper_versions(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_versions_checksum ON paper_versions(file_checksum);
CREATE INDEX IF NOT EXISTS idx_paper_pages_version_id ON paper_pages(paper_version_id);
CREATE INDEX IF NOT EXISTS idx_paper_pages_version_page ON paper_pages(paper_version_id, page_number);
