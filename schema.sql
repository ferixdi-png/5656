-- Оптимизированная схема БД для баланса и операций
-- Разработана для эффективного использования 1 ГБ пространства

-- Таблица пользователей с балансом
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    balance NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индекс для быстрого поиска по ID
CREATE INDEX IF NOT EXISTS idx_users_id ON users(id);

-- Таблица операций (тонкие записи)
CREATE TABLE IF NOT EXISTS operations (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,  -- 'payment', 'generation', 'refund', etc.
    amount NUMERIC(12, 2) NOT NULL,
    model TEXT,  -- Название модели (если применимо)
    result_url TEXT,  -- URL результата (не сам файл!)
    prompt TEXT,  -- Обрезанный промпт (до 1000 символов)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индексы для быстрого поиска операций
CREATE INDEX IF NOT EXISTS idx_operations_user_id ON operations(user_id);
CREATE INDEX IF NOT EXISTS idx_operations_created_at ON operations(created_at);
CREATE INDEX IF NOT EXISTS idx_operations_type ON operations(type);

-- Таблица для логов KIE (с автоматической очисткой)
CREATE TABLE IF NOT EXISTS kie_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    model TEXT,
    prompt TEXT,  -- Обрезанный до 1000 символов
    result_url TEXT,
    error_message TEXT,  -- Обрезанный до 500 символов
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индекс для очистки старых логов
CREATE INDEX IF NOT EXISTS idx_kie_logs_created_at ON kie_logs(created_at);

-- Таблица для debug логов (временная, будет очищаться)
CREATE TABLE IF NOT EXISTS debug_logs (
    id BIGSERIAL PRIMARY KEY,
    level TEXT NOT NULL,
    message TEXT,  -- Обрезанный до 1000 символов
    context JSONB,  -- Легковесный JSON
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индекс для очистки старых debug логов
CREATE INDEX IF NOT EXISTS idx_debug_logs_created_at ON debug_logs(created_at);

-- Функция для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер для автоматического обновления updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Функция для очистки старых логов (вызывается через cron)
CREATE OR REPLACE FUNCTION cleanup_old_logs(days_to_keep INTEGER DEFAULT 30)
RETURNS TABLE(deleted_kie_logs BIGINT, deleted_debug_logs BIGINT) AS $$
DECLARE
    kie_count BIGINT;
    debug_count BIGINT;
BEGIN
    -- Удаляем старые KIE логи
    DELETE FROM kie_logs WHERE created_at < NOW() - (days_to_keep || ' days')::INTERVAL;
    GET DIAGNOSTICS kie_count = ROW_COUNT;
    
    -- Удаляем старые debug логи
    DELETE FROM debug_logs WHERE created_at < NOW() - (days_to_keep || ' days')::INTERVAL;
    GET DIAGNOSTICS debug_count = ROW_COUNT;
    
    RETURN QUERY SELECT kie_count, debug_count;
END;
$$ LANGUAGE plpgsql;


