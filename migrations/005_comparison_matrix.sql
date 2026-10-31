-- Migration 005: Cross-Paper Comparison Matrix and Structured Evidence
-- Establishes structured evidence extraction tables per paper within a research project study.

CREATE TABLE IF NOT EXISTS project_matrix_evidence (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    objective TEXT,
    methodology TEXT,
    datasets TEXT,
    findings TEXT,
    limitations TEXT,
    provenance JSONB DEFAULT '{}'::jsonb NOT NULL,
    is_custom_edited BOOLEAN DEFAULT FALSE NOT NULL,
    status VARCHAR(50) DEFAULT 'completed' NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_project_paper_matrix UNIQUE (project_id, paper_id)
);

CREATE INDEX IF NOT EXISTS idx_matrix_project ON project_matrix_evidence(project_id);
CREATE INDEX IF NOT EXISTS idx_matrix_paper ON project_matrix_evidence(paper_id);
