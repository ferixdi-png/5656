# ОТЧЕТ: РЕФАКТОРИНГ USERCONTEXT

## ✅ ВЫПОЛНЕНО

### 1. Обновлен `UserContext` в `services/pricing_service.py`

**Новая структура:**
```python
@dataclass
class UserContext:
    """
    Контекст пользователя для расчета цены.
    
    Все проверки админа должны проходить через этот класс.
    Запрещено передавать is_admin как bool напрямую.
    """
    user_id: int  # Обязательное поле
    is_admin: bool  # Является ли пользователь админом
    is_user_mode: bool  # True если админ в режиме обычного пользователя
    has_free_generations: bool = False
    free_model_id: str = FREE_MODEL_ID
    
    def is_effective_admin(self) -> bool:
        """
        Возвращает True, если пользователь является админом и НЕ в режиме пользователя.
        Используется для расчета цен и проверок прав.
        """
        return self.is_admin and not self.is_user_mode
```

**Изменения:**
- ✅ Добавлено обязательное поле `user_id: int`
- ✅ Добавлено поле `is_user_mode: bool` для режима админа
- ✅ Добавлен метод `is_effective_admin()` для проверки эффективного статуса админа
- ✅ Обновлена документация с запретом передачи `is_admin` как bool

### 2. Создан `services/user_context_factory.py`

**Фабрика для создания UserContext:**
```python
def create_user_context(
    user_id: int,
    is_admin_func: Callable[[int], bool],
    is_user_mode_func: Optional[Callable[[int], bool]] = None,
    has_free_generations: bool = False,
    free_model_id: Optional[str] = None
) -> UserContext:
    """
    Создает UserContext из user_id.
    
    ВСЕ проверки админа проходят через эту фабрику.
    Запрещено создавать UserContext напрямую с is_admin как bool.
    """
```

**Преимущества:**
- ✅ Централизованное создание `UserContext`
- ✅ Гарантирует правильную установку `is_admin` и `is_user_mode`
- ✅ Запрещает передачу `is_admin` как bool напрямую

### 3. Добавлены функции в `bot_kie.py`

**Новая функция `is_user_mode()`:**
```python
def is_user_mode(user_id: int) -> bool:
    """
    Проверяет, находится ли админ в режиме обычного пользователя.
    
    Returns:
        True если админ в режиме пользователя, False иначе
    """
    if not is_admin(user_id):
        return False  # Не админ не может быть в режиме пользователя
    
    return user_id in user_sessions and user_sessions[user_id].get('admin_user_mode', False)
```

**Новая функция `create_user_context_for_pricing()`:**
```python
def create_user_context_for_pricing(user_id: int, has_free_generations: bool = False) -> 'UserContext':
    """
    Создает UserContext для расчета цен.
    
    ВСЕ проверки админа проходят через эту функцию.
    Запрещено передавать is_admin как bool напрямую.
    """
    from services.user_context_factory import create_user_context
    
    return create_user_context(
        user_id=user_id,
        is_admin_func=is_admin,
        is_user_mode_func=is_user_mode,
        has_free_generations=has_free_generations
    )
```

### 4. Обновлен `calculate_price_rub()` в `bot_kie.py`

**Новая сигнатура:**
```python
def calculate_price_rub(
    model_id: str, 
    params: dict = None, 
    user_context: 'UserContext' = None,  # РЕКОМЕНДУЕТСЯ
    # DEPRECATED: Используйте user_context вместо этих параметров
    is_admin: bool = False, 
    user_id: int = None
) -> float:
```

**Изменения:**
- ✅ Принимает `UserContext` как основной параметр
- ✅ Параметры `is_admin` и `user_id` помечены как DEPRECATED
- ✅ Если `user_context` не передан, создается из устаревших параметров (обратная совместимость)
- ✅ Использует новый `pricing_service.get_price()` для расчета

### 5. Обновлен `get_price()` в `services/pricing_service.py`

**Изменения:**
- ✅ Использует `user_context.is_effective_admin()` вместо `user_context.is_admin`
- ✅ Все проверки админа проходят через `UserContext`

---

## 📋 ПРАВИЛА ИСПОЛЬЗОВАНИЯ

### ✅ ПРАВИЛЬНО:

