"""
Примеры интеграции новой структуры в существующий код
"""

# ============================================
# ПРИМЕР 1: Использование нового PricingService
# ============================================

# Старый способ (все еще работает):
from bot_kie import calculate_price_rub

price_old = calculate_price_rub("z-image", {"aspect_ratio": "1:1"}, is_admin=False)

# Новый способ (рекомендуется):
from bot_kie_services import pricing_service

price_new = pricing_service.calculate_price_rub(
    "z-image",
    {"aspect_ratio": "1:1"},
    is_admin=False
)

# Преимущества нового способа:
# - Автоматическое кэширование
# - Лучшая структура кода
# - Легче тестировать


# ============================================
# ПРИМЕР 2: Использование StorageService
# ============================================

# Старый способ:
from bot_kie import get_user_balance, set_user_balance

balance_old = get_user_balance(user_id)
set_user_balance(user_id, 100.0)

# Новый способ:
from bot_kie_services import storage_service

balance_new = storage_service.get_user_balance(user_id)
storage_service.set_user_balance(user_id, 100.0)

# Преимущества:
# - Автоматическое кэширование балансов
# - Единый интерфейс для всех операций с данными
# - Легче перейти на БД в будущем


# ============================================
# ПРИМЕР 3: Использование ModelValidator
# ============================================

from bot_kie_services import model_validator

# Валидация данных перед отправкой в API
data = {
    "prompt": "test",
    "aspect_ratio": "1:1"
}

result = model_validator.validate("z-image", data)

if result.valid:
    print("Данные валидны, можно отправлять в API")
    if result.warnings:
        print(f"Предупреждения: {result.warnings}")
else:
    print(f"Ошибки валидации: {result.errors}")


# ============================================
# ПРИМЕР 4: Использование обработки ошибок
# ============================================

from bot_kie_utils.errors import handle_errors, ValidationError
from telegram import Update
from telegram.ext import ContextTypes

@handle_errors
async def example_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Если произойдет ошибка, она будет автоматически обработана
    # и пользователь получит понятное сообщение
    result = model_validator.validate("z-image", {})
    if not result.valid:
        raise ValidationError(
            message="Ошибка валидации",
            user_message="❌ Пожалуйста, проверьте введенные данные"
        )


# ============================================
# ПРИМЕР 5: Использование helpers
# ============================================

from bot_kie_utils.helpers import (
    normalize_float,
    normalize_int,
    normalize_bool,
    normalize_image_size,
    is_placeholder
)

# Нормализация данных из формы
guidance_scale = normalize_float("3,5")  # 3.5
num_images = normalize_int("2")  # 2
enable_safety = normalize_bool("true")  # True
image_size = normalize_image_size("Square HD")  # "square_hd"

# Проверка placeholder
if is_placeholder("Upload successfully"):
    # Это placeholder, нужно заменить на реальный URL
    pass


# ============================================
# ПРИМЕР 6: Использование конфигурации
# ============================================

from config import settings

# Вместо:
# FREE_GENERATIONS_PER_DAY = 5
# REFERRAL_BONUS_GENERATIONS = 5

# Используем:
free_gens = settings.FREE_GENERATIONS_PER_DAY
ref_bonus = settings.REFERRAL_BONUS_GENERATIONS


# ============================================
# ПРИМЕР 7: Комбинированное использование
# ============================================

from bot_kie_services import pricing_service, storage_service, model_validator
from bot_kie_utils.helpers import is_admin, normalize_float
from bot_kie_utils.errors import handle_errors

@handle_errors
async def process_generation_request(user_id: int, model_id: str, params: dict):
    # 1. Проверяем админа
    admin = is_admin(user_id)
    
    # 2. Валидируем данные
    validation_result = model_validator.validate(model_id, params)
    if not validation_result.valid:
        raise ValidationError(
            message="Validation failed",
            user_message=f"Ошибки: {', '.join(validation_result.errors)}"
        )
    
    # 3. Рассчитываем цену
    price = pricing_service.calculate_price_rub(model_id, params, admin)
    
    # 4. Проверяем баланс
    balance = storage_service.get_user_balance(user_id)
    
    if balance < price:
        raise PaymentError(
            message="Insufficient balance",
            user_message=f"Недостаточно средств. Требуется: {price:.2f} ₽, у вас: {balance:.2f} ₽"
        )
    
    # 5. Списываем средства
    new_balance = storage_service.add_user_balance(user_id, -price)
    
    return {
        "price": price,
        "new_balance": new_balance,
        "warnings": validation_result.warnings
    }
