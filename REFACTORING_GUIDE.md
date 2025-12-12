# Руководство по использованию новой структуры

## 📁 Новая структура проекта

```
bot_kie_handlers/     # Обработчики команд и callback'ов
bot_kie_services/     # Бизнес-логика и сервисы
bot_kie_models/       # Модели данных
bot_kie_utils/        # Утилиты и вспомогательные функции
config.py             # Централизованная конфигурация
```

## 🚀 Как использовать новые сервисы

### 1. Конфигурация

```python
from config import settings

# Использование настроек
admin_id = settings.ADMIN_ID
bot_token = settings.BOT_TOKEN
free_generations = settings.FREE_GENERATIONS_PER_DAY
```

### 2. Обработка ошибок

```python
from bot_kie_utils.errors import BotError, ValidationError, handle_errors

@handle_errors
async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Ваш код
        pass
    except ValidationError as e:
        await update.message.reply_text(e.user_message, parse_mode='HTML')
```

### 3. Ценообразование

```python
from bot_kie_services import pricing_service

# Расчет цены
price = pricing_service.calculate_price_rub(
    model_id="z-image",
    params={"aspect_ratio": "1:1"},
    is_admin=False
)

# Форматирование цены
price_text = pricing_service.format_price(price, is_admin=False)
```

### 4. Хранение данных

```python
from bot_kie_services import storage_service

# Получить баланс
balance = storage_service.get_user_balance(user_id)

# Установить баланс
storage_service.set_user_balance(user_id, 100.0)

# Добавить к балансу
new_balance = storage_service.add_user_balance(user_id, 50.0)
```

### 5. Валидация

```python
from bot_kie_services import model_validator

# Валидация данных
result = model_validator.validate("z-image", {
    "prompt": "test",
    "aspect_ratio": "1:1"
})

if result.valid:
    print("Данные валидны")
else:
    print(f"Ошибки: {result.errors}")
    print(f"Предупреждения: {result.warnings}")
```

### 6. Вспомогательные функции

```python
from bot_kie_utils.helpers import (
    is_admin,
    normalize_float,
    normalize_int,
    normalize_bool,
    normalize_enum,
    normalize_image_size,
    is_placeholder
)

# Проверка админа
if is_admin(user_id):
    # Админ логика
    pass

# Нормализация значений
float_value = normalize_float("3,5")  # 3.5
int_value = normalize_int("10")  # 10
bool_value = normalize_bool("true")  # True

# Проверка placeholder
if is_placeholder("Upload successfully"):
    # Это placeholder
    pass
```

### 7. Кэширование

```python
from bot_kie_services import cache_service

# Кэш автоматически используется в pricing_service и storage_service
# Но можно использовать напрямую:

# Получить из кэша
cached_price = cache_service.get_price(model_id, params, is_admin)

# Сохранить в кэш
cache_service.set_price(model_id, params, is_admin, price)

# Инвалидировать кэш баланса
cache_service.invalidate_balance(user_id)
```

## 🔄 Миграция существующего кода

### Старый способ:
```python
from bot_kie import calculate_price_rub, get_user_balance

price = calculate_price_rub("z-image", {}, False)
balance = get_user_balance(user_id)
```

### Новый способ:
```python
from bot_kie_services import pricing_service, storage_service

price = pricing_service.calculate_price_rub("z-image", {}, False)
balance = storage_service.get_user_balance(user_id)
```

## 📝 Преимущества новой структуры

1. **Модульность**: Код разделен на логические модули
2. **Тестируемость**: Легче писать тесты для отдельных компонентов
3. **Переиспользование**: Сервисы можно использовать в разных местах
4. **Кэширование**: Автоматическое кэширование для производительности
5. **Типобезопасность**: Лучшая поддержка типов
6. **Централизация**: Вся конфигурация в одном месте

## ⚠️ Обратная совместимость

Все существующие функции в `bot_kie.py` продолжают работать. Новая структура использует их внутри для обратной совместимости. Постепенно можно переносить код в новые модули.

## 🎯 Следующие шаги

1. ✅ Создана базовая структура
2. ✅ Созданы основные сервисы
3. ⏳ Перенос handlers в отдельные файлы
4. ⏳ Полный рефакторинг calculate_price_rub
5. ⏳ Миграция на SQLite (опционально)



