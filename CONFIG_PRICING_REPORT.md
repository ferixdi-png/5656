# ОТЧЕТ: ВЫНЕСЕНИЕ КОНСТАНТ В CONFIG/PRICING.PY

## ✅ ВЫПОЛНЕНО

### 1. Создан файл `config/pricing.py`

**Вынесены все константы и коэффициенты:**

#### Основные константы:
- ✅ `CREDIT_TO_USD = Decimal("0.005")` - конвертация кредитов в USD
- ✅ `USD_TO_RUB_DEFAULT = Decimal("77.2222")` - курс USD к RUB
- ✅ `USER_PRICE_MULTIPLIER = Decimal("2")` - множитель цены для пользователей
- ✅ `DEFAULT_FALLBACK_CREDITS = Decimal("1.0")` - дефолтная цена при отсутствии модели

#### Дефолтные параметры:
- ✅ `DEFAULT_VIDEO_DURATION = 5` - дефолтная длительность видео
- ✅ `DEFAULT_RESOLUTION = "720p"` - дефолтное разрешение
- ✅ `DEFAULT_RESOLUTION_1K = "1K"` - для моделей с 1K/2K/4K
- ✅ `DEFAULT_RESOLUTION_480P = "480p"` - для моделей с 480p/720p/1080p
- ✅ `DEFAULT_RESOLUTION_768P = "768P"` - для моделей с 768P/1080P
- ✅ `DEFAULT_N_FRAMES = "10"` - дефолтное количество кадров
- ✅ `DEFAULT_SIZE = "standard"` - дефолтный размер
- ✅ `DEFAULT_RENDERING_SPEED = "BALANCED"` - дефолтная скорость рендеринга
- ✅ `DEFAULT_UPSCALE_FACTOR = "2"` - дефолтный upscale factor
- ✅ `DEFAULT_IMAGE_SIZE = "square_hd"` - дефолтный размер изображения
- ✅ `DEFAULT_IMAGE_SIZE_EDIT = "landscape_4_3"` - для qwen/image-edit
- ✅ `DEFAULT_DURATION_STR = "5"` - дефолтная длительность как строка
- ✅ `DEFAULT_DURATION_INT = 5` - дефолтная длительность как число
- ✅ `DEFAULT_DURATION_HAILUO = 6` - для Hailuo моделей
- ✅ `DEFAULT_DURATION_HAILUO_STR = "6"` - для Hailuo моделей (строка)

#### Специальные константы:
- ✅ `FREE_MODEL_ID = "z-image"` - ID бесплатной модели
- ✅ `DEFAULT_CURRENCY = "RUB"` - валюта по умолчанию
- ✅ `ZERO_CREDITS = Decimal("0")` - нулевое значение кредитов
- ✅ `ZERO_RUB = Decimal("0")` - нулевое значение рублей

#### Коэффициенты для расчета:
- ✅ `MEGAPIXELS_MAP` - карта мегапикселей для разных размеров изображений
- ✅ `QWEN_CREDITS_PER_MEGAPIXEL = Decimal("4")` - кредиты за мегапиксель для qwen/text-to-image
- ✅ `QWEN_EDIT_CREDITS_PER_MEGAPIXEL = Decimal("6")` - кредиты за мегапиксель для qwen/image-edit

### 2. Обновлен `services/pricing_service.py`

**Все хардкод числа заменены на константы:**

- ✅ `CREDIT_TO_USD` → импорт из `config.pricing`
- ✅ `USD_TO_RUB_DEFAULT` → импорт из `config.pricing`
- ✅ `FREE_MODEL_ID` → импорт из `config.pricing`
- ✅ `Decimal("2")` → `USER_PRICE_MULTIPLIER`
- ✅ `Decimal("1.0")` → `DEFAULT_FALLBACK_CREDITS`
- ✅ `Decimal("0")` → `ZERO_CREDITS` / `ZERO_RUB`
- ✅ `"RUB"` → `DEFAULT_CURRENCY`
- ✅ Все дефолтные значения заменены на константы

**Все функции-калькуляторы используют константы:**
- ✅ `_resolution_based_price()` - использует `DEFAULT_RESOLUTION_1K`
- ✅ `_duration_based_price()` - использует `DEFAULT_DURATION_STR`
- ✅ `_duration_sound_price()` - использует `DEFAULT_DURATION_STR`
- ✅ `_duration_resolution_price()` - использует `DEFAULT_RESOLUTION`, `DEFAULT_DURATION_INT`
- ✅ `_n_frames_price()` - использует `DEFAULT_N_FRAMES`
- ✅ `_size_n_frames_price()` - использует `DEFAULT_SIZE`, `DEFAULT_N_FRAMES`
- ✅ `_rendering_speed_num_images_price()` - использует `DEFAULT_RENDERING_SPEED`
- ✅ `_upscale_factor_price()` - использует `DEFAULT_UPSCALE_FACTOR`
- ✅ `_megapixels_price()` - использует `DEFAULT_IMAGE_SIZE`, `MEGAPIXELS_MAP`, `QWEN_CREDITS_PER_MEGAPIXEL`
- ✅ `_megapixels_num_images_price()` - использует `DEFAULT_IMAGE_SIZE_EDIT`, `MEGAPIXELS_MAP`, `QWEN_EDIT_CREDITS_PER_MEGAPIXEL`
- ✅ `_resolution_duration_matrix_price()` - использует `DEFAULT_RESOLUTION`, `DEFAULT_DURATION_STR`
- ✅ `_resolution_duration_default_price()` - использует `DEFAULT_RESOLUTION_480P`, `DEFAULT_DURATION_INT`

