-- Migration: Add balance reserves table for idempotency and rollback support
-- Supports: idempotency keys, reserve/commit/release operations

-- Удаляем старую таблицу если существует
DROP TABLE IF EXISTS balance_reserves CASCADE;

-- Таблица резервов баланса для генераций
CREATE TABLE balance_reserves (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    idempotency_key TEXT UNIQUE,  -- Ключ идемпотентности (task_id + user_id + model_id)
    status TEXT NOT NULL DEFAULT 'reserved',  -- 'reserved', 'committed', 'released'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(task_id, user_id, model_id)  -- Один резерв на задачу
);

CREATE INDEX idx_balance_reserves_user_id ON balance_reserves(user_id);
CREATE INDEX idx_balance_reserves_task_id ON balance_reserves(task_id);
CREATE INDEX idx_balance_reserves_idempotency_key ON balance_reserves(idempotency_key);
CREATE INDEX idx_balance_reserves_status ON balance_reserves(status);

-- Триггер для обновления updated_at
DROP TRIGGER IF EXISTS update_balance_reserves_updated_at ON balance_reserves;
CREATE TRIGGER update_balance_reserves_updated_at BEFORE UPDATE ON balance_reserves
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Добавляем idempotency_key к payments если ещё нет
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'payments' AND column_name = 'idempotency_key'
    ) THEN
        ALTER TABLE payments ADD COLUMN idempotency_key TEXT UNIQUE;
        CREATE INDEX idx_payments_idempotency_key ON payments(idempotency_key);
    END IF;
END $$;

