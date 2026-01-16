-- HOTFIX: Re-create update_lock_heartbeat with explicit type cast
-- Fixes production issue: "function update_lock_heartbeat(bigint, unknown) does not exist"
-- 
-- Root cause: psycopg2 passes Python strings as "unknown" type to PostgreSQL,
-- requiring explicit ::TEXT cast for function signature matching.

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

-- Verify function exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc 
        WHERE proname = 'update_lock_heartbeat'
    ) THEN
        RAISE EXCEPTION 'update_lock_heartbeat function creation failed';
    END IF;
END $$;
