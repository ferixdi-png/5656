"""
Resilience utilities: fail-open/fail-closed strategies, circuit breakers, retries.
"""

from app.resilience.fail_strategy import (
    FailureMode,
    FailStrategyError,
    FailOpenError,
    FailClosedError,
    fail_open,
    fail_closed,
    log_fail_open,
    log_fail_closed,
    OPERATION_STRATEGY,
    get_operation_strategy,
    is_fail_open_operation,
    is_fail_closed_operation,
)

__all__ = [
    "FailureMode",
    "FailStrategyError",
    "FailOpenError",
    "FailClosedError",
    "fail_open",
    "fail_closed",
    "log_fail_open",
    "log_fail_closed",
    "OPERATION_STRATEGY",
    "get_operation_strategy",
    "is_fail_open_operation",
    "is_fail_closed_operation",
]

