-- Migration 006: Create New Tables and Indexes
-- Creates jobs, wallets, ledger, ui_state and other V2 tables
-- Migrates data from generation_jobs if exists

-- PHASE 1: Create wallets table
CREATE TABLE IF NOT EXISTS wallets (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    balance_rub NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (balance_rub >= 0),
    hold_rub NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (hold_rub >= 0),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT balance_plus_hold_positive CHECK (balance_rub + hold_rub >= 0)
);

CREATE INDEX IF NOT EXISTS idx_wallets_updated ON wallets(updated_at);

-- PHASE 2: Create jobs table (or migrate from generation_jobs)
DO $$
BEGIN
    -- Create jobs table if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'jobs') THEN
        CREATE TABLE jobs (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            model_id TEXT NOT NULL,
            category TEXT NOT NULL,
            input_json JSONB NOT NULL,
            price_rub NUMERIC(12, 2) NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                'draft', 'await_confirm', 'queued', 'running',
                'done', 'failed', 'canceled'
            )),
            kie_task_id TEXT,
            kie_status TEXT,
            result_json JSONB,
            error_text TEXT,
            idempotency_key TEXT NOT NULL,
            chat_id BIGINT,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMP
        );
        
        RAISE NOTICE 'Created jobs table';
        
        -- Migrate from generation_jobs if exists
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'generation_jobs') THEN
            INSERT INTO jobs (
                user_id, model_id, category, input_json, price_rub,
                status, kie_task_id, result_json, error_text,
                idempotency_key, created_at, updated_at
            )
            SELECT
                user_id,
                model_id,
                COALESCE(
                    (params->>'category')::TEXT,
                    CASE 
                        WHEN model_id LIKE '%video%' THEN 'video'
                        WHEN model_id LIKE '%image%' THEN 'image'
                        WHEN model_id LIKE '%audio%' THEN 'audio'
                        ELSE 'other'
                    END
                ) as category,
                params as input_json,
                price as price_rub,
                CASE status
                    WHEN 'queued' THEN 'queued'
                    WHEN 'running' THEN 'running'
                    WHEN 'done' THEN 'done'
                    WHEN 'failed' THEN 'failed'
                    WHEN 'canceled' THEN 'canceled'
                    ELSE 'draft'
                END as status,
                external_task_id as kie_task_id,
                result_urls::jsonb as result_json,
                error_message as error_text,
                CONCAT('migrated:', job_id) as idempotency_key,
                created_at,
                updated_at
            FROM generation_jobs
            WHERE NOT EXISTS (
                SELECT 1 FROM jobs WHERE jobs.idempotency_key = CONCAT('migrated:', generation_jobs.job_id)
            );
            
            RAISE NOTICE 'Migrated data from generation_jobs to jobs';
            
            -- Drop old table
            DROP TABLE generation_jobs CASCADE;
            RAISE NOTICE 'Dropped generation_jobs table';
        END IF;
    END IF;
    
    -- CRITICAL: Ensure all columns exist in jobs table (for tables created by old migrations)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'jobs') THEN
        -- Add missing columns if they don't exist
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='chat_id') THEN
            ALTER TABLE jobs ADD COLUMN chat_id BIGINT;
            RAISE NOTICE 'Added chat_id column to existing jobs table';
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='delivered_at') THEN
            ALTER TABLE jobs ADD COLUMN delivered_at TIMESTAMP;
            RAISE NOTICE 'Added delivered_at column to existing jobs table';
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='kie_status') THEN
            ALTER TABLE jobs ADD COLUMN kie_status TEXT;
            RAISE NOTICE 'Added kie_status column to existing jobs table';
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name='finished_at') THEN
            ALTER TABLE jobs ADD COLUMN finished_at TIMESTAMP;
            RAISE NOTICE 'Added finished_at column to existing jobs table';
        END IF;
    END IF;
END $$;

-- PHASE 3: Create indexes on jobs (AFTER ensuring all columns exist)
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_kie_task ON jobs(kie_task_id);
CREATE INDEX IF NOT EXISTS idx_jobs_chat_id ON jobs(chat_id);

-- PHASE 4: Create ledger table
CREATE TABLE IF NOT EXISTS ledger (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('topup', 'charge', 'refund', 'hold', 'release', 'adjust')),
    amount_rub NUMERIC(12, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'done' CHECK (status IN ('pending', 'done', 'failed', 'cancelled')),
    ref TEXT,
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ledger_user ON ledger(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_ref ON ledger(ref) WHERE ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ledger_status ON ledger(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_idempotency ON ledger(ref) WHERE ref IS NOT NULL AND status = 'done';

-- PHASE 5: Create ui_state table
CREATE TABLE IF NOT EXISTS ui_state (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    data JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ui_state_expires ON ui_state(expires_at);

-- PHASE 6: Create users indexes (safe after user_id exists)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- PHASE 7: Admin actions log
CREATE TABLE IF NOT EXISTS admin_actions (
    id BIGSERIAL PRIMARY KEY,
    admin_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    action_type TEXT NOT NULL CHECK (action_type IN (
        'model_enable', 'model_disable', 'model_price', 'model_free', 
        'user_topup', 'user_charge', 'user_ban', 'user_unban',
        'config_change', 'other'
    )),
    target_type TEXT NOT NULL CHECK (target_type IN ('model', 'user', 'config', 'system')),
    target_id TEXT,
    old_value JSONB,
    new_value JSONB,
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_actions_admin ON admin_actions(admin_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_actions_type ON admin_actions(action_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_actions_target ON admin_actions(target_type, target_id);

-- PHASE 8: Free models config
CREATE TABLE IF NOT EXISTS free_models (
    model_id TEXT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    daily_limit INT NOT NULL DEFAULT 5,
    hourly_limit INT DEFAULT 2,
    meta JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_free_models_enabled ON free_models(enabled);

-- PHASE 9: Free usage tracking
CREATE TABLE IF NOT EXISTS free_usage (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    job_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_free_usage_user_model ON free_usage(user_id, model_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_free_usage_created ON free_usage(created_at);

-- Verification
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_name IN ('users', 'wallets', 'jobs', 'ledger', 'ui_state', 'orphan_callbacks');
    
    IF table_count < 6 THEN
        RAISE EXCEPTION 'Migration 006 failed: expected 6 core tables, found %', table_count;
    END IF;
    
    RAISE NOTICE 'Migration 006 complete: Created % core tables with indexes', table_count;
END $$;
