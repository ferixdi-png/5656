"""
BATCH 46: Auto-Diagnostic Logging Integration

Автоматически интегрирует structured logging в существующий код.
Обогащает логи correlation IDs, timing, context.
"""

import logging
import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
import inspect

from app.utils.correlation import get_correlation_id, ensure_correlation_id
from app.logging.structured_logger import StructuredLog

logger = logging.getLogger(__name__)


# ============================================================================
# CONTEXT MANAGERS FOR REQUEST FLOW TRACING
# ============================================================================

class RequestFlowTracer:
    """
    Context manager для трейсинга полного flow запроса.
    
    Usage:
        with RequestFlowTracer("USER_GENERATION", user_id=123, model_id="flux"):
            # ... generation logic ...
            pass
    """
    
    def __init__(self, flow_name: str, **context):
        self.flow_name = flow_name
        self.context = context
        self.start_time = None
        self.correlation_id = None
        
    def __enter__(self):
        self.start_time = time.monotonic()
        self.correlation_id = ensure_correlation_id()
        
        StructuredLog(f"{self.flow_name}_START") \
            .context(correlation_id=self.correlation_id, **self.context) \
            .phase("FLOW_START") \
            .log(logger, level="INFO")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.monotonic() - self.start_time) * 1000 if self.start_time else 0
        
        if exc_type is None:
            # Success
            StructuredLog(f"{self.flow_name}_END") \
                .context(correlation_id=self.correlation_id, **self.context) \
                .phase("FLOW_END") \
                .timing(duration_ms=round(duration_ms, 2)) \
                .result(status="SUCCESS") \
                .log(logger, level="INFO")
        else:
            # Error
            StructuredLog(f"{self.flow_name}_END") \
                .context(correlation_id=self.correlation_id, **self.context) \
                .phase("FLOW_END") \
                .timing(duration_ms=round(duration_ms, 2)) \
                .result(status="ERROR") \
                .error(exception=exc_val) \
                .log(logger, level="ERROR")
        
        return False  # Don't suppress exceptions


# ============================================================================
# ENHANCED DECORATORS
# ============================================================================

def log_handler(handler_type: str = "CALLBACK"):
    """
    Decorator для Telegram handlers с full context.
    
    Usage:
        @log_handler("CALLBACK")
        async def button_callback(callback: CallbackQuery):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.monotonic()
            correlation_id = ensure_correlation_id()
            
            # Extract context from args (Telegram update objects)
            context = _extract_telegram_context(args, kwargs)
            context["correlation_id"] = correlation_id
            
            # Entry log
            StructuredLog(f"HANDLER_{handler_type}") \
                .phase("ENTER", step=func.__name__) \
                .context(**context) \
                .log(logger, level="INFO")
            
            try:
                result = await func(*args, **kwargs)
                
                # Success log
                duration_ms = (time.monotonic() - start_time) * 1000
                StructuredLog(f"HANDLER_{handler_type}") \
                    .phase("EXIT", step=func.__name__) \
                    .context(**context) \
                    .timing(duration_ms=round(duration_ms, 2)) \
                    .result(status="SUCCESS") \
                    .log(logger, level="INFO")
                
                return result
            
            except Exception as e:
                # Error log with full diagnostics
                duration_ms = (time.monotonic() - start_time) * 1000
                StructuredLog(f"HANDLER_{handler_type}") \
                    .phase("EXIT", step=func.__name__) \
                    .context(**context) \
                    .timing(duration_ms=round(duration_ms, 2)) \
                    .result(status="ERROR") \
                    .error(exception=e) \
                    .log(logger, level="ERROR")
                raise
        
        return wrapper
    return decorator


def _extract_telegram_context(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Extract user_id, chat_id, callback_data from Telegram update objects."""
    context = {}
    
    # Try to extract from args
    for arg in args:
        if hasattr(arg, 'from_user') and arg.from_user:
            context['user_id'] = arg.from_user.id
            if hasattr(arg.from_user, 'username') and arg.from_user.username:
                context['username'] = arg.from_user.username
        
        if hasattr(arg, 'message') and arg.message:
            if hasattr(arg.message, 'chat') and arg.message.chat:
                context['chat_id'] = arg.message.chat.id
            if hasattr(arg.message, 'message_id'):
                context['message_id'] = arg.message.message_id
        
        if hasattr(arg, 'chat') and arg.chat:
            context['chat_id'] = arg.chat.id
        
        if hasattr(arg, 'data'):  # CallbackQuery
            context['callback_data'] = arg.data
        
        if hasattr(arg, 'text'):  # Message
            text = arg.text or ""
            context['message_text'] = text[:100]  # Truncate
    
    # Try to extract from kwargs
    for key in ['user_id', 'chat_id', 'model_id', 'callback_data']:
        if key in kwargs:
            context[key] = kwargs[key]
    
    return context


# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================

class PerformanceMonitor:
    """
    Monitors operation performance and logs if it exceeds threshold.
    
    Usage:
        with PerformanceMonitor("DB_QUERY", threshold_ms=100, user_id=123):
            # ... slow query ...
            pass
    """
    
    def __init__(self, operation: str, threshold_ms: float = 1000, **context):
        self.operation = operation
        self.threshold_ms = threshold_ms
        self.context = context
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.monotonic()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.monotonic() - self.start_time) * 1000 if self.start_time else 0
        
        if duration_ms > self.threshold_ms:
            StructuredLog("PERFORMANCE_WARNING") \
                .context(
                    operation=self.operation,
                    threshold_ms=self.threshold_ms,
                    **self.context
                ) \
                .timing(duration_ms=round(duration_ms, 2)) \
                .result(
                    status="SLOW",
                    exceeded_by_ms=round(duration_ms - self.threshold_ms, 2)
                ) \
                .log(logger, level="WARNING")
        
        return False


# ============================================================================
# HEALTH CHECK MARKERS
# ============================================================================

def log_health_marker(component: str, status: str, **details):
    """
    Logs a health check marker for system monitoring.
    
    Usage:
        log_health_marker("DATABASE", "HEALTHY", pool_size=10, active_connections=3)
        log_health_marker("KIE_API", "DEGRADED", last_error="timeout", retry_count=3)
    """
    StructuredLog("HEALTH_CHECK") \
        .context(component=component, health_status=status, **details) \
        .log(logger, level="INFO" if status == "HEALTHY" else "WARNING")


def log_startup_phase(phase: str, **details):
    """
    Logs startup phase completion with details.
    
    Usage:
        log_startup_phase("DB_POOL_CREATED", maxconn=15, hostname="dpg-...")
        log_startup_phase("WEBHOOK_SET", url="https://...")
    """
    StructuredLog("STARTUP") \
        .phase(phase) \
        .context(**details) \
        .log(logger, level="INFO")


# ============================================================================
# ERROR REPORTING WITH AUTO-DIAGNOSIS
# ============================================================================

def log_error_with_diagnosis(
    error_code: str,
    message: str,
    exception: Optional[Exception] = None,
    **context
):
    """
    Logs an error with automatic diagnosis hints.
    
    Usage:
        log_error_with_diagnosis(
            "DB_DNS_RESOLUTION_FAILED",
            "Could not resolve hostname",
            exception=exc,
            hostname="dpg-xxx",
            user_id=123
        )
    """
    StructuredLog("ERROR") \
        .context(**context) \
        .error(code=error_code, message=message, exception=exception) \
        .log(logger, level="ERROR")


# ============================================================================
# REQUEST/RESPONSE LOGGING
# ============================================================================

def log_api_request(
    api_name: str,
    endpoint: str,
    method: str = "POST",
    payload_size: Optional[int] = None,
    **context
):
    """Logs outgoing API request."""
    log_data = StructuredLog(f"API_REQUEST_{api_name}") \
        .context(
            api=api_name,
            endpoint=endpoint,
            method=method,
            **context
        )
    
    if payload_size:
        log_data.context(payload_size_bytes=payload_size)
    
    log_data.log(logger, level="INFO")


def log_api_response(
    api_name: str,
    status_code: int,
    duration_ms: float,
    response_size: Optional[int] = None,
    error: Optional[Exception] = None,
    **context
):
    """Logs API response with timing."""
    log_data = StructuredLog(f"API_RESPONSE_{api_name}") \
        .context(
            api=api_name,
            status_code=status_code,
            **context
        ) \
        .timing(duration_ms=round(duration_ms, 2))
    
    if response_size:
        log_data.context(response_size_bytes=response_size)
    
    if error or status_code >= 400:
        log_data.result(status="FAIL")
        if error:
            log_data.error(exception=error)
        log_data.log(logger, level="ERROR")
    else:
        log_data.result(status="SUCCESS")
        log_data.log(logger, level="INFO")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example 1: Request flow tracing
    with RequestFlowTracer("USER_GENERATION", user_id=123, model_id="flux-pro"):
        time.sleep(0.1)  # Simulate work
    
    # Example 2: Performance monitoring
    with PerformanceMonitor("SLOW_QUERY", threshold_ms=50, user_id=123):
        time.sleep(0.1)  # Simulate slow query
    
    # Example 3: Health check
    log_health_marker("DATABASE", "HEALTHY", pool_size=15, active=3)
    
    # Example 4: Startup phase
    log_startup_phase("WEBHOOK_SET", url="https://example.com/webhook")
    
    # Example 5: Error with diagnosis
    log_error_with_diagnosis(
        "DB_DNS_RESOLUTION_FAILED",
        "Could not resolve hostname",
        hostname="dpg-xxx",
        attempt=3
    )

