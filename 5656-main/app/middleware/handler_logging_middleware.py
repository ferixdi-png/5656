"""
Ultra-explaining handler logging middleware.

Logs HANDLER_ENTER, HANDLER_EXIT, and HANDLER_EXCEPTION for every handler execution.
Provides 1-2 line summary: "what this was / what we expected / what we did / what we returned to user".
"""

import logging
import traceback
from typing import Any, Awaitable, Callable, Dict, Optional
from datetime import datetime

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.utils.correlation import get_correlation_id, ensure_correlation_id
from app.telemetry.telemetry_helpers import get_update_id, get_user_id, get_chat_id
from app.audit.action_logger import log_action
from app.audit.action_logger import log_action

logger = logging.getLogger(__name__)


def _get_handler_name(handler: Callable) -> str:
    """Extract handler name from handler function."""
    if hasattr(handler, "__name__"):
        return handler.__name__
    if hasattr(handler, "__qualname__"):
        return handler.__qualname__
    return str(handler)


async def _get_fsm_state(data: Dict[str, Any]) -> Optional[str]:
    """Get current FSM state from context."""
    try:
        state: FSMContext = data.get("state")
        if state:
            # FSMContext.get_state() is async in aiogram 3.x
            current_state = await state.get_state()
            if current_state:
                return str(current_state)
    except Exception:
        pass
    return None


def _extract_callback_data(event: TelegramObject) -> Optional[str]:
    """Extract callback_data from event."""
    if isinstance(event, CallbackQuery):
        return event.data
    if isinstance(event, Update) and event.callback_query:
        return event.callback_query.data
    return None


def _extract_message_id(event: TelegramObject) -> Optional[int]:
    """Extract message_id from event."""
    if isinstance(event, Message):
        return event.message_id
    if isinstance(event, CallbackQuery) and event.message:
        return event.message.message_id
    if isinstance(event, Update):
        if event.message:
            return event.message.message_id
        if event.callback_query and event.callback_query.message:
            return event.callback_query.message.message_id
    return None


def _get_active_mode(data: Dict[str, Any]) -> str:
    """Get active mode (ACTIVE/PASSIVE) from context."""
    bot_state = data.get("bot_state")
    if bot_state:
        return bot_state
    # Fallback: check runtime_state
    try:
        from app.utils.runtime_state import runtime_state
        return "ACTIVE" if runtime_state.lock_acquired else "PASSIVE"
    except Exception:
        return "UNKNOWN"


def _determine_user_message_key(result: Any, event: TelegramObject) -> Optional[str]:
    """
    Determine user_message_key (short code for what was returned to user).
    
    Returns short codes like:
    - "menu_sent" - menu was sent
    - "error_shown" - error message shown
    - "callback_answered" - callback was answered
    - "message_sent" - message was sent
    - None - no user-facing action
    """
    # This is a heuristic - we can't always know what was sent
    # But we can infer from handler name or result type
    if isinstance(event, CallbackQuery):
        return "callback_answered"
    if isinstance(event, Message):
        return "message_sent"
    return None


class HandlerLoggingMiddleware(BaseMiddleware):
    """
    Ultra-explaining handler logging middleware.
    
    Logs:
    - HANDLER_ENTER: when handler starts
    - HANDLER_EXIT: when handler completes (OK/FAIL_OPEN/ERROR)
    - HANDLER_EXCEPTION: when handler raises exception
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Wrap handler execution with ultra-explaining logs."""
        
        # Ensure correlation ID exists
        cid = data.get("cid") or ensure_correlation_id()
        if not data.get("cid"):
            data["cid"] = cid
        
        # Extract context
        handler_name = _get_handler_name(handler)
        user_id = get_user_id(event)  # P0 FIX: function takes 1 arg, not 2
        chat_id = get_chat_id(event)  # P0 FIX: function takes 1 arg, not 2
        message_id = _extract_message_id(event)
        callback_data = _extract_callback_data(event)
        fsm_state = await _get_fsm_state(data)  # FSM state is async
        active_mode = _get_active_mode(data)
        update_id = get_update_id(event, data)  # OK: function takes 2 args
        
        # HANDLER_ENTER: Log handler start
        logger.info(
            f"[HANDLER_ENTER] cid={cid} handler={handler_name} "
            f"user_id={user_id} chat_id={chat_id} message_id={message_id} "
            f"callback_data={callback_data} fsm_state={fsm_state} active_mode={active_mode} "
            f"update_id={update_id}"
        )
        
        # Execute handler
        result = None
        result_status = "OK"
        user_message_key = None
        exception_info = None
        
        try:
            result = await handler(event, data)
            result_status = "OK"
            user_message_key = _determine_user_message_key(result, event)
            
            # Log action to audit trail (success)
            try:
                action_type = "button_click" if isinstance(event, CallbackQuery) else ("command" if isinstance(event, Message) and event.text and event.text.startswith("/") else "message")
                action_data = callback_data or (event.text if isinstance(event, Message) else str(event)[:200])
                
                log_action(
                    user_id=user_id,
                    chat_id=chat_id,
                    action_type=action_type,
                    action_data=str(action_data)[:200],
                    bot_response=user_message_key or "processed",
                    handler_name=handler_name,
                    success=True
                )
            except Exception as audit_error:
                logger.debug(f"Failed to log action to audit: {audit_error}")
            
        except Exception as exc:
            result_status = "ERROR"
            exception_info = {
                "type": type(exc).__name__,
                "message": str(exc)[:200],  # Truncate long messages
                "traceback": traceback.format_exc()
            }
            
            # HANDLER_EXCEPTION: Log exception with full context
            logger.error(
                f"[HANDLER_EXCEPTION] cid={cid} handler={handler_name} "
                f"user_id={user_id} chat_id={chat_id} update_id={update_id} "
                f"exception={exception_info['type']}: {exception_info['message']}\n"
                f"{exception_info['traceback']}"
            )
            
            # Log action to audit trail (error)
            try:
                action_type = "button_click" if isinstance(event, CallbackQuery) else ("command" if isinstance(event, Message) and event.text and event.text.startswith("/") else "message")
                action_data = callback_data or (event.text if isinstance(event, Message) else str(event)[:200])
                
                log_action(
                    user_id=user_id,
                    chat_id=chat_id,
                    action_type=action_type,
                    action_data=str(action_data)[:200],
                    bot_response=None,
                    handler_name=handler_name,
                    success=False,
                    error=exception_info['message'][:200]
                )
            except Exception as audit_error:
                logger.debug(f"Failed to log action to audit: {audit_error}")
            
            # Re-raise to let ExceptionMiddleware handle it
            raise
        
        finally:
            # HANDLER_EXIT: Log handler completion
            logger.info(
                f"[HANDLER_EXIT] cid={cid} handler={handler_name} "
                f"user_id={user_id} chat_id={chat_id} update_id={update_id} "
                f"result={result_status} user_message_key={user_message_key}"
            )
        
        return result


__all__ = ["HandlerLoggingMiddleware"]

