"""
Продвинутая ценовая логика для KIE AI.
Использует только рубли, формула: price_rub = round(credits * admin_credit_rate * 2)
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

# Админский курс кредита к рублю (настраивается)
ADMIN_CREDIT_TO_RUB_RATE = 0.1  # 1 кредит = 0.1 рубля (пример)
MARGA_MULTIPLIER = 2.0  # Маржа x2


def get_credit_to_rub_rate() -> float:
    """Получает курс кредита к рублю (из админских настроек)."""
    try:
        # Можно загружать из БД или конфига
        import os
        rate = float(os.getenv('CREDIT_TO_RUB_RATE', ADMIN_CREDIT_TO_RUB_RATE))
        return rate
    except:
        return ADMIN_CREDIT_TO_RUB_RATE


def calculate_price_rub_from_credits(
    credits: float,
    credit_rate: Optional[float] = None
) -> float:
    """
    Рассчитывает цену в рублях из кредитов.
    
    Args:
        credits: Количество кредитов KIE AI
        credit_rate: Курс кредита к рублю (если None, используется админский)
    
    Returns:
        Цена в рублях
    """
    if credit_rate is None:
        credit_rate = get_credit_to_rub_rate()
    
    # Формула: price_rub = round(credits * credit_rate * маржа)
    price_rub = credits * credit_rate * MARGA_MULTIPLIER
    
    # Округляем до 2 знаков
    return round(price_rub, 2)


def get_model_credits(
    model_key: str,
    mode_id: str,
    params: Dict[str, Any]
) -> float:
    """
    Получает количество кредитов для модели и mode.
    
    Args:
        model_key: Ключ модели
        mode_id: ID mode
        params: Параметры генерации
    
    Returns:
        Количество кредитов
    """
    try:
        from kie_models_new import get_mode_by_key
        
        mode_data = get_mode_by_key(model_key, mode_id)
        if not mode_data:
            logger.warning(f"⚠️ Mode {model_key}:{mode_id} не найден, используем базовую цену")
            return 10.0  # Базовая цена
        
        pricing_unit = mode_data.get("pricing_unit", "per_use")
        input_schema = mode_data.get("input_schema", {})
        properties = input_schema.get("properties", {})
        
        # Базовая цена зависит от pricing_unit
        base_credits = {
            "per_image": 5.0,
            "per_5s": 50.0,
            "per_10s": 100.0,
            "per_minute": 10.0,
            "per_use": 10.0
        }.get(pricing_unit, 10.0)
        
        # Дополнительные наценки за параметры
        additional_credits = 0.0
        
        # Наценка за разрешение
        resolution = params.get("resolution") or params.get("size")
        if resolution:
            if "1080" in str(resolution) or "high" in str(resolution).lower() or "4k" in str(resolution).lower():
                additional_credits += base_credits * 0.3  # +30%
            elif "720" in str(resolution) or "standard" in str(resolution).lower():
                pass  # Базовое разрешение
        
        # Наценка за длительность (для видео)
        duration = params.get("duration") or params.get("n_frames")
        if duration:
            try:
                duration_sec = int(duration)
                if duration_sec > 10:
                    # За каждые дополнительные 5 секунд
                    extra_seconds = duration_sec - 10
                    additional_credits += base_credits * 0.1 * (extra_seconds / 5)  # +10% за каждые 5 сек
            except (ValueError, TypeError):
                pass
        
        # Наценка за количество изображений
        num_images = params.get("num_images") or params.get("variant_count")
        if num_images and isinstance(num_images, (int, str)):
            try:
                num = int(num_images)
                if num > 1:
                    additional_credits += base_credits * (num - 1) * 0.8  # 80% за каждое дополнительное
            except (ValueError, TypeError):
                pass
        
        # Наценка за удаление водяного знака
        if params.get("remove_watermark", False):
            additional_credits += base_credits * 0.5  # +50%
        
        total_credits = base_credits + additional_credits
        
        return total_credits
        
    except Exception as e:
        logger.error(f"❌ Ошибка при расчете кредитов: {e}", exc_info=True)
        return 10.0  # Базовая цена при ошибке


def calculate_price_rub_for_mode(
    model_key: str,
    mode_id: str,
    params: Dict[str, Any],
    credit_rate: Optional[float] = None
) -> float:
    """
    Рассчитывает цену в рублях для модели и mode.
    
    Args:
        model_key: Ключ модели
        mode_id: ID mode
        params: Параметры генерации
        credit_rate: Курс кредита к рублю (опционально)
    
    Returns:
        Цена в рублях
    """
    credits = get_model_credits(model_key, mode_id, params)
    price_rub = calculate_price_rub_from_credits(credits, credit_rate)
    
    logger.debug(f"💰 Расчет цены: {model_key}:{mode_id} = {credits} кредитов = {price_rub} ₽")
    
    return price_rub


def format_price_breakdown(
    model_key: str,
    mode_id: str,
    params: Dict[str, Any],
    user_lang: str = 'ru'
) -> str:
    """
    Форматирует детализацию цены для пользователя.
    
    Args:
        model_key: Ключ модели
        mode_id: ID mode
        params: Параметры генерации
        user_lang: Язык пользователя
    
    Returns:
        Отформатированный текст с детализацией
    """
    try:
        credits = get_model_credits(model_key, mode_id, params)
        price_rub = calculate_price_rub_for_mode(model_key, mode_id, params)
        credit_rate = get_credit_to_rub_rate()
        
        if user_lang == 'ru':
            text = f"💰 <b>Детализация стоимости:</b>\n\n"
            text += f"📊 <b>Кредиты KIE AI:</b> {credits:.2f}\n"
            text += f"💱 <b>Курс:</b> 1 кредит = {credit_rate:.2f} ₽\n"
            text += f"📈 <b>Маржа:</b> x{MARGA_MULTIPLIER}\n"
            text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"💵 <b>Итого:</b> <b>{price_rub:.2f}</b> ₽\n"
        else:
            text = f"💰 <b>Price Breakdown:</b>\n\n"
            text += f"📊 <b>KIE AI Credits:</b> {credits:.2f}\n"
            text += f"💱 <b>Rate:</b> 1 credit = {credit_rate:.2f} ₽\n"
            text += f"📈 <b>Margin:</b> x{MARGA_MULTIPLIER}\n"
            text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"💵 <b>Total:</b> <b>{price_rub:.2f}</b> ₽\n"
        
        return text
        
    except Exception as e:
        logger.error(f"❌ Ошибка при форматировании цены: {e}", exc_info=True)
        return "💰 <b>Стоимость:</b> рассчитывается..."

