# Оптимизация базы данных для эффективного использования 1 ГБ

## Обзор

База данных оптимизирована для хранения баланса и истории операций в компактном формате. Структура разработана так, чтобы 1 ГБ хватило на тысячи пользователей и сотни тысяч операций.

## Структура базы данных

### Таблицы

1. **users** - Пользователи с балансом
   - `id BIGINT` - ID пользователя Telegram
   - `balance NUMERIC(12,2)` - Баланс (до 99,999,999,999.99)
   - `created_at TIMESTAMPTZ` - Дата создания
   - `updated_at TIMESTAMPTZ` - Дата обновления

2. **operations** - История операций (тонкие записи)
   - `id BIGSERIAL` - Уникальный ID операции
   - `user_id BIGINT` - ID пользователя
   - `type TEXT` - Тип операции (payment, generation, refund)
   - `amount NUMERIC(12,2)` - Сумма операции
   - `model TEXT` - Название модели (если применимо)
   - `result_url TEXT` - URL результата (НЕ сам файл!)
   - `prompt TEXT` - Промпт (обрезанный до 1000 символов)
   - `created_at TIMESTAMPTZ` - Дата создания

3. **kie_logs** - Логи операций KIE (с автоматической очисткой)
   - `id BIGSERIAL` - Уникальный ID
   - `user_id BIGINT` - ID пользователя
   - `model TEXT` - Модель
   - `prompt TEXT` - Промпт (обрезанный до 1000 символов)
   - `result_url TEXT` - URL результата
   - `error_message TEXT` - Сообщение об ошибке (обрезанный до 500 символов)
   - `created_at TIMESTAMPTZ` - Дата создания

4. **debug_logs** - Debug логи (временные, очищаются автоматически)
   - `id BIGSERIAL` - Уникальный ID
   - `level TEXT` - Уровень лога
   - `message TEXT` - Сообщение (обрезанный до 1000 символов)
   - `context JSONB` - Контекст (легковесный JSON)
   - `created_at TIMESTAMPTZ` - Дата создания

## Принципы оптимизации

### ✅ Что хранится в БД:
- Баланс пользователей (NUMERIC - компактный формат)
- История операций (только метаданные)
- URL результатов (не сами файлы!)
- Обрезанные промпты (до 1000 символов)
- Обрезанные сообщения об ошибках (до 500 символов)

### ❌ Что НЕ хранится в БД:
- Сами картинки/видео от нейросетей
- Большие JSON-логи
- Полные промпты без ограничений
- Временные данные старше 30 дней

## Установка и настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Убедитесь, что в `.env` или в настройках Render установлена переменная:

```
DATABASE_URL=postgresql://user:password@host:port/database
```

Также можно настроить период хранения логов:

```
LOG_RETENTION_DAYS=30  # По умолчанию 30 дней
```

### 3. Инициализация базы данных

Запустите скрипт инициализации:

```bash
python init_database.py
```

Это создаст все необходимые таблицы, индексы и функции.

## Использование

### Работа с балансом

```python
from database import get_user_balance, update_user_balance, add_to_balance
from decimal import Decimal

# Получить баланс
balance = get_user_balance(user_id=123456789)

# Обновить баланс
update_user_balance(user_id=123456789, new_balance=Decimal('100.50'))

# Добавить к балансу
add_to_balance(user_id=123456789, amount=Decimal('50.00'))
```

### Создание операции

```python
from database import create_operation
from decimal import Decimal

# Создать операцию
operation_id = create_operation(
    user_id=123456789,
    operation_type='generation',
    amount=Decimal('-5.00'),
    model='flux-2-pro',
    result_url='https://example.com/result.jpg',
    prompt='Create a beautiful sunset'  # Автоматически обрежется до 1000 символов
)
```

### Получение истории операций

```python
from database import get_user_operations

# Получить последние 50 операций
operations = get_user_operations(user_id=123456789, limit=50)

# Получить операции определенного типа
payment_operations = get_user_operations(
    user_id=123456789,
    operation_type='payment',
    limit=20
)
```

### Логирование

```python
from database import log_kie_operation, log_debug

# Логировать операцию KIE
log_kie_operation(
    user_id=123456789,
    model='flux-2-pro',
    prompt='Create a sunset',
    result_url='https://example.com/result.jpg'
)

# Логировать ошибку
log_kie_operation(
    user_id=123456789,
    model='flux-2-pro',
    prompt='Create a sunset',
    error_message='API timeout'
)

# Debug логирование
log_debug(
    level='INFO',
    message='User requested generation',
    context={'user_id': 123456789, 'model': 'flux-2-pro'}
)
```

## Очистка старых данных

### Автоматическая очистка (Cron)

Настройте cron для автоматической очистки старых логов. Например, для очистки каждый день в 3:00:

```bash
0 3 * * * cd /path/to/project && python cleanup_database.py
```

Или добавьте в `render.yaml`:

```yaml
services:
  - type: cron
    name: cleanup-database
    schedule: "0 3 * * *"
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python cleanup_database.py"
```

### Ручная очистка

```bash
python cleanup_database.py
```

Скрипт удалит все логи старше 30 дней (или значение из `LOG_RETENTION_DAYS`).

## Мониторинг размера БД

Проверить размер базы данных:

```python
from database import get_database_size

db_info = get_database_size()
print(f"Размер БД: {db_info['database_size']['db_size']}")
print("Таблицы:")
for table in db_info['tables']:
    print(f"  {table['tablename']}: {table['size']}")
```

## Оценка использования пространства

### Примерные расчеты:

- **users**: ~50 байт на пользователя
  - 1000 пользователей = ~50 КБ

- **operations**: ~200 байт на операцию
  - 100,000 операций = ~20 МБ

- **kie_logs**: ~300 байт на запись
  - 10,000 записей (за 30 дней) = ~3 МБ

- **debug_logs**: ~250 байт на запись
  - 5,000 записей (за 30 дней) = ~1.25 МБ

**Итого для 1000 пользователей и 100,000 операций: ~25 МБ**

Это означает, что 1 ГБ хватит на:
- **~40,000 пользователей**
- **~4,000,000 операций**
- **~400,000 KIE логов (за 30 дней)**
- **~200,000 debug логов (за 30 дней)**

## Рекомендации

1. **Регулярно запускайте очистку** - настройте cron для автоматической очистки старых логов
2. **Мониторьте размер БД** - периодически проверяйте размер таблиц
3. **Не храните файлы в БД** - используйте внешнее хранилище (S3, Cloud Storage)
4. **Обрезайте длинные тексты** - промпты и сообщения автоматически обрезаются
5. **Используйте индексы** - все важные поля проиндексированы для быстрого поиска

## Интеграция в bot_kie.py

Для интеграции в основной бот добавьте в начало файла:

```python
from database import (
    get_user_balance, update_user_balance, add_to_balance,
    create_operation, get_user_operations,
    log_kie_operation, init_database
)

# Инициализация БД при запуске
init_database()
```

Затем используйте функции для работы с балансом и операциями вместо JSON файлов.


