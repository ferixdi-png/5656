-- Migration 010: Platform-Wide Atomic Delivery Lock
-- Ensures ALL Kie.ai generation types (image/video/audio/upscale/etc.) have delivery lock columns
-- IDEMPOTENT: Safe to run multiple times

DO $$ 
BEGIN
    -- ========================================
    -- PART 1: generation_jobs table (legacy schema)
    -- ========================================
    
    -- Ensure delivered_at exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='generation_jobs' AND column_name='delivered_at'
    ) THEN
        ALTER TABLE generation_jobs ADD COLUMN delivered_at TIMESTAMPTZ;
        RAISE NOTICE '[010] Added delivered_at to generation_jobs';
    ELSE
        RAISE NOTICE '[010] delivered_at already exists in generation_jobs';
    END IF;

    -- Ensure delivering_at exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='generation_jobs' AND column_name='delivering_at'
    ) THEN
        ALTER TABLE generation_jobs ADD COLUMN delivering_at TIMESTAMPTZ;
        RAISE NOTICE '[010] Added delivering_at to generation_jobs';
    ELSE
        RAISE NOTICE '[010] delivering_at already exists in generation_jobs';
    END IF;

    -- ========================================
    -- PART 2: jobs table (V2 schema)
    -- ========================================
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'jobs') THEN
        -- Ensure delivered_at exists
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='jobs' AND column_name='delivered_at'
        ) THEN
            ALTER TABLE jobs ADD COLUMN delivered_at TIMESTAMPTZ;
            RAISE NOTICE '[010] Added delivered_at to jobs';
        ELSE
            RAISE NOTICE '[010] delivered_at already exists in jobs';
        END IF;

        -- Ensure delivering_at exists
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name='jobs' AND column_name='delivering_at'
        ) THEN
            ALTER TABLE jobs ADD COLUMN delivering_at TIMESTAMPTZ;
            RAISE NOTICE '[010] Added delivering_at to jobs';
        ELSE
            RAISE NOTICE '[010] delivering_at already exists in jobs';
        END IF;
    END IF;

    -- ========================================
    -- PART 3: Optimized indexes for atomic lock
    -- ========================================
    
    -- Index for fast task lookup
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename='generation_jobs' AND indexname='idx_generation_jobs_external_task'
    ) THEN
        CREATE INDEX idx_generation_jobs_external_task 
        ON generation_jobs(external_task_id);
        RAISE NOTICE '[010] Created idx_generation_jobs_external_task';
    ELSE
        RAISE NOTICE '[010] idx_generation_jobs_external_task already exists';
    END IF;

    -- Partial index for undelivered jobs (fastest lock queries)
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename='generation_jobs' AND indexname='idx_generation_jobs_undelivered'
    ) THEN
        CREATE INDEX idx_generation_jobs_undelivered 
        ON generation_jobs(external_task_id, delivering_at) 
        WHERE delivered_at IS NULL;
        RAISE NOTICE '[010] Created idx_generation_jobs_undelivered (partial)';
    ELSE
        RAISE NOTICE '[010] idx_generation_jobs_undelivered already exists';
    END IF;

    -- Index for stale lock sweeps
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename='generation_jobs' AND indexname='idx_generation_jobs_delivering_at'
    ) THEN
        CREATE INDEX idx_generation_jobs_delivering_at 
        ON generation_jobs(delivering_at) 
        WHERE delivering_at IS NOT NULL;
        RAISE NOTICE '[010] Created idx_generation_jobs_delivering_at (partial)';
    ELSE
        RAISE NOTICE '[010] idx_generation_jobs_delivering_at already exists';
    END IF;

    -- Same indexes for jobs table if it exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'jobs') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE tablename='jobs' AND indexname='idx_jobs_kie_task_id'
        ) THEN
            CREATE INDEX idx_jobs_kie_task_id ON jobs(kie_task_id);
            RAISE NOTICE '[010] Created idx_jobs_kie_task_id';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE tablename='jobs' AND indexname='idx_jobs_undelivered'
        ) THEN
            CREATE INDEX idx_jobs_undelivered 
            ON jobs(kie_task_id, delivering_at) 
            WHERE delivered_at IS NULL;
            RAISE NOTICE '[010] Created idx_jobs_undelivered (partial)';
        END IF;
    END IF;

    RAISE NOTICE '[010] Migration 010 completed successfully';
END $$;
