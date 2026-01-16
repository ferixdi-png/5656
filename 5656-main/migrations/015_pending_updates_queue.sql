-- Migration 015: Pending updates queue for PASSIVE mode (P0 CRITICAL FIX)
-- Purpose: Persist updates in PASSIVE mode to prevent loss during deploy overlap
-- Created: 2026-01-14 (P0: Fix update loss in PASSIVE mode)

-- Create table for pending updates queue
CREATE TABLE IF NOT EXISTS pending_updates (
    id BIGSERIAL PRIMARY KEY,
    update_id BIGINT NOT NULL,
    update_payload JSONB NOT NULL,
    update_type TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    enqueued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    processing_instance_id TEXT,
    attempts INT NOT NULL DEFAULT 0,
    last_error TEXT,
    CONSTRAINT unique_pending_update_id UNIQUE (update_id)
);

-- Index for efficient querying of unprocessed updates
CREATE INDEX IF NOT EXISTS idx_pending_updates_unprocessed 
ON pending_updates(processed_at) 
WHERE processed_at IS NULL;

-- Index for cleanup (remove old processed updates)
CREATE INDEX IF NOT EXISTS idx_pending_updates_enqueued_at 
ON pending_updates(enqueued_at);

-- Index for instance-based queries
CREATE INDEX IF NOT EXISTS idx_pending_updates_instance_id 
ON pending_updates(instance_id);

COMMENT ON TABLE pending_updates IS 'Queue for updates received in PASSIVE mode - processed when instance becomes ACTIVE';
COMMENT ON COLUMN pending_updates.update_id IS 'Telegram update_id (unique globally)';
COMMENT ON COLUMN pending_updates.update_payload IS 'Full Telegram update JSON payload';
COMMENT ON COLUMN pending_updates.update_type IS 'Type: message, callback_query, inline_query, etc.';
COMMENT ON COLUMN pending_updates.instance_id IS 'Instance ID that enqueued this update';
COMMENT ON COLUMN pending_updates.enqueued_at IS 'When update was enqueued (PASSIVE mode)';
COMMENT ON COLUMN pending_updates.processed_at IS 'When update was processed (ACTIVE mode)';
COMMENT ON COLUMN pending_updates.processing_instance_id IS 'Instance ID that processed this update';
COMMENT ON COLUMN pending_updates.attempts IS 'Number of processing attempts';
COMMENT ON COLUMN pending_updates.last_error IS 'Last error message if processing failed';