### 3. Создан `config/__init__.py`

**Экспорт всех констант для удобного импорта**

---

## 📋 СТРУКТУРА ФАЙЛОВ

```
config/
├── __init__.py          # Экспорт констант
└── pricing.py           # Все константы и коэффициенты

services/
└── pricing_service.py   # Бизнес-логика (без хардкода чисел)
```

---

## ✅ ПРОВЕРКА

### Тест 1: Импорт констант
```python
from config.pricing import CREDIT_TO_USD, USER_PRICE_MULTIPLIER
# ✅ Работает
```

### Тест 2: Расчет цены с множителем
```python
from services.pricing_service import get_price, UserContext
from decimal import Decimal

# Пользователь (цена * 2)
result1 = get_price('z-image', {}, UserContext(is_admin=False), Decimal('77.22'))
# User price: 0.617760 RUB

# Админ (цена без умножения)
result2 = get_price('z-image', {}, UserContext(is_admin=True), Decimal('77.22'))
# Admin price: 0.308880 RUB

# Проверка множителя
result1.rub / result2.rub == 2  # ✅ True
```

### Тест 3: Синтаксис
```bash
python -m py_compile config/pricing.py services/pricing_service.py
# ✅ Успешно
```

---

## 📊 СРАВНЕНИЕ

### БЫЛО (services/pricing_service.py):

```python
# Хардкод в коде
CREDIT_TO_USD = Decimal("0.005")
USD_TO_RUB_DEFAULT = Decimal("77.2222")
FREE_MODEL_ID = "z-image"

# В функции get_price():
price_rub *= Decimal("2")  # Хардкод множителя
base_credits = Decimal("1.0")  # Хардкод fallback
return PriceResult(..., currency="RUB")  # Хардкод валюты

# В функциях-калькуляторах:
default_resolution: str = "720p"  # Хардкод
default_duration: str = "5"  # Хардкод
default_n_frames: str = "10"  # Хардкод
```

**Проблемы:**
- ❌ Константы смешаны с бизнес-логикой
- ❌ Хардкод чисел в коде
- ❌ Сложно изменять коэффициенты
- ❌ Нет единого места для конфигурации

### СТАЛО:

**config/pricing.py:**
```python
# Все константы в одном месте
CREDIT_TO_USD = Decimal("0.005")
USER_PRICE_MULTIPLIER = Decimal("2")
DEFAULT_VIDEO_DURATION = 5
DEFAULT_RESOLUTION = "720p"
# ... и т.д.
```

**services/pricing_service.py:**
```python
# Импорт констант
from config.pricing import (
    CREDIT_TO_USD,
    USER_PRICE_MULTIPLIER,
    DEFAULT_VIDEO_DURATION,
    # ... и т.д.
)

# Использование констант
price_rub *= USER_PRICE_MULTIPLIER  # Используем константу
base_credits = DEFAULT_FALLBACK_CREDITS  # Используем константу
return PriceResult(..., currency=DEFAULT_CURRENCY)  # Используем константу

# В функциях-калькуляторах:
default_resolution: str = None  # Будет использоваться DEFAULT_RESOLUTION
if default_resolution is None:
    default_resolution = DEFAULT_RESOLUTION  # Используем константу
```

**Преимущества:**
- ✅ Константы отделены от бизнес-логики
- ✅ Нет хардкода чисел в pricing_service
- ✅ Легко изменять коэффициенты (все в одном файле)
- ✅ Единое место для конфигурации
- ✅ Легко тестировать (можно подменять константы)

---

## 🎯 ИТОГ

**Все константы и коэффициенты вынесены в `config/pricing.py`:**

- ✅ `CREDIT_TO_USD`
- ✅ `USER_PRICE_MULTIPLIER`
- ✅ `DEFAULT_VIDEO_DURATION`
- ✅ Все дефолтные параметры
- ✅ Все коэффициенты расчета
- ✅ Все специальные константы

**`services/pricing_service.py` не содержит хардкода чисел:**
- ✅ Все числа импортируются из `config.pricing`
- ✅ Все дефолтные значения используют константы
- ✅ Только цены моделей остались в `MODEL_PRICING` (это данные, не константы)

**Файлы готовы к использованию!**

