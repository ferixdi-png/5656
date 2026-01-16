"""
Сервис расчёта цен для моделей KIE AI.
"""

import logging
from typing import Optional, Dict
from app.config import Settings
from app.kie_catalog.catalog import get_model, ModelSpec

logger = logging.getLogger(__name__)


def get_usd_to_rub(settings: Settings) -> float:
    """
    Получает курс USD к RUB из настроек.
    
    Args:
        settings: Настройки приложения
    
    Returns:
        Курс USD к RUB (по умолчанию 100.0)
    """
    return getattr(settings, 'usd_to_rub', 100.0)


def user_price_rub(official_usd: float, usd_to_rub: float, price_multiplier: float = 2.0) -> int:
    """
    Рассчитывает цену для пользователя в рублях.
    
    Формула: official_usd * usd_to_rub * price_multiplier
    
    Args:
        official_usd: Официальная цена в USD (Our Price)
        usd_to_rub: Курс USD к RUB
        price_multiplier: Множитель цены (по умолчанию 2.0)
    
    Returns:
        Цена в рублях (округляется до целого, минимум 1₽)
    """
    price = official_usd * usd_to_rub * price_multiplier
    price_int = max(1, int(round(price)))
    return price_int


def price_for_model_rub(model_id: str, mode_index: int, settings: Settings) -> Optional[int]:
    """
    Рассчитывает цену для конкретной модели и режима в рублях.
    
    Args:
        model_id: ID модели
        mode_index: Индекс режима в списке modes модели
        settings: Настройки приложения
    
    Returns:
        Цена в рублях или None, если модель/режим не найдены
    """
    model = get_model(model_id)
    if not model:
        logger.warning(f"Model not found: {model_id}")
        return None
    
    if mode_index < 0 or mode_index >= len(model.modes):
        logger.warning(f"Invalid mode index {mode_index} for model {model_id}")
        return None
    
    mode = model.modes[mode_index]
    usd_to_rub = get_usd_to_rub(settings)
    price_multiplier = getattr(settings, 'price_multiplier', 2.0)
    
    return user_price_rub(mode.official_usd, usd_to_rub, price_multiplier)


def get_model_price_info(model_id: str, mode_index: int, settings: Settings) -> Optional[Dict]:
    """
    Получает полную информацию о цене модели.
    
    Args:
        model_id: ID модели
        mode_index: Индекс режима
        settings: Настройки приложения
    
    Returns:
        Словарь с информацией о цене или None
    """
    model = get_model(model_id)
    if not model:
        return None
    
    if mode_index < 0 or mode_index >= len(model.modes):
        return None
    
    mode = model.modes[mode_index]
    usd_to_rub = get_usd_to_rub(settings)
    price_multiplier = getattr(settings, 'price_multiplier', 2.0)
    price_rub = user_price_rub(mode.official_usd, usd_to_rub, price_multiplier)
    
    return {
        "model_id": model_id,
        "model_title": model.title_ru,
        "mode_index": mode_index,
        "mode_notes": mode.notes,
        "unit": mode.unit,
        "credits": mode.credits,
        "official_usd": mode.official_usd,
        "usd_to_rub": usd_to_rub,
        "price_multiplier": price_multiplier,
        "price_rub": price_rub
    }

