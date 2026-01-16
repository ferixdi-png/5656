-- Add lock heartbeat tracking for stale lock detection
-- This allows detecting and releasing locks from dead instances

CREATE TABLE IF NOT EXISTS lock_heartbeat (
    lock_key BIGINT PRIMARY KEY,
    instance_id TEXT NOT NULL,
    last_heartbeat TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    acquired_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for fast lookup by heartbeat time
CREATE INDEX IF NOT EXISTS idx_lock_heartbeat_last_heartbeat 
ON lock_heartbeat(last_heartbeat);

-- Function to update heartbeat (FIXED: explicit type cast for psycopg2 compatibility)
CREATE OR REPLACE FUNCTION update_lock_heartbeat(
    p_lock_key BIGINT,
    p_instance_id TEXT
) RETURNS VOID AS $$
BEGIN
    INSERT INTO lock_heartbeat (lock_key, instance_id, last_heartbeat, acquired_at)
    VALUES (p_lock_key, p_instance_id::TEXT, NOW(), NOW())
    ON CONFLICT (lock_key) DO UPDATE
    SET last_heartbeat = NOW(),
        instance_id = EXCLUDED.instance_id;
END;
$$ LANGUAGE plpgsql;

-- Function to check if lock is stale (>5 minutes without heartbeat)
CREATE OR REPLACE FUNCTION is_lock_stale(
    p_lock_key BIGINT,
    p_stale_threshold_seconds INTEGER DEFAULT 300
) RETURNS BOOLEAN AS $$
DECLARE
    v_last_heartbeat TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT last_heartbeat INTO v_last_heartbeat
    FROM lock_heartbeat
    WHERE lock_key = p_lock_key;
    
    IF v_last_heartbeat IS NULL THEN
        RETURN TRUE; -- No heartbeat record = stale
    END IF;
    
    RETURN (NOW() - v_last_heartbeat) > (p_stale_threshold_seconds || ' seconds')::INTERVAL;
END;
$$ LANGUAGE plpgsql;
