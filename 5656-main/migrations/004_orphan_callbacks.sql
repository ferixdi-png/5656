-- Migration 004: Orphan callbacks table
-- Handles callbacks that arrive before job record is created (race condition)

CREATE TABLE IF NOT EXISTS orphan_callbacks (
    task_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_orphan_callbacks_processed ON orphan_callbacks(processed);
CREATE INDEX IF NOT EXISTS idx_orphan_callbacks_received_at ON orphan_callbacks(received_at);

-- Cleanup old processed orphans (keep for 7 days for debugging)
CREATE INDEX IF NOT EXISTS idx_orphan_callbacks_cleanup ON orphan_callbacks(processed, received_at);