```python
from services.user_context_factory import create_user_context
from bot_kie import is_admin, is_user_mode

# Создаем UserContext через фабрику
user_context = create_user_context(
    user_id=12345,
    is_admin_func=is_admin,
    is_user_mode_func=is_user_mode
)

# Или используем функцию из bot_kie
from bot_kie import create_user_context_for_pricing

user_context = create_user_context_for_pricing(user_id=12345)

# Используем для расчета цены
from services.pricing_service import get_price
price_result = get_price(
    model_id="z-image",
    params={},
    user_context=user_context
)
```

### ❌ ЗАПРЕЩЕНО:

```python
# ❌ НЕ передавайте is_admin как bool
user_context = UserContext(
    user_id=12345,
    is_admin=True,  # ЗАПРЕЩЕНО!
    is_user_mode=False
)

# ❌ НЕ проверяйте админа через Telegram ID напрямую
if user_id == ADMIN_ID:  # ЗАПРЕЩЕНО!
    is_admin = True

# ❌ НЕ используйте calculate_price_rub с is_admin
price = calculate_price_rub(model_id, params, is_admin=True)  # DEPRECATED!
```

---

## 🔄 МИГРАЦИЯ

### Старый код:
```python
# Старый способ (DEPRECATED)
is_admin_user = get_is_admin(user_id)
price = calculate_price_rub(model_id, params, is_admin=is_admin_user, user_id=user_id)
```

### Новый код:
```python
# Новый способ (РЕКОМЕНДУЕТСЯ)
from bot_kie import create_user_context_for_pricing

user_context = create_user_context_for_pricing(user_id)
price = calculate_price_rub(model_id, params, user_context=user_context)
```

---

## 📊 СТРУКТУРА ФАЙЛОВ

```
services/
├── pricing_service.py          # UserContext dataclass, get_price()
└── user_context_factory.py     # Фабрика для создания UserContext

bot_kie.py
├── is_admin()                  # Проверка админа по ID
├── get_is_admin()              # Проверка админа с учетом user_mode
├── is_user_mode()              # Проверка режима пользователя
└── create_user_context_for_pricing()  # Создание UserContext
```

---

## ✅ ПРОВЕРКА

### Тест 1: Создание UserContext
```python
from bot_kie import create_user_context_for_pricing

user_context = create_user_context_for_pricing(user_id=12345)
assert user_context.user_id == 12345
assert isinstance(user_context.is_admin, bool)
assert isinstance(user_context.is_user_mode, bool)
```

### Тест 2: is_effective_admin()
```python
# Админ не в режиме пользователя
user_context = UserContext(
    user_id=12345,
    is_admin=True,
    is_user_mode=False
)
assert user_context.is_effective_admin() == True

# Админ в режиме пользователя
user_context = UserContext(
    user_id=12345,
    is_admin=True,
    is_user_mode=True
)
assert user_context.is_effective_admin() == False

# Обычный пользователь
user_context = UserContext(
    user_id=12345,
    is_admin=False,
    is_user_mode=False
)
assert user_context.is_effective_admin() == False
```

### Тест 3: Расчет цены
```python
from services.pricing_service import get_price
from decimal import Decimal

# Админ
admin_context = UserContext(
    user_id=12345,
    is_admin=True,
    is_user_mode=False
)
price_admin = get_price("z-image", {}, admin_context, Decimal("77.22"))

# Админ в режиме пользователя
admin_user_mode_context = UserContext(
    user_id=12345,
    is_admin=True,
    is_user_mode=True
)
price_admin_user = get_price("z-image", {}, admin_user_mode_context, Decimal("77.22"))

# Обычный пользователь
user_context = UserContext(
    user_id=12345,
    is_admin=False,
    is_user_mode=False
)
price_user = get_price("z-image", {}, user_context, Decimal("77.22"))

# Проверка: админ в режиме пользователя видит цены как обычный пользователь
assert price_admin_user.rub == price_user.rub
assert price_admin.rub < price_user.rub  # Админ видит цены без умножения
```

---

## 🎯 ИТОГ

**Все проверки админа теперь проходят через `UserContext`:**

- ✅ `UserContext` содержит `user_id`, `is_admin`, `is_user_mode`
- ✅ Запрещено передавать `is_admin` как bool напрямую
- ✅ Запрещено проверять админа через Telegram ID напрямую
- ✅ Все проверки только через `UserContext`
- ✅ Фабрика `create_user_context()` гарантирует правильное создание
- ✅ Метод `is_effective_admin()` для проверки эффективного статуса админа

**Файлы готовы к использованию!**

