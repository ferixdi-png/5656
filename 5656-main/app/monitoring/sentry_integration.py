"""
Optional Sentry integration for production error monitoring.

Usage:
  Set SENTRY_DSN environment variable to enable.
  Example: https://key@sentry.io/project_id

Features:
  - Automatic error capture
  - Performance monitoring
  - Release tracking
  - User session tracking
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """
    Initialize Sentry error tracking (optional).

    Returns:
        True if Sentry initialized, False if disabled
    """
    sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
    if not sentry_dsn:
        logger.info("[MONITORING] Sentry disabled (SENTRY_DSN not set)")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.asyncio import AsyncioIntegration

        # Setup Sentry
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=0.1,  # 10% of transactions
            profiles_sample_rate=0.1,  # 10% of transactions with profiling
            integrations=[
                LoggingIntegration(
                    level=logging.INFO,  # Capture INFO and above as breadcrumbs
                    event_level=logging.ERROR  # Send ERROR and above as events
                ),
                AsyncioIntegration(),
            ],
            environment=os.getenv("APP_ENV", "production"),
            release=os.getenv("APP_VERSION", "unknown"),
            include_local_variables=True,  # Include local variables in errors (production caution!)
        )

        logger.info("[MONITORING] Sentry initialized successfully")
        return True

    except ImportError:
        logger.warning("[MONITORING] sentry-sdk not installed. Install with: pip install sentry-sdk")
        return False
    except Exception as e:
        logger.error(f"[MONITORING] Failed to initialize Sentry: {e}")
        return False


def capture_exception(exc: Exception, context: Optional[dict] = None) -> None:
    """
    Capture exception in Sentry.

    Args:
        exc: Exception to capture
        context: Optional context dict (user_id, model_id, etc)
    """
    try:
        import sentry_sdk

        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_context(key, {"value": str(value)})
                sentry_sdk.capture_exception(exc)
        else:
            sentry_sdk.capture_exception(exc)

    except Exception as e:
        logger.warning(f"[MONITORING] Failed to send to Sentry: {e}")


def set_user_context(user_id: int, username: Optional[str] = None) -> None:
    """
    Set user context for Sentry.

    Args:
        user_id: User Telegram ID
        username: Optional username
    """
    try:
        import sentry_sdk

        sentry_sdk.set_user({
            "id": user_id,
            "username": username,
        })
    except Exception as e:
        logger.debug(f"[MONITORING] Failed to set user context: {e}")


def add_breadcrumb(message: str, category: str = "info", level: str = "info") -> None:
    """
    Add breadcrumb for Sentry.

    Args:
        message: Breadcrumb message
        category: Breadcrumb category (e.g., "payment", "generation")
        level: Severity level (debug, info, warning, error)
    """
    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level
        )
    except Exception as e:
        logger.debug(f"[MONITORING] Failed to add breadcrumb: {e}")


# Example usage patterns:
"""
# In main.py
from app.monitoring.sentry_integration import init_sentry

async def main():
    sentry_enabled = init_sentry()
    # ... rest of code
    
# In error handlers
from app.monitoring.sentry_integration import capture_exception, set_user_context

try:
    # ... code
except Exception as e:
    set_user_context(user_id, username)
    capture_exception(e, context={
        "user_id": user_id,
        "model_id": model_id,
        "step": "generation"
    })
    
# In handlers
from app.monitoring.sentry_integration import add_breadcrumb

async def handler(message: Message):
    add_breadcrumb("User started generation", category="generation")
    # ... code
"""
