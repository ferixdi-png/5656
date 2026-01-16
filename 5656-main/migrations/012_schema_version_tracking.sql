/**
 * Migration 012: Schema Version Tracking
 * 
 * Purpose: Add migration_history table to track which migrations have been applied.
 * This enables smarter migration logic and prevents re-applying completed migrations.
 * 
 * Critical for:
 * - Detecting schema version at startup
 * - Preventing duplicate migration application
 * - Audit trail of schema changes
 * 
 * Applied: 2026-01-13 (post emergency hotfix)
 */

-- Create migration_history table to track applied migrations
CREATE TABLE IF NOT EXISTS migration_history (
    id BIGSERIAL PRIMARY KEY,
    migration_name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'success',  -- 'success', 'failure', 'rollback'
    error_message TEXT,
    
    CONSTRAINT migration_name_not_empty CHECK (length(migration_name) > 0),
    CONSTRAINT status_valid CHECK (status IN ('success', 'failure', 'rollback'))
);

-- Index for fast lookup during startup
CREATE INDEX IF NOT EXISTS idx_migration_history_name ON migration_history(migration_name);
CREATE INDEX IF NOT EXISTS idx_migration_history_applied_at ON migration_history(applied_at DESC);

-- Insert existing migrations (idempotent - will fail silently if already in history)
-- This assumes migrations were applied in order during Cycle 8 stabilization
INSERT INTO migration_history (migration_name, status, applied_at) VALUES
    ('001_initial_schema.sql', 'success', NOW()),
    ('002_balance_reserves.sql', 'success', NOW()),
    ('003_users_username.sql', 'success', NOW()),
    ('004_orphan_callbacks.sql', 'success', NOW()),
    ('005_add_columns.sql', 'success', NOW()),
    ('006_create_tables.sql', 'success', NOW()),
    ('007_lock_heartbeat.sql', 'success', NOW()),
    ('008_processed_updates.sql', 'success', NOW()),
    ('009_add_delivering_at.sql', 'success', NOW()),
    ('010_delivery_lock_platform_wide.sql', 'success', NOW()),
    ('011_fix_heartbeat_type.sql', 'success', NOW())
ON CONFLICT (migration_name) DO NOTHING;

-- Helper function: Check if migration was already applied
CREATE OR REPLACE FUNCTION migration_already_applied(p_migration_name TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM migration_history
        WHERE migration_name = p_migration_name AND status = 'success'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Helper function: Record migration attempt
CREATE OR REPLACE FUNCTION record_migration(
    p_migration_name TEXT,
    p_status TEXT DEFAULT 'success',
    p_error_message TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO migration_history (migration_name, status, error_message)
    VALUES (p_migration_name, p_status, p_error_message)
    ON CONFLICT (migration_name) DO UPDATE SET
        status = EXCLUDED.status,
        error_message = EXCLUDED.error_message,
        applied_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (assuming readonly_user exists)
-- These will fail silently if user doesn't exist (on fresh deploy)
DO $$
BEGIN
    GRANT SELECT ON migration_history TO readonly_user;
    GRANT EXECUTE ON FUNCTION migration_already_applied(TEXT) TO readonly_user;
EXCEPTION WHEN OTHERS THEN
    -- User may not exist yet, that's ok
    NULL;
END;
$$;
