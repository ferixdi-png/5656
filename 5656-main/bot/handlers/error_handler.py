"""
Global error handler - user-friendly error messages.
Contract: All errors caught, user always gets response with keyboard (no dead ends).
"""
from aiogram import Router
from aiogram.types import ErrorEvent, InlineKeyboardButton, InlineKeyboardMarkup
import logging

logger = logging.getLogger(__name__)

router = Router(name="error_handler")


def _error_fallback_keyboard() -> InlineKeyboardMarkup:
    """Fallback keyboard for error messages - always provide navigation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
            [InlineKeyboardButton(text="❓ Поддержка", callback_data="menu:support")],
        ]
    )


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
    
    # Детальное логирование для диагностики
    user_id = None
    username = None
    error_context = {}
    
    if update.message:
        user_id = update.message.from_user.id
        username = update.message.from_user.username
        error_context = {
            "message_id": update.message.message_id,
            "text": update.message.text[:100] if update.message.text else None,
            "chat_id": update.message.chat.id
        }
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        username = update.callback_query.from_user.username
        error_context = {
            "callback_data": update.callback_query.data,
            "message_id": update.callback_query.message.message_id if update.callback_query.message else None
        }
    
    # Расширенное логирование с контекстом и correlation ID
    from app.utils.correlation import correlation_tag
    cid = correlation_tag()
    
    logger.error(
        f"{cid} 🔴 ERROR | Update {update.update_id} | "
        f"User {user_id} (@{username}) | "
        f"Type: {type(exception).__name__} | "
        f"Message: {str(exception)[:200]} | "
        f"Context: {error_context}",
        exc_info=exception,
        extra={
            "correlation_id": cid,
            "update_id": update.update_id,
            "user_id": user_id,
            "username": username,
            "error_type": type(exception).__name__,
            "context": error_context
        }
    )
    
    # User-friendly error message (no stacktrace)
    # Определяем тип ошибки для более понятного сообщения
    if "timeout" in str(exception).lower():
        error_message = (
            "⏱ <b>Превышено время ожидания</b>\n\n"
            "Сервер слишком долго отвечает. Попробуйте:\n"
            "• Подождать минуту и повторить\n"
            "• Выбрать другую модель\n"
            "• Нажать /start для главного меню"
        )
    elif "network" in str(exception).lower() or "connection" in str(exception).lower():
        error_message = (
            "🌐 <b>Проблема с подключением</b>\n\n"
            "Не удалось связаться с сервером.\n\n"
            "Попробуйте через минуту или нажмите /start"
        )
    else:
        error_message = (
            "⚠️ <b>Произошла ошибка</b>\n\n"
            "Мы уже работаем над исправлением.\n\n"
            "💡 <b>Попробуйте:</b>\n"
            "• Повторить действие\n"
            "• Нажать /start для главного меню\n"
            "• Обратиться в поддержку, если проблема повторяется"
        )
    
    # Always provide keyboard to avoid dead ends
    keyboard = _error_fallback_keyboard()
    
    # Determine update type and respond accordingly (with retry for Telegram API failures)
    import asyncio
    from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
    
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if update.message:
                await update.message.answer(error_message, reply_markup=keyboard)
                break  # Success
            elif update.callback_query:
                callback = update.callback_query
                from app.telemetry.telemetry_helpers import safe_answer_callback
                await safe_answer_callback(
                    callback,
                    text="⚠️ Ошибка",
                    show_alert=False,
                    logger_instance=logger
                )
                await callback.message.answer(error_message, reply_markup=keyboard)
                break  # Success
            elif update.edited_message:
                await update.edited_message.answer(error_message, reply_markup=keyboard)
                break  # Success
        except TelegramRetryAfter as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = e.retry_after
                logger.warning(f"[ERROR_HANDLER] Telegram rate limit hit. Retrying in {delay}s (attempt {attempt+1}/{max_retries})")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[ERROR_HANDLER] Failed to send error message after {max_retries} retries: {e}")
                break
        except TelegramAPIError as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                logger.warning(f"[ERROR_HANDLER] Telegram API error. Retrying in {delay}s (attempt {attempt+1}/{max_retries}): {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[ERROR_HANDLER] Failed to send error message after {max_retries} retries: {e}")
                break
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = (attempt + 1) * 2
                logger.warning(f"[ERROR_HANDLER] Error sending message. Retrying in {delay}s (attempt {attempt+1}/{max_retries}): {e}")
                await asyncio.sleep(delay)
            else:
                logger.critical(f"[ERROR_HANDLER] Failed to send error message after {max_retries} retries: {e}")
                break
    
    if last_error:
        logger.critical(f"[ERROR_HANDLER] Could not deliver error message to user after all retries: {last_error}")
    
    # Don't re-raise - we've handled it
    return True
