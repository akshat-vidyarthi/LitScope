-- LitScope Migration: 002_add_auth_fields.sql
-- Description: Adds password hash column to users and creates audit_events table.

-- 1. Add hashed_password column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR(255);

-- 2. Audit Events Table
-- Tracks security events, role changes, project invitations, and key actions.
CREATE TABLE IF NOT EXISTS audit_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL, -- e.g. user_login, member_invited, role_changed
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_events_user ON audit_events(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_project ON audit_events(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_action ON audit_events(action);
