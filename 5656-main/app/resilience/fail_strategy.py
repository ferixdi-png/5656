"""
Fail-open and fail-closed strategies for resilient operations.

FAIL-OPEN: Non-critical operations that can gracefully degrade (stats, analytics, history).
           Show empty state + clear message, but keep UX working.

FAIL-CLOSED: Critical operations that must not simulate success (payments, generations, updates).
             Explicitly fail and provide retry scenario.

Strategy Matrix:
- Read-only stats/analytics → FAIL_OPEN (empty + message)
- Balance checks (for display) → FAIL_OPEN (show "N/A")
- History/logs → FAIL_OPEN (empty + message)
- Payment processing → FAIL_CLOSED (explicit error + retry)
- Generation requests → FAIL_CLOSED (explicit error + retry)
- Update processing → FAIL_CLOSED (explicit error + retry/503)
- Balance deduction → FAIL_CLOSED (explicit error + retry)
"""

import logging
from typing import Callable, Any, Optional, TypeVar, Dict
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


class FailureMode(Enum):
    """Failure mode for operations."""
    FAIL_OPEN = "FAIL_OPEN"    # Degrade gracefully, keep UX working
    FAIL_CLOSED = "FAIL_CLOSED"  # Explicitly fail, require retry


class FailStrategyError(Exception):
    """Base exception for fail strategy errors."""
    pass


class FailOpenError(FailStrategyError):
    """Error for fail-open operations (degraded, but not critical)."""
    pass


class FailClosedError(FailStrategyError):
    """Error for fail-closed operations (critical failure, must retry)."""
    pass


def log_fail_open(
    operation: str,
    error: Exception,
    fallback_value: Any = None,
    cid: Optional[str] = None
) -> None:
    """
    Log FAIL_OPEN event.
    
    Args:
        operation: Operation name
        error: Original exception
        fallback_value: Fallback value returned
        cid: Correlation ID (optional)
    """
    cid_prefix = f"{cid} " if cid else ""
    logger.warning(
        f"{cid_prefix}[FAIL_OPEN] operation={operation} "
        f"error={error.__class__.__name__}: {str(error)[:200]} "
        f"fallback={fallback_value} | "
        f"UX degraded but working"
    )


def log_fail_closed(
    operation: str,
    error: Exception,
    retry_hint: Optional[str] = None,
    cid: Optional[str] = None
) -> None:
    """
    Log FAIL_CLOSED event.
    
    Args:
        operation: Operation name
        error: Original exception
        retry_hint: Hint for retry scenario
        cid: Correlation ID (optional)
    """
    cid_prefix = f"{cid} " if cid else ""
    retry_text = f"retry_hint={retry_hint}" if retry_hint else "retry_required"
    logger.error(
        f"{cid_prefix}[FAIL_CLOSED] operation={operation} "
        f"error={error.__class__.__name__}: {str(error)[:200]} | "
        f"{retry_text} | CRITICAL: operation must not proceed"
    )


