"""
BATCH 46: Ultra-Diagnostic Structured Logging System

Цель: Логи настолько информативные, что AI может мгновенно диагностировать
и исправить проблемы просто прочитав их.

Каждый лог содержит:
- Категория операции (DB, API, PAYMENT, MODEL, UX, etc.)
- Correlation ID для трейсинга
- Контекст (user_id, model_id, chat_id)
- Timing metrics (duration, latency)
- Error codes + fix hints
- Source location (file:line:func)
"""

import logging
import time
import traceback
from typing import Optional, Dict, Any
from functools import wraps
import inspect
import os

logger = logging.getLogger(__name__)


# ============================================================================
# ERROR CATEGORIES & FIX HINTS
# ============================================================================

ERROR_CATALOG: Dict[str, Dict[str, str]] = {
    # DATABASE ERRORS
    "DB_CONNECTION_FAILED": {
        "category": "DATABASE",
        "severity": "CRITICAL",
        "fix_hint": "Check DATABASE_URL in Render Environment Variables",
        "check": ["DATABASE_URL env var", "PostgreSQL status in Render Dashboard", "Network connectivity"],
        "docs": "docs/RENDER_DATABASE_DNS_FIX.md"
    },
    "DB_DNS_RESOLUTION_FAILED": {
        "category": "DATABASE",
        "severity": "CRITICAL",
        "fix_hint": "Database hostname cannot be resolved - check DATABASE_URL",
        "check": ["Render Dashboard → Databases → verify hostname", "DATABASE_URL matches actual DB hostname"],
        "docs": "docs/RENDER_DATABASE_DNS_FIX.md"
    },
    "DB_QUERY_TIMEOUT": {
        "category": "DATABASE",
        "severity": "HIGH",
        "fix_hint": "Query took too long - check indexes or increase statement_timeout",
        "check": ["DB_STATEMENT_TIMEOUT_MS env var", "Query performance (EXPLAIN ANALYZE)", "Missing indexes"],
        "docs": None
    },
    "DB_POOL_EXHAUSTED": {
        "category": "DATABASE",
        "severity": "HIGH",
        "fix_hint": "No available connections in pool - increase DB_MAXCONN",
        "check": ["DB_MAXCONN env var (current value)", "Connection leaks (not released)", "Traffic spike"],
        "docs": None
    },
    
    # KIE API ERRORS
    "KIE_API_TIMEOUT": {
        "category": "KIE_API",
        "severity": "HIGH",
        "fix_hint": "KIE API did not respond in time - check model category timeout",
        "check": ["Model category (photo/video/audio)", "Timeout value (90s/300s/180s)", "KIE API status"],
        "docs": None
    },
    "KIE_API_RATE_LIMIT": {
        "category": "KIE_API",
        "severity": "MEDIUM",
        "fix_hint": "KIE API rate limit exceeded - implement exponential backoff",
        "check": ["Rate limit headers", "Request frequency", "Retry-After value"],
        "docs": None
    },
    "KIE_INVALID_PARAMS": {
        "category": "KIE_API",
        "severity": "HIGH",
        "fix_hint": "KIE API rejected parameters - check input_schema vs payload",
        "check": ["Model input_schema", "Payload builder output", "Required vs optional fields"],
        "docs": None
    },
    
    # PAYMENT ERRORS
    "PAYMENT_INSUFFICIENT_BALANCE": {
        "category": "PAYMENT",
        "severity": "LOW",
        "fix_hint": "User has insufficient balance - show topup prompt",
        "check": ["User balance", "Model price", "Transaction history"],
        "docs": None
    },
    "PAYMENT_DUPLICATE_CHARGE": {
        "category": "PAYMENT",
        "severity": "CRITICAL",
        "fix_hint": "Idempotency key collision - check charge_task_id uniqueness",
        "check": ["Idempotency key generation", "Duplicate detection logic", "Transaction logs"],
        "docs": None
    },
    
    # UX ERRORS
    "UX_HANDLER_NOT_FOUND": {
        "category": "UX",
        "severity": "HIGH",
        "fix_hint": "No handler registered for callback_data - check router registration",
        "check": ["callback_data pattern", "Handler registration in router", "Button map generator output"],
        "docs": None
    },
    "UX_FSM_STATE_MISMATCH": {
        "category": "UX",
        "severity": "MEDIUM",
        "fix_hint": "FSM state does not match expected - check state transitions",
        "check": ["Current FSM state", "Expected state", "State cleanup logic"],
        "docs": None
    },
    
    # TELEGRAM API ERRORS
    "TG_API_TIMEOUT": {
        "category": "TELEGRAM",
        "severity": "MEDIUM",
        "fix_hint": "Telegram API timeout - retry with exponential backoff",
        "check": ["Telegram API status", "Network latency", "Message size (too large?)"],
        "docs": None
    },
    "TG_MESSAGE_TOO_LONG": {
        "category": "TELEGRAM",
        "severity": "LOW",
        "fix_hint": "Message exceeds Telegram limit (4096 chars) - split or truncate",
        "check": ["Message length", "Split logic", "Truncation strategy"],
        "docs": None
    },
}


