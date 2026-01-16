-- Migration 014: Add composite index on jobs(status, updated_at) for stale job cleanup
-- This index optimizes queries like: SELECT * FROM jobs WHERE status = 'running' AND updated_at < NOW() - INTERVAL '30 minutes'

DO $$
BEGIN
    -- Check if index already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'jobs' AND indexname = 'idx_jobs_status_updated_at'
    ) THEN
        CREATE INDEX idx_jobs_status_updated_at ON jobs(status, updated_at DESC);
        RAISE NOTICE '[014] Created idx_jobs_status_updated_at for stale job cleanup optimization';
    ELSE
        RAISE NOTICE '[014] idx_jobs_status_updated_at already exists';
    END IF;
END $$;

