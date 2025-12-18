"""
Модуль для пошагового подтверждения стоимости перед генерацией.
"""

import logging
from typing import Dict, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def show_price_confirmation(
    bot,
    chat_id: int,
    model_id: str,
    model_name: str,
    params: Dict[str, Any],
    price: float,
    user_id: int,
    lang: str = 'ru',
    is_free: bool = False,
    bonus_available: float = 0.0,
    discount: Optional[float] = None
) -> Optional[Any]:
    """
    Показывает финальное подтверждение с детализацией цены.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        model_id: ID модели
        model_name: Название модели
        params: Параметры генерации
        price: Итоговая цена
        user_id: ID пользователя
        lang: Язык
        is_free: Бесплатная ли генерация
        bonus_available: Доступные бонусы
        discount: Размер скидки (0.0-1.0)
    
    Returns:
        Сообщение бота или None
    """
    try:
        from pricing_transparency import format_price_breakdown, calculate_detailed_price
        from bonus_system import get_user_bonuses
        
        # Рассчитываем детализированную цену
        # Получаем базовую цену модели (нужно будет интегрировать с KIE API)
        base_price_usd = 0.1  # Пример, нужно получать из API
        price_info = calculate_detailed_price(model_id, params, base_price_usd)
        
        # Применяем скидку, если есть
        final_price = price
        if discount:
            final_price = price * (1 - discount)
            price_info['discount'] = discount
            price_info['discount_amount'] = price * discount
            price_info['total_price'] = final_price
        
        # Применяем бонусы, если доступны
        if bonus_available > 0 and not is_free:
            if bonus_available >= final_price:
                final_price = 0.0
                price_info['bonus_used'] = final_price
                price_info['bonus_remaining'] = bonus_available - final_price
            else:
                final_price = final_price - bonus_available
                price_info['bonus_used'] = bonus_available
                price_info['bonus_remaining'] = 0.0
            price_info['total_price'] = final_price
        
        if is_free:
            final_price = 0.0
            price_info['total_price'] = 0.0
        
        # Форматируем параметры для отображения
        params_text = ""
        for param_name, param_value in params.items():
            if param_name != 'prompt':  # Промпт показываем отдельно
                params_text += f"  • <b>{param_name}:</b> {param_value}\n"
        
        prompt = params.get('prompt', '')
        
        if lang == 'ru':
            message_text = (
                f"📋 <b>Подтверждение генерации</b>\n\n"
                f"🤖 <b>Модель:</b> {model_name}\n"
            )
            
            if prompt:
                prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
                message_text += f"📝 <b>Промпт:</b> {prompt_preview}\n\n"
            
            if params_text:
                message_text += f"⚙️ <b>Параметры:</b>\n{params_text}\n"
            
            message_text += "\n" + format_price_breakdown(price_info, lang)
            
            if is_free:
                message_text += "\n🎁 <b>БЕСПЛАТНАЯ ГЕНЕРАЦИЯ</b> (используется бесплатный лимит)\n"
            elif discount:
                discount_percent = int(discount * 100)
                message_text += f"\n🎫 <b>Применена скидка {discount_percent}%</b>\n"
            elif bonus_available > 0:
                message_text += f"\n🎁 <b>Использовано бонусов:</b> {price_info.get('bonus_used', 0):.2f} ₽\n"
            
            message_text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            message_text += f"💵 <b>К ОПЛАТЕ:</b> <b>{final_price:.2f}</b> ₽\n"
            
            # Получаем баланс пользователя
            try:
                from bot_kie import get_user_balance
                user_balance = get_user_balance(user_id)
                message_text += f"💳 <b>Ваш баланс:</b> {user_balance:.2f} ₽\n"
                
                if user_balance < final_price and not is_free:
                    message_text += f"\n⚠️ <b>Недостаточно средств!</b>\n"
                    message_text += f"Пополните баланс или используйте бонусы.\n"
            except:
                pass
            
            buttons = [
                [InlineKeyboardButton("✅ Подтвердить и начать", callback_data="confirm_generate")],
                [InlineKeyboardButton("✏️ Изменить параметры", callback_data="back_to_previous_step")],
                [InlineKeyboardButton("🏠 В главное меню", callback_data="back_to_menu")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
            ]
        else:
            message_text = (
                f"📋 <b>Generation Confirmation</b>\n\n"
                f"🤖 <b>Model:</b> {model_name}\n"
            )
            
            if prompt:
                prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
                message_text += f"📝 <b>Prompt:</b> {prompt_preview}\n\n"
            
            if params_text:
                message_text += f"⚙️ <b>Parameters:</b>\n{params_text}\n"
            
            message_text += "\n" + format_price_breakdown(price_info, lang)
            
            if is_free:
                message_text += "\n🎁 <b>FREE GENERATION</b> (using free limit)\n"
            elif discount:
                discount_percent = int(discount * 100)
                message_text += f"\n🎫 <b>Discount {discount_percent}% applied</b>\n"
            elif bonus_available > 0:
                message_text += f"\n🎁 <b>Bonuses used:</b> {price_info.get('bonus_used', 0):.2f} ₽\n"
            
            message_text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            message_text += f"💵 <b>TO PAY:</b> <b>{final_price:.2f}</b> ₽\n"
            
            buttons = [
                [InlineKeyboardButton("✅ Confirm and Start", callback_data="confirm_generate")],
                [InlineKeyboardButton("✏️ Change Parameters", callback_data="back_to_previous_step")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_menu")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
        
        return await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при показе подтверждения цены: {e}", exc_info=True)
        return None


def update_price_on_parameter_change(
    model_id: str,
    current_params: Dict[str, Any],
    changed_param: str,
    new_value: Any
) -> Dict[str, Any]:
    """
    Обновляет цену при изменении параметра.
    
    Args:
        model_id: ID модели
        current_params: Текущие параметры
        changed_param: Измененный параметр
        new_value: Новое значение
    
    Returns:
        Обновленная информация о цене
    """
    # Обновляем параметры
    updated_params = current_params.copy()
    updated_params[changed_param] = new_value
    
    # Пересчитываем цену
    from pricing_transparency import calculate_detailed_price
    base_price_usd = 0.1  # Пример, нужно получать из API
    price_info = calculate_detailed_price(model_id, updated_params, base_price_usd)
    
    return price_info