# ============================================================================
# STRUCTURED LOG BUILDER
# ============================================================================

class StructuredLog:
    """
    Builder for structured log entries.
    
    Usage:
        StructuredLog("DB_QUERY") \\
            .context(user_id=123, model_id="flux") \\
            .timing(duration_ms=45.2) \\
            .error(code="DB_TIMEOUT", message="Query timeout") \\
            .log(logger, level="ERROR")
    """
    
    def __init__(self, operation: str):
        self.operation = operation
        self.data: Dict[str, Any] = {"operation": operation}
        self._caller_info = self._get_caller_info()
        
    def _get_caller_info(self) -> Dict[str, str]:
        """Get caller file, line, and function name."""
        frame = inspect.currentframe()
        if frame is None:
            return {}
        
        # Go up the stack to find the actual caller (skip StructuredLog internals)
        caller_frame = frame.f_back.f_back if frame.f_back else None
        if caller_frame is None:
            return {}
        
        filename = caller_frame.f_code.co_filename
        # Make path relative to project root
        try:
            filename = os.path.relpath(filename)
        except ValueError:
            pass
        
        return {
            "file": filename,
            "line": caller_frame.f_lineno,
            "func": caller_frame.f_code.co_name
        }
    
    def context(self, **kwargs) -> 'StructuredLog':
        """Add context fields (user_id, model_id, chat_id, etc.)."""
        self.data.update(kwargs)
        return self
    
    def timing(self, **kwargs) -> 'StructuredLog':
        """Add timing fields (duration_ms, latency_ms, etc.)."""
        self.data.update(kwargs)
        return self
    
    def error(self, code: Optional[str] = None, message: Optional[str] = None, 
              exception: Optional[Exception] = None) -> 'StructuredLog':
        """Add error information."""
        if code:
            self.data["error_code"] = code
            # Add fix hints from catalog
            if code in ERROR_CATALOG:
                catalog_entry = ERROR_CATALOG[code]
                self.data["error_category"] = catalog_entry["category"]
                self.data["error_severity"] = catalog_entry["severity"]
                self.data["fix_hint"] = catalog_entry["fix_hint"]
                self.data["check_list"] = " | ".join(catalog_entry["check"])
                if catalog_entry["docs"]:
                    self.data["docs"] = catalog_entry["docs"]
        
        if message:
            self.data["error_message"] = message
        
        if exception:
            self.data["exception_type"] = type(exception).__name__
            self.data["exception_str"] = str(exception)
            # Only include traceback for truly unexpected errors
            if not code or code.startswith("UNKNOWN"):
                self.data["traceback"] = "".join(traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                ))
        
        return self
    
    def phase(self, phase: str, step: Optional[str] = None) -> 'StructuredLog':
        """Add phase/step information (e.g., phase=PAYMENT step=HOLD)."""
        self.data["phase"] = phase
        if step:
            self.data["step"] = step
        return self
    
    def result(self, status: str, **kwargs) -> 'StructuredLog':
        """Add result information (status=SUCCESS/FAIL/TIMEOUT, etc.)."""
        self.data["status"] = status
        self.data.update(kwargs)
        return self
    
    def log(self, logger_obj: logging.Logger, level: str = "INFO") -> None:
        """Write the structured log entry."""
        # Add caller info
        self.data.update(self._caller_info)
        
        # Format as key=value pairs for easy parsing
        parts = []
        for key, value in self.data.items():
            if isinstance(value, str) and (" " in value or "=" in value):
                # Quote strings with spaces or equals signs
                parts.append(f'{key}="{value}"')
            else:
                parts.append(f"{key}={value}")
        
        log_line = " ".join(parts)
        
        # Prefix with operation in brackets for easy filtering
        log_line = f"[{self.operation}] {log_line}"
        
        # Log at appropriate level
        log_func = getattr(logger_obj, level.lower(), logger_obj.info)
        log_func(log_line)


