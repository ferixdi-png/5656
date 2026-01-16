-- Migration 003: Add username and telegram metadata to users table
-- Fixes: "column username does not exist" error

-- Add username column (nullable for backward compatibility)
ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;

-- Add first_name and last_name for full user info
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT;

-- Add index on username for lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Update updated_at trigger (if not exists)
-- This ensures updated_at is automatically maintained
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
