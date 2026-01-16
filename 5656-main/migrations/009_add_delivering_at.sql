-- Migration: Add delivering_at for atomic delivery lock
-- Prevents race conditions between callback + polling and ACTIVE + PASSIVE instances

DO $$ 
BEGIN
    -- Add delivered_at column if not exists (CRITICAL: needed for atomic lock)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='generation_jobs' AND column_name='delivered_at'
    ) THEN
        ALTER TABLE generation_jobs ADD COLUMN delivered_at TIMESTAMP;
        RAISE NOTICE 'Added delivered_at column to generation_jobs table';
    END IF;

    -- Add delivering_at column if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='generation_jobs' AND column_name='delivering_at'
    ) THEN
        ALTER TABLE generation_jobs ADD COLUMN delivering_at TIMESTAMP;
        RAISE NOTICE 'Added delivering_at column to generation_jobs table';
    END IF;

    -- Add delivering_at to jobs table (new schema)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'jobs') THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='jobs' AND column_name='delivered_at'
        ) THEN
            ALTER TABLE jobs ADD COLUMN delivered_at TIMESTAMP;
            RAISE NOTICE 'Added delivered_at column to jobs table';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='jobs' AND column_name='delivering_at'
        ) THEN
            ALTER TABLE jobs ADD COLUMN delivering_at TIMESTAMP;
            RAISE NOTICE 'Added delivering_at column to jobs table';
        END IF;
    END IF;

    -- Create index for fast delivery lock queries
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename='generation_jobs' AND indexname='idx_jobs_delivery_lock'
    ) THEN
        CREATE INDEX idx_jobs_delivery_lock ON generation_jobs(external_task_id, delivered_at, delivering_at) 
        WHERE delivered_at IS NULL;
        RAISE NOTICE 'Created idx_jobs_delivery_lock index';
    END IF;
END $$;
