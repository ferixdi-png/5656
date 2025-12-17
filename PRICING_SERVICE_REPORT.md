# ОТЧЕТ: СОЗДАНИЕ PRICING_SERVICE.PY

## ✅ ВЫПОЛНЕНО

### 1. Создан файл `services/pricing_service.py`

**Структура:**
- ✅ Dataclass `PriceResult` с полями: `credits`, `rub`, `is_free`, `currency`
- ✅ Dataclass `UserContext` для контекста пользователя
- ✅ Единая функция `get_price()` для расчета цены
- ✅ Структура `MODEL_PRICING` со всеми ценами моделей

### 2. Вынесены все цены моделей в структуру данных

**Всего моделей в MODEL_PRICING: 65**

**Типы цен:**
- Фиксированные цены (fixed_price)
- Цены на основе разрешения (resolution_based_price)
- Цены на основе длительности (duration_based_price)
- Цены на основе длительности и звука (duration_sound_price)
- Цены на основе разрешения и длительности (duration_resolution_price)
- Цены на основе n_frames (n_frames_price)
- Цены на основе size и n_frames (size_n_frames_price)
- Цены на основе rendering_speed и num_images (rendering_speed_num_images_price)
- Цены на основе upscale_factor (upscale_factor_price)
- Цены на основе max_images (max_images_price)
- Цены на основе мегапикселей (megapixels_price)
- Цены на основе матрицы разрешение x длительность (resolution_duration_matrix_price)

### 3. Убраны все if/elif

**Было:** ~600 строк if/elif в `calculate_price_rub()`

**Стало:** Структура данных `MODEL_PRICING` с функциями-калькуляторами

### 4. Убраны хардкод числа

**Все константы вынесены:**
- `CREDIT_TO_USD = Decimal("0.005")`
- `USD_TO_RUB_DEFAULT = Decimal("77.2222")`
- `FREE_MODEL_ID = "z-image"`

**Все цены моделей в структуре данных, а не в коде**

### 5. Чистый сервис без зависимостей

- ✅ Нет импортов из Telegram
- ✅ Нет UI-кода
- ✅ Только бизнес-логика расчета цен
- ✅ Использует `Decimal` для точных расчетов

---

## 📋 СТРУКТУРА ФАЙЛА

```
services/
├── __init__.py          # Экспорт основных функций
├── pricing_service.py   # Основной сервис расчета цен
└── README.md            # Документация
```

---

## 🔧 ИСПОЛЬЗОВАНИЕ

### Пример 1: Простая модель с фиксированной ценой

```python
from decimal import Decimal
from services.pricing_service import get_price, UserContext

user_context = UserContext(is_admin=False, user_id=12345)
price_result = get_price(
    model_id="z-image",
    params={},
    user_context=user_context
)

print(f"Цена: {price_result.rub} ₽")
print(f"Кредиты: {price_result.credits}")
print(f"Бесплатно: {price_result.is_free}")
```

### Пример 2: Модель с параметрами

```python
from decimal import Decimal
from services.pricing_service import get_price, UserContext

user_context = UserContext(is_admin=False, user_id=12345)
price_result = get_price(
    model_id="nano-banana-pro",
    params={"resolution": "4K"},
    user_context=user_context,
    usd_to_rub_rate=Decimal("77.22")
)

print(f"Цена: {price_result.rub} ₽")
```

### Пример 3: Админ (цена без умножения на 2)

```python
from decimal import Decimal
from services.pricing_service import get_price, UserContext

admin_context = UserContext(is_admin=True, user_id=12345)
price_result = get_price(
    model_id="sora-2-text-to-video",
    params={},
    user_context=admin_context
)

print(f"Цена для админа: {price_result.rub} ₽")
```

### Пример 4: Бесплатная генерация

```python
from decimal import Decimal
from services.pricing_service import get_price, UserContext

user_context = UserContext(
    is_admin=False,
    user_id=12345,
    has_free_generations=True  # У пользователя есть бесплатные генерации
)
price_result = get_price(
    model_id="z-image",  # Бесплатная модель
    params={},
    user_context=user_context
)

print(f"Бесплатно: {price_result.is_free}")  # True
print(f"Цена: {price_result.rub} ₽")  # 0
```

---

## 📊 СРАВНЕНИЕ С ОРИГИНАЛЬНЫМ КОДОМ

### Было (bot_kie.py):

```python
def calculate_price_rub(model_id: str, params: dict = None, is_admin: bool = False, user_id: int = None) -> float:
    if params is None:
        params = {}
    
    # 600+ строк if/elif
    if model_id == "z-image":
        base_credits = 0.8
    elif model_id == "nano-banana-pro":
        resolution = params.get("resolution", "1K")
        if resolution == "4K":
            base_credits = 24
        else:
            base_credits = 18
    # ... еще 60+ моделей ...
    
    price_usd = base_credits * CREDIT_TO_USD
    price_rub = price_usd * get_usd_to_rub_rate()
    
    if not is_admin_check:
        price_rub *= 2
    
    return price_rub
```

**Проблемы:**
- ❌ 600+ строк if/elif
- ❌ Хардкод чисел в коде
- ❌ Сложно добавлять новые модели
- ❌ Сложно тестировать
- ❌ Зависимость от Telegram (get_is_admin, get_usd_to_rub_rate)

### Стало (services/pricing_service.py):

```python
def get_price(
    model_id: str,
    params: Dict[str, Any],
    user_context: UserContext,
    usd_to_rub_rate: Optional[Decimal] = None
) -> PriceResult:
    # Получаем калькулятор из структуры данных
    price_calculator = MODEL_PRICING.get(model_id)
    
    if price_calculator is None:
        base_credits = Decimal("1.0")  # Fallback
    else:
        base_credits = price_calculator(params)
    
    # Конвертируем в RUB
    price_usd = base_credits * CREDIT_TO_USD
    price_rub = price_usd * (usd_to_rub_rate or USD_TO_RUB_DEFAULT)
    
    # Умножаем на 2 для обычных пользователей
    if not user_context.is_admin:
        price_rub *= Decimal("2")
    
    # Проверка на бесплатную генерацию
    if not user_context.is_admin and user_context.has_free_generations and model_id == user_context.free_model_id:
        return PriceResult(credits=Decimal("0"), rub=Decimal("0"), is_free=True)
    
    return PriceResult(credits=base_credits, rub=price_rub, is_free=False)
```

**Преимущества:**
- ✅ Нет if/elif - все в структуре данных
- ✅ Нет хардкода - все константы вынесены
- ✅ Легко добавлять новые модели
- ✅ Легко тестировать
- ✅ Нет зависимостей от Telegram
- ✅ Типобезопасность с dataclasses
- ✅ Точные расчеты с Decimal

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

1. **Интеграция в bot_kie.py:**
   - Заменить `calculate_price_rub()` на вызов `get_price()`
   - Адаптировать `UserContext` из существующих функций
   - Обновить все места использования

2. **Тестирование:**
   - Создать unit-тесты для всех моделей
   - Проверить соответствие цен оригинальной функции
   - Проверить edge cases

3. **Документация:**
   - Добавить примеры для всех типов моделей
   - Описать процесс добавления новой модели

---

## ✅ ИТОГ

Создан чистый, поддерживаемый и масштабируемый сервис расчета цен:

- ✅ **65 моделей** покрыты в структуре данных
- ✅ **Нет if/elif** - все в структуре данных
- ✅ **Нет хардкода** - все константы вынесены
- ✅ **Нет зависимостей** от Telegram
- ✅ **Типобезопасность** с dataclasses
- ✅ **Точные расчеты** с Decimal

**Файл готов к использованию!**