# ============================================================================
# DECORATORS FOR AUTO-LOGGING
# ============================================================================

def log_operation(operation_name: str, capture_args: bool = False):
    """
    Decorator to automatically log function entry/exit with timing.
    
    Usage:
        @log_operation("DB_QUERY", capture_args=True)
        async def get_user(user_id: int):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.monotonic()
            
            # Entry log
            entry_log = StructuredLog(operation_name).phase("ENTER")
            if capture_args:
                entry_log.context(args=str(args)[:200], kwargs=str(kwargs)[:200])
            entry_log.log(logger, level="DEBUG")
            
            try:
                result = await func(*args, **kwargs)
                
                # Success log
                duration_ms = (time.monotonic() - start_time) * 1000
                StructuredLog(operation_name) \
                    .phase("EXIT") \
                    .timing(duration_ms=round(duration_ms, 2)) \
                    .result(status="SUCCESS") \
                    .log(logger, level="INFO")
                
                return result
            
            except Exception as e:
                # Error log
                duration_ms = (time.monotonic() - start_time) * 1000
                StructuredLog(operation_name) \
                    .phase("EXIT") \
                    .timing(duration_ms=round(duration_ms, 2)) \
                    .result(status="FAIL") \
                    .error(exception=e) \
                    .log(logger, level="ERROR")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.monotonic()
            
            # Entry log
            entry_log = StructuredLog(operation_name).phase("ENTER")
            if capture_args:
                entry_log.context(args=str(args)[:200], kwargs=str(kwargs)[:200])
            entry_log.log(logger, level="DEBUG")
            
            try:
                result = func(*args, **kwargs)
                
                # Success log
                duration_ms = (time.monotonic() - start_time) * 1000
                StructuredLog(operation_name) \
                    .phase("EXIT") \
                    .timing(duration_ms=round(duration_ms, 2)) \
                    .result(status="SUCCESS") \
                    .log(logger, level="INFO")
                
                return result
            
            except Exception as e:
                # Error log
                duration_ms = (time.monotonic() - start_time) * 1000
                StructuredLog(operation_name) \
                    .phase("EXIT") \
                    .timing(duration_ms=round(duration_ms, 2)) \
                    .result(status="FAIL") \
                    .error(exception=e) \
                    .log(logger, level="ERROR")
                raise
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_db_operation(operation: str, duration_ms: float, query: Optional[str] = None,
                     error: Optional[Exception] = None, **context):
    """Quick helper for database operation logging."""
    log_builder = StructuredLog("DB_OPERATION") \
        .context(db_operation=operation, **context) \
        .timing(duration_ms=round(duration_ms, 2))
    
    if query:
        # Truncate long queries
        log_builder.context(query=query[:200] + ("..." if len(query) > 200 else ""))
    
    if error:
        log_builder.error(
            code="DB_QUERY_FAILED",
            message=str(error),
            exception=error
        )
        log_builder.log(logger, level="ERROR")
    else:
        log_builder.result(status="SUCCESS")
        log_builder.log(logger, level="INFO")


def log_kie_request(model_id: str, duration_ms: float, payload_size: int,
                    status_code: Optional[int] = None, error: Optional[Exception] = None,
                    **context):
    """Quick helper for KIE API request logging."""
    log_builder = StructuredLog("KIE_API_REQUEST") \
        .context(model_id=model_id, payload_size_bytes=payload_size, **context) \
        .timing(duration_ms=round(duration_ms, 2))
    
    if error:
        # Determine error code
        error_code = "KIE_API_UNKNOWN_ERROR"
        if "timeout" in str(error).lower():
            error_code = "KIE_API_TIMEOUT"
        elif "rate" in str(error).lower() and "limit" in str(error).lower():
            error_code = "KIE_API_RATE_LIMIT"
        elif "invalid" in str(error).lower() or "parameter" in str(error).lower():
            error_code = "KIE_INVALID_PARAMS"
        
        log_builder.error(code=error_code, exception=error)
        log_builder.log(logger, level="ERROR")
    else:
        log_builder.result(status="SUCCESS", status_code=status_code or 200)
        log_builder.log(logger, level="INFO")


def log_payment_operation(operation: str, user_id: int, amount: float, charge_task_id: str,
                          error: Optional[Exception] = None, **context):
    """Quick helper for payment operation logging."""
    log_builder = StructuredLog("PAYMENT_OPERATION") \
        .context(
            payment_operation=operation,
            user_id=user_id,
            amount=amount,
            charge_task_id=charge_task_id,
            **context
        )
    
    if error:
        # Determine error code
        error_code = "PAYMENT_UNKNOWN_ERROR"
        if "insufficient" in str(error).lower() or "balance" in str(error).lower():
            error_code = "PAYMENT_INSUFFICIENT_BALANCE"
        elif "duplicate" in str(error).lower() or "idempotency" in str(error).lower():
            error_code = "PAYMENT_DUPLICATE_CHARGE"
        
        log_builder.error(code=error_code, exception=error)
        log_builder.result(status="FAIL")
        log_builder.log(logger, level="ERROR")
    else:
        log_builder.result(status="SUCCESS")
        log_builder.log(logger, level="INFO")


def log_user_action(action: str, user_id: int, callback_data: Optional[str] = None,
                    model_id: Optional[str] = None, **context):
    """Quick helper for user action logging."""
    StructuredLog("USER_ACTION") \
        .context(
            user_action=action,
            user_id=user_id,
            callback_data=callback_data,
            model_id=model_id,
            **context
        ) \
        .log(logger, level="INFO")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example 1: Database error with fix hint
    StructuredLog("DB_CONNECTION") \
        .context(user_id=12345, hostname="dpg-xxx") \
        .error(
            code="DB_DNS_RESOLUTION_FAILED",
            message="could not translate host name"
        ) \
        .log(logger, level="ERROR")
    
    # Example 2: KIE API timeout
    StructuredLog("KIE_GENERATION") \
        .context(user_id=12345, model_id="flux-pro", chat_id=67890) \
        .phase("POLLING", step="WAIT_RESULT") \
        .timing(duration_ms=95000, timeout_ms=90000) \
        .error(code="KIE_API_TIMEOUT", message="No response after 90s") \
        .log(logger, level="ERROR")
    
    # Example 3: Successful operation
    StructuredLog("PAYMENT_CHARGE") \
        .context(user_id=12345, model_id="flux-pro", amount=50.0) \
        .phase("COMMIT", step="CHARGE") \
        .timing(duration_ms=12.3) \
        .result(status="SUCCESS", balance_after=450.0) \
        .log(logger, level="INFO")

