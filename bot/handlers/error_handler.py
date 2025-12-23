"""
Global error handler - user-friendly error messages.
"""
from aiogram import Router
from aiogram.types import ErrorEvent, Message, CallbackQuery
from aiogram.exceptions import TelegramAPIError
import logging

logger = logging.getLogger(__name__)

router = Router(name="error_handler")


@router.error()
async def global_error_handler(event: ErrorEvent):
    """Global error handler - always respond to user."""
    exception = event.exception
    update = event.update
    
    # Log error for debugging
    logger.error(f"Error in update {update.update_id}: {exception}", exc_info=exception)
    
    # Determine update type and respond accordingly
    try:
        if update.message:
            message = update.message
            await message.answer(
                "⚠️ Произошла ошибка при обработке сообщения.\n\n"
                "Пожалуйста, попробуйте еще раз или нажмите /start для главного меню."
            )
        elif update.callback_query:
            callback = update.callback_query
            try:
                await callback.answer("⚠️ Произошла ошибка. Попробуйте еще раз.")
            except:
                pass
            try:
                await callback.message.answer(
                    "⚠️ Произошла ошибка.\n\n"
                    "Пожалуйста, нажмите /start для главного меню."
                )
            except:
                pass
        elif update.edited_message:
            message = update.edited_message
            await message.answer(
                "⚠️ Произошла ошибка.\n\n"
                "Пожалуйста, нажмите /start для главного меню."
            )
    except Exception as e:
        # Last resort - log and hope for the best
        logger.critical(f"Failed to send error message to user: {e}")
    
    # Don't re-raise - we've handled it
    return True

