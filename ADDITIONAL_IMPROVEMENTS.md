# Дополнительные улучшения системы

## ✅ РЕАЛИЗОВАНО

### 1. ✅ Система метрик и мониторинга (`bot_kie_services/metrics.py`)

**Возможности:**
- Сбор метрик (запросы, генерации, ошибки, доходы)
- Измерение времени выполнения операций
- Хранение истории ошибок
- Статистика по компонентам

**Использование:**
```python
from bot_kie_services import metrics_service

# Увеличить метрику
metrics_service.increment('total_generations')

# Записать время выполнения
metrics_service.record_time('generation_duration', 2.5)

# Записать ошибку
metrics_service.record_error('APIError', 'Connection timeout', user_id=123)

# Получить статистику
stats = metrics_service.get_stats()
```

### 2. ✅ Rate Limiting (`bot_kie_services/rate_limiter.py`)

**Возможности:**
- Ограничение частоты запросов по пользователям
- Разные лимиты для разных типов операций
- Защита от злоупотреблений

**Использование:**
```python
from bot_kie_services import rate_limit_service

# Проверить лимит на генерацию
is_allowed, remaining = rate_limit_service.check_generation(user_id)
if not is_allowed:
    await update.message.reply_text(f"Лимит превышен. Попробуйте через минуту. Осталось: {remaining}")
```

**Лимиты:**
- Генерации: 5 в минуту
- API запросы: 30 в минуту
- Сообщения: 20 в минуту

### 3. ✅ Retry механизм (`bot_kie_services/retry.py`)

**Возможности:**
- Автоматические повторы при ошибках
- Экспоненциальная задержка
- Настраиваемые параметры

**Использование:**
```python
from bot_kie_services.retry import retry_async, RetryConfig, with_retry

# Вариант 1: Использование функции
result = await retry_async(
    api_call,
    config=RetryConfig(max_attempts=3, initial_delay=1.0),
    arg1, arg2
)

# Вариант 2: Декоратор
@with_retry(RetryConfig(max_attempts=3))
async def api_call():
    # Ваш код
    pass
```

### 4. ✅ Улучшенное логирование (`bot_kie_utils/logger.py`)

**Возможности:**
- Структурированное логирование (JSON)
- Контекстные логи
- Настройка уровней и форматов

**Использование:**
```python
from bot_kie_utils.logger import setup_logging, get_logger, LoggerAdapter

# Настройка логирования
setup_logging(level=logging.INFO, structured=True, log_file='bot.log')

# Получить logger
logger = get_logger(__name__)

# Logger с контекстом
adapter = LoggerAdapter(logger, {'user_id': 123, 'model_id': 'z-image'})
adapter.info("Generation started")
```

### 5. ✅ Health Checks (`bot_kie_services/health.py`)

**Возможности:**
- Проверка состояния компонентов
- Мониторинг доступности
- История проверок

**Использование:**
```python
from bot_kie_services import health_check_service

# Выполнить проверки
health_status = await health_check_service.run_checks()

# Получить общее состояние
overall = health_check_service.get_overall_health()
if not overall['healthy']:
    # Система нездорова
    pass
```

**Проверки:**
- Storage (доступность файлов)
- API (доступность HTTP клиента)
- Cache (работа кэша)

### 6. ✅ Автоматическая очистка (`bot_kie_services/cleanup.py`)

**Возможности:**
- Очистка старых сессий
- Удаление старых логов
- Очистка временных файлов

**Использование:**
```python
from bot_kie_services import cleanup_service

# Выполнить все очистки
cleanup_service.run_all_cleanups()

# Или отдельно
cleanup_service.cleanup_old_sessions(max_age_hours=24)
cleanup_service.cleanup_old_logs(max_age_days=30)
cleanup_service.cleanup_temp_files(max_age_hours=1)
```

## 📋 РЕКОМЕНДАЦИИ ПО ИНТЕГРАЦИИ

### Интеграция в bot_kie.py

1. **Добавить rate limiting в handlers:**
```python
from bot_kie_services import rate_limit_service

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверка rate limit
    is_allowed, remaining = rate_limit_service.check_message(user_id)
    if not is_allowed:
        await update.message.reply_text(
            f"Слишком много запросов. Попробуйте через минуту. "
            f"Осталось запросов: {remaining}"
        )
        return
    
    # Остальной код...
```

2. **Добавить метрики:**
```python
from bot_kie_services import metrics_service

async def handle_generation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    metrics_service.increment('total_generations')
    
    try:
        # Генерация...
        metrics_service.record_time('generation_duration', time.time() - start_time)
    except Exception as e:
        metrics_service.record_error('GenerationError', str(e), user_id)
        raise
```

3. **Добавить retry для API:**
```python
from bot_kie_services.retry import retry_async, RetryConfig

async def call_api():
    config = RetryConfig(max_attempts=3, initial_delay=1.0)
    return await retry_async(actual_api_call, config)
```

4. **Добавить периодические задачи:**
```python
async def periodic_tasks():
    """Периодические задачи"""
    while True:
        await asyncio.sleep(3600)  # Каждый час
        
        # Health checks
        await health_check_service.run_checks()
        
        # Cleanup
        cleanup_service.run_all_cleanups()

# Запустить в main
asyncio.create_task(periodic_tasks())
```

## 🎯 ПРЕИМУЩЕСТВА

1. **Мониторинг**: Видно что происходит в системе
2. **Надежность**: Retry механизм повышает стабильность
3. **Защита**: Rate limiting защищает от злоупотреблений
4. **Отладка**: Улучшенное логирование упрощает поиск проблем
5. **Производительность**: Автоматическая очистка предотвращает утечки памяти

## 📊 МЕТРИКИ ДЛЯ МОНИТОРИНГА

- `total_requests` - общее количество запросов
- `total_generations` - общее количество генераций
- `total_errors` - общее количество ошибок
- `total_users` - количество пользователей
- `total_revenue` - общий доход
- `generation_duration` - среднее время генерации
- `api_response_time` - время ответа API

## ⚠️ ВАЖНО

Все новые сервисы опциональны и не ломают существующий код. Можно постепенно интегрировать их в систему.



