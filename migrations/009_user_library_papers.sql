-- LitScope Migration: 009_user_library_papers.sql
-- Description: Creates user_library_papers table for per-user master libraries.
-- Maintains canonical paper deduplication while ensuring account-level separability.

CREATE TABLE IF NOT EXISTS user_library_papers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_user_paper UNIQUE (user_id, paper_id)
);

CREATE INDEX IF NOT EXISTS idx_user_library_user ON user_library_papers(user_id);
CREATE INDEX IF NOT EXISTS idx_user_library_paper ON user_library_papers(paper_id);

-- Backfill from audit_events and project_papers for existing data if any
INSERT INTO user_library_papers (user_id, paper_id, added_at)
SELECT DISTINCT 
    ae.user_id, 
    (ae.details->>'paper_id')::int AS paper_id,
    ae.created_at
FROM audit_events ae
WHERE ae.action = 'paper_uploaded' 
  AND ae.user_id IS NOT NULL 
  AND ae.details->>'paper_id' IS NOT NULL
ON CONFLICT (user_id, paper_id) DO NOTHING;

INSERT INTO user_library_papers (user_id, paper_id)
SELECT DISTINCT 
    pm.user_id,
    pp.paper_id
FROM project_papers pp
JOIN project_members pm ON pp.project_id = pm.project_id
ON CONFLICT (user_id, paper_id) DO NOTHING;
