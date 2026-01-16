"""
Telemetry Middleware for aiogram - adds correlation ID and bot state to all updates.

CRITICAL: This middleware must be fail-safe - if telemetry fails, app should still work.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware

if TYPE_CHECKING:
    # Type hints only - not evaluated at runtime
    from aiogram.types import TelegramObject, Update
else:
    # Runtime imports for isinstance checks
    from aiogram.types import TelegramObject, Update

from app.telemetry.events import generate_cid, log_update_received
# Break circular import: import from utils instead of telemetry_helpers
from app.telemetry.utils import get_update_id, get_user_id, get_chat_id
from app.utils.runtime_state import runtime_state

logger = logging.getLogger(__name__)


class TelemetryMiddleware(BaseMiddleware):
    """
    Middleware that adds correlation ID (cid) and bot state to all updates.
    
    CRITICAL: Fail-safe - if telemetry logging fails, app continues normally.
    """
    
    async def __call__(
        self,
        handler: Callable[["TelegramObject", Dict[str, Any]], Awaitable[Any]],
        event: "TelegramObject",
        data: Dict[str, Any],
    ) -> Any:
        """
        Process update: add cid and bot_state, log UPDATE_RECEIVED.
        
        Fail-safe: any telemetry errors are logged but don't break the flow.
        """
        # Generate correlation ID
        cid = generate_cid()
        
        # Add cid to data context (available to all handlers)
        data["cid"] = cid
        
        # Add bot state (ACTIVE/PASSIVE)
        data["bot_state"] = "ACTIVE" if runtime_state.lock_acquired else "PASSIVE"
        
        # Extract context safely
        try:
            update_id = get_update_id(event, data)
            user_id = get_user_id(event)
            chat_id = get_chat_id(event)
        except Exception as e:
            logger.debug(f"Failed to extract telemetry context: {e}")
            update_id = None
            user_id = None
            chat_id = None
        
        # Log UPDATE_RECEIVED (fail-safe: don't break if logging fails)
        try:
            log_update_received(
                update_id=update_id,
                user_id=user_id,
                chat_id=chat_id,
                cid=cid,
                bot_state=data["bot_state"]
            )
        except Exception as e:
            logger.warning(f"Telemetry logging failed (non-critical): {e}")
        
        # AUTOMATIC CALLBACK TRACING: Log BUTTON_RECEIVED for CallbackQuery
        callback_data = None
        try:
            if hasattr(event, 'data') and event.data:
                # This is a CallbackQuery
                callback_data = event.data
                from app.observability.button_trace import log_button_received
                log_button_received(
                    cid=cid,
                    callback_data=callback_data,
                    update_id=update_id,
                    user_id=user_id,
                )
        except Exception as e:
            logger.debug(f"Failed to log BUTTON_RECEIVED (non-critical): {e}")
        
        # Continue to handler
        try:
            result = await handler(event, data)
            
            # AUTOMATIC UI_RENDER: Log UI_RENDER after handler returns (for callbacks)
            if callback_data:
                try:
                    from app.observability.button_trace import log_ui_render
                    # Try to extract screen_id from result or handler name
                    handler_name = handler.__name__ if hasattr(handler, '__name__') else "unknown"
                    log_ui_render(
                        cid=cid,
                        screen_id=handler_name,
                        user_id=user_id,
                        reason="handler_completed"
                    )
                except Exception as e:
                    logger.debug(f"Failed to log UI_RENDER (non-critical): {e}")
            
            # Log DISPATCH_OK (fail-safe)
            try:
                from app.telemetry.events import log_dispatch_ok
                log_dispatch_ok(cid=cid)
            except Exception as e:
                logger.debug(f"Failed to log DISPATCH_OK: {e}")
            
            return result
            
        except Exception as e:
            # Log DISPATCH_FAIL (fail-safe)
            # Note: log_dispatch_fail may not exist, use log_callback_rejected as fallback
            try:
                from app.telemetry.events import log_dispatch_ok, log_callback_rejected
                from app.telemetry.logging_contract import ReasonCode
                # Try to log as dispatch fail, fallback to callback_rejected
                try:
                    if hasattr(log_callback_rejected, '__call__'):
                        log_callback_rejected(
                            cid=cid,
                            reason_code=ReasonCode.INTERNAL_ERROR,
                            reason_detail=f"{type(e).__name__}: {str(e)[:200]}"
                        )
                except Exception:
                    pass  # Even logging failed, continue
            except Exception as log_err:
                logger.debug(f"Failed to log dispatch failure: {log_err}")
            
            # Re-raise to let exception middleware handle it
            raise

