-- Migration 005: Add Missing Columns (ADDITIVE ONLY)
-- Safe, idempotent column additions to existing tables
-- NO CREATE TABLE, NO DROP, NO indexes - only ALTER TABLE ADD COLUMN IF NOT EXISTS

-- PHASE 1: Fix users table (add missing columns from 001 → V2 schema)
DO $$
BEGIN
    -- CRITICAL: Add user_id as alias for id (001 uses 'id', V2 uses 'user_id')
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='user_id') THEN
        ALTER TABLE users ADD COLUMN user_id BIGINT;
        UPDATE users SET user_id = id WHERE user_id IS NULL;
        ALTER TABLE users ALTER COLUMN user_id SET NOT NULL;
    END IF;
    
    -- Add role column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='role') THEN
        ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
        ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('user', 'admin', 'banned'));
    END IF;
    
    -- Add locale column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='locale') THEN
        ALTER TABLE users ADD COLUMN locale TEXT DEFAULT 'ru';
    END IF;
    
    -- Add metadata column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='metadata') THEN
        ALTER TABLE users ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
    END IF;
    
    -- Add username column (might exist from 003)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='username') THEN
        ALTER TABLE users ADD COLUMN username TEXT;
    END IF;
    
    -- Add first_name column
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='first_name') THEN
        ALTER TABLE users ADD COLUMN first_name TEXT;
    END IF;
    
    RAISE NOTICE 'Migration 005: Added missing columns to users table';
END $$;

-- PHASE 2: No other table modifications
-- Migration 006 will handle new tables and indexes

-- Verification
DO $$
DECLARE
    user_id_exists BOOLEAN;
    role_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='users' AND column_name='user_id'
    ) INTO user_id_exists;
    
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='users' AND column_name='role'
    ) INTO role_exists;
    
    IF NOT user_id_exists THEN
        RAISE EXCEPTION 'Migration 005 failed: user_id column not added';
    END IF;
    
    IF NOT role_exists THEN
        RAISE EXCEPTION 'Migration 005 failed: role column not added';
    END IF;
    
    RAISE NOTICE 'Migration 005 complete: users table ready for V2 schema';
END $$;
