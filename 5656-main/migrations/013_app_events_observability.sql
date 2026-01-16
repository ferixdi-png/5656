-- Migration 013: App Events Observability
-- Purpose: Structured event logging for observability and diagnostics
-- Created: 2026-01-14

CREATE TABLE IF NOT EXISTS app_events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    level TEXT NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    event TEXT NOT NULL,
    cid TEXT,
    user_id BIGINT,
    chat_id BIGINT,
    update_id BIGINT,
    task_id BIGINT REFERENCES jobs(id) ON DELETE SET NULL,
    model TEXT,
    payload_json JSONB DEFAULT '{}'::jsonb,
    err_stack TEXT,
    tags JSONB DEFAULT '{}'::jsonb
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_app_events_ts ON app_events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_app_events_event ON app_events(event);
CREATE INDEX IF NOT EXISTS idx_app_events_user_id ON app_events(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_app_events_task_id ON app_events(task_id) WHERE task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_app_events_cid ON app_events(cid) WHERE cid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_app_events_level ON app_events(level) WHERE level IN ('ERROR', 'CRITICAL');
CREATE INDEX IF NOT EXISTS idx_app_events_model ON app_events(model) WHERE model IS NOT NULL;

-- Composite index for common queries (event + time range)
CREATE INDEX IF NOT EXISTS idx_app_events_event_ts ON app_events(event, ts DESC);

COMMENT ON TABLE app_events IS 'Structured event log for observability: telemetry, errors, job lifecycle, user actions';
COMMENT ON COLUMN app_events.cid IS 'Correlation ID for tracing event chains';
COMMENT ON COLUMN app_events.task_id IS 'FK to jobs table (if event relates to a job)';
COMMENT ON COLUMN app_events.payload_json IS 'Event-specific data (JSON)';
COMMENT ON COLUMN app_events.err_stack IS 'Error stack trace (for ERROR/CRITICAL events)';
COMMENT ON COLUMN app_events.tags IS 'Additional tags for filtering/grouping';


