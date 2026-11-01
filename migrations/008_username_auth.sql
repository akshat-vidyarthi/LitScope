-- LitScope Migration: 008_username_auth.sql
-- Description: Replaces email-based authentication with unique username authentication.
-- Makes email optional and adds unique username column to users table.

-- 1. Add username column
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100) UNIQUE;

-- 2. Populate username from email if any existing users have NULL username
UPDATE users SET username = SPLIT_PART(email, '@', 1) WHERE username IS NULL AND email IS NOT NULL;

-- 3. Set NOT NULL on username
ALTER TABLE users ALTER COLUMN username SET NOT NULL;

-- 4. Allow email to be optional
ALTER TABLE users ALTER COLUMN email DROP NOT NULL;

-- 5. Case-insensitive lookup index
CREATE INDEX IF NOT EXISTS idx_users_username_lower ON users (LOWER(username));
