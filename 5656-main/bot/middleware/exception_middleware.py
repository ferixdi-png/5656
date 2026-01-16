"""
Exception Middleware - catches unhandled exceptions and ensures user always gets a response.
Fail-safe: never raises new exceptions from within exception handling.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, CallbackQuery, Message
from telegram import Update as LegacyUpdate

logger = logging.getLogger(__name__)


class ExceptionMiddleware(BaseMiddleware):
    """
    Middleware that catches all unhandled exceptions and ensures user gets a response.
    
    Contract:
    - User always gets a friendly message (no stacktrace)
    - All exceptions are logged with full context
    - Never raises new exceptions from within exception handling (fail-safe)
    - Telemetry logging is wrapped in try/except to prevent cascading failures
    """
    
    def __init__(self):
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Wrap handler execution with exception catching.
        
        CRITICAL: This middleware must NEVER throw exceptions.
        All exception handling is wrapped in try/except to prevent cascading failures.
        
        Args:
            handler: Next handler in chain
            event: Telegram event (Update or CallbackQuery)
            data: Handler data
            
        Returns:
            Handler result or None if exception occurred
        """
        try:
            return await handler(event, data)
        except Exception as e:
            # CRITICAL: Extract callback BEFORE any other operations
            # This ensures we can always answer callback even if logging fails
            callback_to_answer = None
            try:
                if isinstance(event, CallbackQuery):
                    callback_to_answer = event
                elif isinstance(event, Update) and event.callback_query:
                    callback_to_answer = event.callback_query
            except Exception:
                pass  # Fail-safe: if extraction fails, continue
            
            # Extract update from event or data (fail-safe)
            update = None
            try:
                update = self._extract_update(event, data)
            except Exception:
                pass  # Fail-safe: continue without update
            
            # ALWAYS answer callback first (prevent infinite spinner)
            if callback_to_answer:
                try:
                    await callback_to_answer.answer("⚠️ Ошибка", show_alert=False)
                except Exception:
                    pass  # Fail-safe: ignore if already answered or fails
            
            # Log error with full context (fail-safe)
            try:
                self._log_exception(e, update, data)
            except Exception as log_err:
                # Fail-safe: if logging fails, at least log to stderr
                try:
                    logger.critical(f"CRITICAL: Exception logging failed: {log_err}", exc_info=True)
                except Exception:
                    pass  # Ultimate fail-safe
            
            # Send user-friendly message (fail-safe)
            try:
                await self._send_error_message(update, e, callback_to_answer)
            except Exception as msg_err:
                # Fail-safe: if sending message fails, log but don't crash
                try:
                    logger.error(f"Failed to send error message to user: {msg_err}", exc_info=True)
                except Exception:
                    pass  # Ultimate fail-safe
            
            # Don't re-raise - we've handled it
            return None
    
    def _extract_update(self, event: TelegramObject, data: Dict[str, Any]) -> Optional[Update]:
        """Extract Update object from event or data."""
        # Try to get from data first (aiogram 3.x style)
        if "event_update" in data:
            return data["event_update"]
        
        # Try event itself if it's an Update
        if isinstance(event, Update):
            return event
        
        # Try legacy Update from data
        if "update" in data and isinstance(data["update"], (Update, LegacyUpdate)):
            return data["update"]
        
        # Try to get from CallbackQuery
        if isinstance(event, CallbackQuery):
            # CallbackQuery doesn't have update_id, but we can get Update from context
            # In aiogram, Update is usually in data
            return None
        
        return None
    
    def _log_exception(
        self,
        exception: Exception,
        update: Optional[Update],
        data: Dict[str, Any]
    ) -> None:
        """
        Log exception with full context.
        Fail-safe: wrapped in try/except to prevent cascading failures.
        """
        try:
            # Extract context info
            update_id = None
            user_id = None
            chat_id = None
            callback_data = None
            message_id = None
            
            if update:
                update_id = getattr(update, 'update_id', None)
                
                if update.message:
                    user_id = update.message.from_user.id if update.message.from_user else None
                    chat_id = update.message.chat_id
                    message_id = update.message.message_id
                elif update.callback_query:
                    callback = update.callback_query
                    user_id = callback.from_user.id if callback.from_user else None
                    chat_id = callback.message.chat_id if callback.message else None
                    message_id = callback.message.message_id if callback.message else None
                    callback_data = callback.data if callback else None
            
            # Log with structured context
            logger.error(
                f"❌ UNHANDLED EXCEPTION: {type(exception).__name__}: {exception}",
                exc_info=exception,
                extra={
                    "update_id": update_id,
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "callback_data": callback_data,
                    "message_id": message_id,
                }
            )
        except Exception as log_err:
            # Fail-safe: if logging fails, at least log basic info
            logger.critical(f"Exception logging failed: {log_err}", exc_info=True)
            logger.error(f"Original exception: {type(exception).__name__}: {exception}")
    
    async def _send_error_message(self, update: Optional[Update], exception: Exception, callback: Optional[CallbackQuery] = None) -> None:
        """
        Send user-friendly error message.
        Fail-safe: wrapped in try/except to prevent cascading failures.
        """
        if not update:
            return
        
        # Determine error type for user-friendly message
        error_msg = str(exception).lower()
        if "timeout" in error_msg:
            user_message = (
                "⏱ <b>Превышено время ожидания</b>\n\n"
                "Сервер слишком долго отвечает. Попробуйте:\n"
                "• Подождать минуту и повторить\n"
                "• Выбрать другую модель\n"
                "• Нажать /start для главного меню"
            )
        elif "network" in error_msg or "connection" in error_msg:
            user_message = (
                "🌐 <b>Проблема с подключением</b>\n\n"
                "Не удалось связаться с сервером.\n\n"
                "Попробуйте через минуту или нажмите /start"
            )
        else:
            user_message = (
                "⚠️ <b>Что-то пошло не так</b>\n\n"
                "Мы уже знаем об этой проблеме и работаем над исправлением.\n\n"
                "💡 Попробуйте:\n"
                "• Повторить действие\n"
                "• Нажать /start для главного меню\n"
                "• Обратиться в поддержку, если проблема повторяется"
            )
        
        # Send message based on update type
        # CRITICAL: callback is already answered in __call__, so we only need to send message
        try:
            if update and update.message:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
                ])
                await update.message.answer(user_message, reply_markup=keyboard, parse_mode="HTML")
            elif callback:
                # Callback already answered in __call__, just send/edit message
                try:
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
                    ])
                    if callback.message:
                        try:
                            await callback.message.edit_text(user_message, reply_markup=keyboard, parse_mode="HTML")
                        except Exception:
                            # If edit fails, try to send new message
                            await callback.message.answer(user_message, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    pass  # Fail-safe: if all fails, just pass
            elif update and update.callback_query:
                # Fallback: if callback wasn't passed but exists in update
                callback = update.callback_query
                try:
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
                    ])
                    if callback.message:
                        try:
                            await callback.message.edit_text(user_message, reply_markup=keyboard, parse_mode="HTML")
                        except Exception:
                            await callback.message.answer(user_message, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    pass  # Fail-safe
        except Exception as send_err:
            # Fail-safe: if sending fails, log but don't crash
            try:
                logger.error(f"Failed to send error message: {send_err}", exc_info=True)
            except Exception:
                pass  # Ultimate fail-safe

