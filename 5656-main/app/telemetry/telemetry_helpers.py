"""
Telemetry helper functions for safe attribute access and context extraction.

NOTE: TelemetryMiddleware class is in app/telemetry/middleware.py
Pure utility functions (get_update_id, etc.) are in app/telemetry/utils.py to avoid circular imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    # Type hints only - not evaluated at runtime
    from aiogram.types import CallbackQuery

# CRITICAL: Break circular import - use lazy import for TelemetryMiddleware
# middleware.py imports from telemetry_helpers, so we can't import middleware at module level
def _get_telemetry_middleware():
    """Lazy import of TelemetryMiddleware to break circular dependency."""
    try:
        from app.telemetry.middleware import TelemetryMiddleware
        return TelemetryMiddleware
    except (ImportError, AttributeError):
        # Fail-open: telemetry disabled, app continues without it
        # No scary error messages - just return None silently
        return None

# Re-export utility functions from utils (no circular dependency)
from app.telemetry.utils import (
    get_update_id,
    get_callback_id,
    get_user_id,
    get_chat_id,
    get_message_id,
)

__all__ = [
    # Utility functions (from utils.py, no circular deps)
    "get_update_id",
    "get_callback_id",
    "get_user_id",
    "get_chat_id",
    "get_message_id",
    # Callback safety
    "safe_answer_callback",
    # Middleware (lazy-loaded)
    "TelemetryMiddleware",
    # Backward-compatible stubs (fail-open)
    "log_callback_received",
    "log_callback_routed",
    "log_callback_accepted",
    "log_callback_rejected",
    "log_callback_processed",
    "log_callback_error",
    "log_ui_render",
    "log_event",
]

# Utility functions are imported from utils.py (see imports above)
# This breaks the circular dependency: middleware -> telemetry_helpers -> middleware


async def safe_answer_callback(
    callback: "CallbackQuery",
    text: Optional[str] = None,
    show_alert: bool = False,
    logger_instance: Optional[Any] = None
) -> bool:
    """
    Safely answer a callback query, preventing infinite spinner.
    
    CRITICAL: This function MUST NOT raise exceptions.
    It handles all errors gracefully to prevent "eternal loading" in Telegram.
    
    Args:
        callback: CallbackQuery to answer
        text: Optional text to show (toast or alert)
        show_alert: If True, show as alert popup; if False, show as toast
        logger_instance: Optional logger instance for error logging
        
    Returns:
        True if answered successfully, False otherwise
    """
    import logging
    
    if logger_instance is None:
        logger_instance = logging.getLogger(__name__)
    
    if callback is None:
        logger_instance.debug("[SAFE_ANSWER] Callback is None, skipping")
        return False
    
    try:
        # Try to answer via callback.answer() method (aiogram 3.x)
        if hasattr(callback, 'answer') and callable(callback.answer):
            await callback.answer(text=text, show_alert=show_alert)
            return True
    except Exception as e:
        # Log but don't fail - try alternative method
        logger_instance.debug(f"[SAFE_ANSWER] callback.answer() failed: {e}")
    
    # Fallback: try via bot.answer_callback_query if callback has bot reference
    try:
        if hasattr(callback, 'bot') and callback.bot:
            if hasattr(callback.bot, 'answer_callback_query'):
                await callback.bot.answer_callback_query(
                    callback_query_id=callback.id,
                    text=text,
                    show_alert=show_alert
                )
                return True
    except Exception as e:
        logger_instance.warning(f"[SAFE_ANSWER] bot.answer_callback_query() failed: {e}")
    
    # Ultimate fallback: if callback has id, try direct API call
    try:
        if hasattr(callback, 'id') and callback.id:
            # This is a last resort - we don't have bot instance
            # Log warning but don't crash
            logger_instance.warning(
                f"[SAFE_ANSWER] Could not answer callback {callback.id}: "
                f"no working method available"
            )
    except Exception:
        pass  # Even logging failed, just give up
    
    return False


# --- Backward-compatible callbacks API (fail-open) ---
# These functions are stubs for backward compatibility.
# Old code (e.g., bot/handlers/marketing.py) may import these,
# but they are no-op to allow clean boot even if telemetry is disabled.

def log_callback_received(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible stub: no-op if telemetry unavailable."""
    return None


def log_callback_processed(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible stub: no-op if telemetry unavailable."""
    return None


def log_callback_error(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible stub: no-op if telemetry unavailable."""
    return None


def log_event(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible stub: no-op if telemetry unavailable."""
    return None


def log_callback_routed(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible stub: no-op if telemetry unavailable."""
    return None


def log_callback_accepted(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible stub: no-op if telemetry unavailable."""
    return None


def log_callback_rejected(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible stub: no-op if telemetry unavailable."""
    return None


def log_ui_render(*args: Any, **kwargs: Any) -> None:
    """Backward-compatible stub: no-op if telemetry unavailable."""
    return None


# Make TelemetryMiddleware accessible (lazy-loaded to break circular import)
# This allows: from app.telemetry.telemetry_helpers import TelemetryMiddleware
TelemetryMiddleware = _get_telemetry_middleware()
