"""
Global error handler - user-friendly error messages.
Contract: All errors caught, user always gets response.
"""
from aiogram import Router
from aiogram.types import ErrorEvent
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import logging

logger = logging.getLogger(__name__)

router = Router(name="error_handler")


@router.error()
async def global_error_handler(event: ErrorEvent):
    """
    Global error handler - always respond to user.
    
    Contract:
    - User gets friendly message (no stacktrace)
    - Suggests /start as next step
    - Never silent
    """
    exception = event.exception
    update = event.update
    
    # Log error for debugging (with full stacktrace)
    logger.error(f"Error in update {update.update_id}: {exception}", exc_info=exception)
    
    # User-friendly error message (no stacktrace)
    error_message = (
        "❌ Ошибка. Средства не списаны.\n\n"
        "Попробуйте еще раз или нажмите /start для главного меню."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")]]
    )
    
    # Determine update type and respond accordingly
    try:
        if update.message:
            await update.message.answer(error_message, reply_markup=keyboard)
        elif update.callback_query:
            callback = update.callback_query
            await callback.answer("⚠️ Ошибка")
            try:
                await callback.message.answer(error_message, reply_markup=keyboard)
            except:
                # If edit fails, try to send new message
                try:
                    await callback.message.answer(error_message, reply_markup=keyboard)
                except:
                    pass
        elif update.edited_message:
            await update.edited_message.answer(error_message, reply_markup=keyboard)
    except Exception as e:
        # Last resort - log but don't crash
        logger.critical(f"Failed to send error message to user: {e}")
    
    # Don't re-raise - we've handled it
    return True
