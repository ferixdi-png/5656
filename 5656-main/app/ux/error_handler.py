"""
Unified error handling with Russian messages and retry options.
"""
from typing import Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def format_error_message(
    error_code: str,
    error_details: Optional[str] = None,
    model_id: Optional[str] = None,
) -> str:
    """
    Format user-friendly error message in Russian.
    
    Args:
        error_code: Error code (TIMEOUT, INSUFFICIENT_CREDITS, etc.)
        error_details: Optional technical details
        model_id: Optional model ID for context
        
    Returns:
        Formatted error message in Russian
    """
    error_messages = {
        'TIMEOUT': (
            "⏱ <b>Превышено время ожидания</b>\n\n"
            "Генерация заняла слишком много времени. Это может произойти при высокой нагрузке на сервер.\n\n"
            "<b>Что делать?</b>\n"
            "• Попробуйте еще раз через пару минут\n"
            "• Упростите запрос (меньше деталей)\n"
            "• Выберите другую модель\n"
        ),
        'INSUFFICIENT_CREDITS': (
            "💳 <b>Недостаточно средств</b>\n\n"
            "На вашем балансе недостаточно средств для генерации.\n\n"
            "<b>Что делать?</b>\n"
            "• Нажмите «💰 Пополнить баланс»\n"
            "• Или выберите бесплатную модель\n"
        ),
        'INSUFFICIENT_BALANCE': (
            "💳 <b>Недостаточно средств</b>\n\n"
            "На вашем балансе недостаточно средств для генерации.\n\n"
            "<b>Что делать?</b>\n"
            "• Нажмите «💰 Пополнить баланс»\n"
            "• Или выберите бесплатную модель\n"
        ),
        'API_ERROR': (
            "⚠️ <b>Ошибка API</b>\n\n"
            "Возникла проблема при обращении к серверу генерации.\n\n"
            "<b>Что делать?</b>\n"
            "• Попробуйте еще раз через минуту\n"
            "• Если проблема повторяется, напишите в поддержку\n"
        ),
        'VALIDATION_ERROR': (
            "❌ <b>Ошибка в параметрах</b>\n\n"
            "Проверьте введенные данные. Возможно, некоторые параметры указаны неправильно.\n\n"
            "<b>Что делать?</b>\n"
            "• Проверьте формат данных\n"
            "• Убедитесь что все поля заполнены корректно\n"
        ),
        'RATE_LIMIT_EXCEEDED': (
            "⏱ <b>Превышен лимит генераций</b>\n\n"
            "Вы сделали слишком много запросов за короткое время.\n\n"
            "<b>Что делать?</b>\n"
            "• Подождите несколько минут\n"
            "• Затем попробуйте снова\n"
        ),
        'NETWORK_ERROR': (
            "🌐 <b>Ошибка сети</b>\n\n"
            "Не удалось связаться с сервером генерации.\n\n"
            "<b>Что делать?</b>\n"
            "• Проверьте интернет-соединение\n"
            "• Попробуйте еще раз через минуту\n"
        ),
        'INPUT_TOO_LARGE': (
            "📏 <b>Запрос слишком большой</b>\n\n"
            "Размер введенных данных превышает допустимый лимит.\n\n"
            "<b>Что делать?</b>\n"
            "• Сократите текст запроса\n"
            "• Уменьшите размер файла\n"
        ),
    }
    
    base_message = error_messages.get(
        error_code,
        "❌ <b>Произошла ошибка</b>\n\n"
        "К сожалению, что-то пошло не так при обработке вашего запроса.\n\n"
        "<b>Что делать?</b>\n"
        "• Попробуйте еще раз\n"
        "• Если проблема повторяется, напишите в поддержку\n"
    )
    
    # Add model context if provided
    if model_id:
        base_message += f"\n<i>Модель: {model_id}</i>"
    
    # Add technical details if provided (for advanced users/support)
    if error_details:
        base_message += f"\n\n<i>Детали: {error_details}</i>"
    
    return base_message


def build_retry_keyboard(
    model_id: str,
    retry_callback: str = "retry_generation",
    show_balance: bool = False,
    show_free_models: bool = False
) -> InlineKeyboardMarkup:
    """
    Build keyboard with retry and navigation options.
    
    Args:
        model_id: Model ID for retry
        retry_callback: Callback data for retry button
        show_balance: Show balance button (for insufficient funds)
        show_free_models: Show free models button
        
    Returns:
        Inline keyboard with retry options
    """
    buttons = []
    
    # Retry button (if applicable)
    if retry_callback:
        buttons.append([
            InlineKeyboardButton(
                text="🔄 Попробовать снова",
                callback_data=retry_callback
            )
        ])
    
    # Balance button (for payment errors)
    if show_balance:
        buttons.append([
            InlineKeyboardButton(
                text="💰 Пополнить баланс",
                callback_data="menu:payment"
            )
        ])
    
    # Free models button
    if show_free_models:
        buttons.append([
            InlineKeyboardButton(
                text="🆓 Бесплатные модели",
                callback_data="menu:free_models"
            )
        ])
    
    # Navigation buttons (always present)
    buttons.extend([
        [
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="main_menu"
            ),
            InlineKeyboardButton(
                text="📚 Помощь",
                callback_data="menu:help"
            )
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def handle_generation_error(
    result: Dict[str, Any],
    model_id: str
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Handle generation error and return user-friendly message + keyboard.
    
    Args:
        result: Generation result with error info
        model_id: Model ID
        
    Returns:
        Tuple of (message, keyboard)
    """
    error_code = result.get('error_code', 'UNKNOWN')
    error_details = result.get('error_message')
    
    # Format message
    message = format_error_message(
        error_code=error_code,
        error_details=error_details,
        model_id=model_id
    )
    
    # Build keyboard based on error type
    show_balance = error_code in ('INSUFFICIENT_CREDITS', 'INSUFFICIENT_BALANCE')
    show_free_models = show_balance  # Show free models for payment errors
    
    keyboard = build_retry_keyboard(
        model_id=model_id,
        retry_callback="retry_generation" if error_code not in ('RATE_LIMIT_EXCEEDED',) else None,
        show_balance=show_balance,
        show_free_models=show_free_models
    )
    
    return message, keyboard

