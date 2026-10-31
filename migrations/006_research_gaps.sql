-- Migration 006: Evidence-Based Candidate Research-Gap Analysis
-- Stores structured candidate research gaps discovered across curated papers within a project.

CREATE TABLE IF NOT EXISTS project_research_gaps (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    paper_id INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    gap_title VARCHAR(500) NOT NULL,
    gap_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    confidence_status VARCHAR(100) DEFAULT 'supported_within_collection' NOT NULL,
    supporting_evidence JSONB DEFAULT '[]'::jsonb NOT NULL,
    counterevidence JSONB DEFAULT '[]'::jsonb NOT NULL,
    review_status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    researcher_notes TEXT,
    refined_question TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_gaps_project ON project_research_gaps(project_id);
CREATE INDEX IF NOT EXISTS idx_research_gaps_paper ON project_research_gaps(paper_id);
CREATE INDEX IF NOT EXISTS idx_research_gaps_type ON project_research_gaps(gap_type);
CREATE INDEX IF NOT EXISTS idx_research_gaps_status ON project_research_gaps(review_status);
