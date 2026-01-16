-- Migration 008: Processed updates deduplication table (CRITICAL FIX)
-- Purpose: Persistent dedup of Telegram update_id to prevent duplicate processing
-- Created: 2026-01-13 (Emergency fix for worker deadlock)

-- Create table if it doesn't exist
CREATE TABLE IF NOT EXISTS processed_updates (
    update_id BIGINT PRIMARY KEY,
    processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Add missing columns if they don't exist (for existing tables)
DO $$
BEGIN
    -- Add worker_instance_id column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processed_updates' AND column_name = 'worker_instance_id'
    ) THEN
        ALTER TABLE processed_updates ADD COLUMN worker_instance_id TEXT;
        RAISE NOTICE 'Added worker_instance_id column to processed_updates';
    END IF;
    
    -- Add update_type column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'processed_updates' AND column_name = 'update_type'
    ) THEN
        ALTER TABLE processed_updates ADD COLUMN update_type TEXT;
        RAISE NOTICE 'Added update_type column to processed_updates';
    END IF;
END $$;

-- Index for cleanup (remove old updates)
CREATE INDEX IF NOT EXISTS idx_processed_updates_processed_at 
ON processed_updates(processed_at);

COMMENT ON TABLE processed_updates IS 'Deduplication: tracks processed Telegram update_id to prevent duplicate message sending';
COMMENT ON COLUMN processed_updates.update_id IS 'Telegram update_id (unique globally)';
COMMENT ON COLUMN processed_updates.processed_at IS 'When this update was first processed';
COMMENT ON COLUMN processed_updates.worker_instance_id IS 'Which instance/worker processed it';