def fail_open(
    operation_name: str,
    fallback_value: Any = None,
    user_message: str = "Информация временно недоступна",
    log_cid: bool = True
):
    """
    Decorator for fail-open operations.
    
    If operation fails, return fallback_value and log FAIL_OPEN.
    UX continues working with degraded state.
    
    Args:
        operation_name: Name of the operation
        fallback_value: Value to return on failure
        user_message: Message to show user (optional)
        log_cid: Whether to include correlation ID in logs
    
    Example:
        @fail_open("get_user_stats", fallback_value={})
        async def get_user_stats(user_id: int):
            # ... DB query that might fail
            return stats
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cid = None
            if log_cid:
                try:
                    from app.utils.correlation import get_correlation_id
                    cid = get_correlation_id()
                except:
                    pass
            
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_fail_open(
                    operation=operation_name,
                    error=e,
                    fallback_value=fallback_value,
                    cid=cid
                )
                return fallback_value
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cid = None
            if log_cid:
                try:
                    from app.utils.correlation import get_correlation_id
                    cid = get_correlation_id()
                except:
                    pass
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_fail_open(
                    operation=operation_name,
                    error=e,
                    fallback_value=fallback_value,
                    cid=cid
                )
                return fallback_value
        
        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def fail_closed(
    operation_name: str,
    retry_hint: str = "Повторите попытку через несколько секунд",
    log_cid: bool = True
):
    """
    Decorator for fail-closed operations.
    
    If operation fails, raise FailClosedError and log FAIL_CLOSED.
    Operation must not proceed, explicit error + retry required.
    
    Args:
        operation_name: Name of the operation
        retry_hint: Hint for retry scenario
        log_cid: Whether to include correlation ID in logs
    
    Example:
        @fail_closed("process_payment", retry_hint="Повторите оплату")
        async def process_payment(user_id: int, amount: float):
            # ... payment processing that must not silently fail
            return payment_result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cid = None
            if log_cid:
                try:
                    from app.utils.correlation import get_correlation_id
                    cid = get_correlation_id()
                except:
                    pass
            
            try:
                return await func(*args, **kwargs)
            except FailClosedError:
                # Already a fail-closed error, just re-raise
                raise
            except Exception as e:
                log_fail_closed(
                    operation=operation_name,
                    error=e,
                    retry_hint=retry_hint,
                    cid=cid
                )
                raise FailClosedError(
                    f"Операция '{operation_name}' не может быть выполнена. {retry_hint}"
                ) from e
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cid = None
            if log_cid:
                try:
                    from app.utils.correlation import get_correlation_id
                    cid = get_correlation_id()
                except:
                    pass
            
            try:
                return func(*args, **kwargs)
            except FailClosedError:
                # Already a fail-closed error, just re-raise
                raise
            except Exception as e:
                log_fail_closed(
                    operation=operation_name,
                    error=e,
                    retry_hint=retry_hint,
                    cid=cid
                )
                raise FailClosedError(
                    f"Операция '{operation_name}' не может быть выполнена. {retry_hint}"
                ) from e
        
        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Strategy matrix for common operations
OPERATION_STRATEGY: Dict[str, FailureMode] = {
    # FAIL_OPEN: Read-only, non-critical operations
    "get_user_stats": FailureMode.FAIL_OPEN,
    "get_generation_history": FailureMode.FAIL_OPEN,
    "get_analytics": FailureMode.FAIL_OPEN,
    "get_user_balance_display": FailureMode.FAIL_OPEN,  # For display only
    "get_model_list": FailureMode.FAIL_OPEN,
    "get_recent_actions": FailureMode.FAIL_OPEN,
    "get_system_metrics": FailureMode.FAIL_OPEN,
    
    # FAIL_CLOSED: Critical operations that must not silently fail
    "process_payment": FailureMode.FAIL_CLOSED,
    "deduct_balance": FailureMode.FAIL_CLOSED,
    "create_generation": FailureMode.FAIL_CLOSED,
    "process_telegram_update": FailureMode.FAIL_CLOSED,
    "enqueue_pending_update": FailureMode.FAIL_CLOSED,
    "acquire_singleton_lock": FailureMode.FAIL_CLOSED,
    "apply_referral_bonus": FailureMode.FAIL_CLOSED,
    "refund_payment": FailureMode.FAIL_CLOSED,
}


def get_operation_strategy(operation_name: str) -> FailureMode:
    """
    Get failure mode for operation.
    
    Args:
        operation_name: Name of the operation
    
    Returns:
        FailureMode enum value
    """
    return OPERATION_STRATEGY.get(operation_name, FailureMode.FAIL_CLOSED)


def is_fail_open_operation(operation_name: str) -> bool:
    """Check if operation should fail open."""
    return get_operation_strategy(operation_name) == FailureMode.FAIL_OPEN


def is_fail_closed_operation(operation_name: str) -> bool:
    """Check if operation should fail closed."""
    return get_operation_strategy(operation_name) == FailureMode.FAIL_CLOSED

