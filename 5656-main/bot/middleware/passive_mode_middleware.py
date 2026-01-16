"""
PASSIVE Mode UX Middleware - ensures user always gets feedback during deploy overlap.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


class PassiveModeMiddleware(BaseMiddleware):
    """
    Middleware that intercepts updates when bot is in PASSIVE mode and provides UX feedback.
    
    Contract:
    - Always answer callback queries immediately (no spinner)
    - Send user-friendly message explaining maintenance
    - Provide refresh button for callbacks
    - Never silently drop updates
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
        Check if bot is PASSIVE and handle accordingly.
        
        Args:
            handler: Next handler in chain
            event: Telegram event
            data: Handler data
            
        Returns:
            Handler result or None if PASSIVE mode handled
        """
        # Check if bot is in PASSIVE mode
        is_passive = await self._is_passive_mode(data)
        
        if not is_passive:
            # ACTIVE mode - proceed normally
            return await handler(event, data)
        
        # PASSIVE mode - provide UX feedback
        try:
            if isinstance(event, CallbackQuery):
                await self._handle_passive_callback(event, data)
            elif isinstance(event, Message):
                await self._handle_passive_message(event, data)
            elif isinstance(event, Update):
                # Extract callback or message from update
                if event.callback_query:
                    await self._handle_passive_callback(event.callback_query, data)
                elif event.message:
                    await self._handle_passive_message(event.message, data)
            
            # Log PASSIVE rejection with telemetry
            from app.telemetry import log_callback_rejected, generate_cid, get_callback_id
            cid = generate_cid()
            callback_id = get_callback_id(event) if isinstance(event, CallbackQuery) else None
            callback_data = event.data if isinstance(event, CallbackQuery) else None
            
            log_callback_rejected(
                callback_data=callback_data,
                reason_code="PASSIVE_REJECT",
                reason_detail="Bot is in PASSIVE mode during deploy overlap",
                cid=cid
            )
            
            # Don't call handler - we've handled it
            return None
        except Exception as e:
            # Fail-safe: if PASSIVE handling fails, log and proceed (better than silent failure)
            logger.error(f"Failed to handle PASSIVE mode: {e}", exc_info=True)
            # Still try to proceed - better than silent failure
            return await handler(event, data)
    
    async def _is_passive_mode(self, data: Dict[str, Any]) -> bool:
        """
        Check if bot is in PASSIVE mode.
        
        Args:
            data: Handler data
            
        Returns:
            True if PASSIVE, False if ACTIVE
        """
        try:
            # Try to get active_state from data or application
            active_state = data.get("active_state")
            if active_state:
                # Check if active_state has 'active' attribute
                if hasattr(active_state, 'active'):
                    return not active_state.active
            
            # Try to get from application bot_data
            application = data.get("application")
            if application and hasattr(application, 'bot_data'):
                active_state = application.bot_data.get("active_state")
                if active_state and hasattr(active_state, 'active'):
                    return not active_state.active
            
            # Default to ACTIVE if we can't determine
            return False
        except Exception as e:
            logger.debug(f"Could not determine PASSIVE mode: {e}")
            return False
    
    async def _handle_passive_callback(self, callback: CallbackQuery, data: Dict[str, Any]) -> None:
        """
        Handle callback query in PASSIVE mode.
        
        CRITICAL: Always answer callback to prevent infinite spinner.
        Always send/edit message with refresh button.
        
        Args:
            callback: CallbackQuery event
            data: Handler data
        """
        try:
            # CRITICAL: Always answer callback immediately (no infinite spinner)
            from app.telemetry.telemetry_helpers import safe_answer_callback
            await safe_answer_callback(
                callback,
                text="⏳ Сервис обновляется, повтори через пару секунд",
                show_alert=False,
                logger_instance=logger
            )
            
            # Send user-friendly message with refresh button
            refresh_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="main_menu")]
            ])
            
            message_text = (
                "⏳ <b>Сервис обновляется</b>\n\n"
                "Идёт перезапуск. Повторите через 10–30 секунд.\n\n"
                "Нажмите 'Обновить' для повторной попытки."
            )
            
            if callback.message:
                try:
                    await callback.message.edit_text(
                        message_text,
                        reply_markup=refresh_keyboard,
                        parse_mode="HTML"
                    )
                except Exception:
                    # If edit fails, try to send new message
                    try:
                        await callback.message.answer(
                            message_text,
                            reply_markup=refresh_keyboard,
                            parse_mode="HTML"
                        )
                    except Exception as msg_err:
                        logger.error(f"Failed to send PASSIVE message: {msg_err}", exc_info=True)
        except Exception as e:
            # Ultimate fail-safe: log error but don't crash
            logger.error(f"Failed to handle PASSIVE callback: {e}", exc_info=True)
            # Try one more time to at least answer the callback
            from app.telemetry.telemetry_helpers import safe_answer_callback
            await safe_answer_callback(
                callback,
                text="⏳ Сервис обновляется",
                show_alert=False,
                logger_instance=logger
            )
    
    async def _handle_passive_message(self, message: Message, data: Dict[str, Any]) -> None:
        """
        Handle message in PASSIVE mode.
        
        Args:
            message: Message event
            data: Handler data
        """
        try:
            message_text = (
                "⏳ <b>Сервис обновляется</b>\n\n"
                "Идёт перезапуск. Попробуйте через 10–30 секунд.\n\n"
                "Используйте /start для главного меню."
            )
            
            await message.answer(message_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to handle PASSIVE message: {e}", exc_info=True)

