# Руководство по интеграции БД в bot_kie.py

## Быстрый старт

### 1. Инициализация БД при запуске бота

Добавьте в начало `bot_kie.py` (после импортов):

```python
# Импорт модуля БД
try:
    from database import (
        init_database,
        get_user_balance as db_get_user_balance,
        update_user_balance as db_update_user_balance,
        add_to_balance as db_add_to_balance,
        create_operation,
        get_user_operations,
        log_kie_operation
    )
    DATABASE_AVAILABLE = True
    logger.info("✅ Модуль БД загружен успешно")
except ImportError as e:
    DATABASE_AVAILABLE = False
    logger.warning(f"⚠️ Модуль БД не доступен: {e}")
```

В функции `main()` добавьте инициализацию:

```python
def main():
    # ... существующий код ...
    
    # Инициализация БД
    if DATABASE_AVAILABLE:
        try:
            init_database()
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            DATABASE_AVAILABLE = False
```

### 2. Замена функций работы с балансом

Найдите функцию `get_user_balance` в `bot_kie.py` и замените на:

```python
def get_user_balance(user_id: int) -> float:
    """Get user balance in rubles."""
    if DATABASE_AVAILABLE:
        try:
            from decimal import Decimal
            balance = db_get_user_balance(user_id)
            return float(balance)
        except Exception as e:
            logger.error(f"Ошибка получения баланса из БД: {e}")
            # Fallback на старый метод
            pass
    
    # Старый метод через JSON (fallback)
    balances = load_json_file(BALANCES_FILE, {})
    return float(balances.get(str(user_id), 0.0))
```

Аналогично для функций обновления баланса:

```python
def update_user_balance(user_id: int, new_balance: float) -> bool:
    """Update user balance."""
    if DATABASE_AVAILABLE:
        try:
            from decimal import Decimal
            return db_update_user_balance(user_id, Decimal(str(new_balance)))
        except Exception as e:
            logger.error(f"Ошибка обновления баланса в БД: {e}")
            # Fallback на старый метод
            pass
    
    # Старый метод через JSON (fallback)
    balances = load_json_file(BALANCES_FILE, {})
    balances[str(user_id)] = new_balance
    save_json_file(BALANCES_FILE, balances)
    return True
```

### 3. Логирование операций KIE

В функциях генерации добавьте логирование:

```python
# После успешной генерации
if DATABASE_AVAILABLE:
    try:
        log_kie_operation(
            user_id=user_id,
            model=model_id,
            prompt=prompt[:1000] if prompt else None,  # Обрезаем до 1000 символов
            result_url=result_url
        )
    except Exception as e:
        logger.error(f"Ошибка логирования KIE: {e}")

# При ошибке
if DATABASE_AVAILABLE:
    try:
        log_kie_operation(
            user_id=user_id,
            model=model_id,
            prompt=prompt[:1000] if prompt else None,
            error_message=str(e)[:500]  # Обрезаем до 500 символов
        )
    except Exception as e2:
        logger.error(f"Ошибка логирования ошибки KIE: {e2}")
```

### 4. Создание записей об операциях

При списании/начислении баланса создавайте операции:

```python
# При списании
if DATABASE_AVAILABLE:
    try:
        from decimal import Decimal
        create_operation(
            user_id=user_id,
            operation_type='generation',
            amount=Decimal(f'-{cost}'),
            model=model_id,
            result_url=result_url,
            prompt=prompt[:1000] if prompt else None
        )
    except Exception as e:
        logger.error(f"Ошибка создания операции: {e}")

# При пополнении
if DATABASE_AVAILABLE:
    try:
        from decimal import Decimal
        create_operation(
            user_id=user_id,
            operation_type='payment',
            amount=Decimal(str(amount)),
            model=None,
            result_url=None,
            prompt=None
        )
    except Exception as e:
        logger.error(f"Ошибка создания операции: {e}")
```

## Миграция данных из JSON

Если у вас уже есть данные в JSON файлах, создайте скрипт миграции:

```python
# migrate_to_database.py
import json
from decimal import Decimal
from database import init_database, get_or_create_user, update_user_balance, create_operation

def migrate_balances():
    """Мигрирует балансы из JSON в БД."""
    try:
        with open('data/user_balances.json', 'r') as f:
            balances = json.load(f)
        
        for user_id_str, balance in balances.items():
            user_id = int(user_id_str)
            update_user_balance(user_id, Decimal(str(balance)))
            print(f"Мигрирован баланс для пользователя {user_id}: {balance}")
    except Exception as e:
        print(f"Ошибка миграции балансов: {e}")

if __name__ == '__main__':
    init_database()
    migrate_balances()
```

## Проверка работы

После интеграции проверьте:

1. Баланс сохраняется в БД
2. Операции создаются при генерации
3. Логи KIE записываются
4. Очистка работает (запустите `cleanup_database.py`)

## Откат на JSON (если нужно)

Если что-то пошло не так, просто установите `DATABASE_AVAILABLE = False` в начале файла, и бот будет использовать старый метод через JSON файлы.


