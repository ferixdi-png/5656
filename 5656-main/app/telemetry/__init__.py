"""
Telemetry module for structured event logging.
All events include cid (correlation ID) and reason codes.

CRITICAL: This module must be fail-open - importing app.telemetry must NEVER crash,
even if telemetry submodules are unavailable.
"""

# Fail-open imports: wrap all imports in try/except to prevent package import failures
try:
    from app.telemetry.events import (
        log_update_received,
        log_callback_received,
        log_command_received,
        log_callback_routed,
        log_callback_rejected,
        log_callback_accepted,
        log_ui_render,
        log_dispatch_ok,
        generate_cid,
    )
except Exception:
    # Fail-open: provide no-op stubs if events module unavailable
    def _noop(*args, **kwargs):
        return None
    
    log_update_received = _noop
    log_callback_received = _noop
    log_command_received = _noop
    log_callback_routed = _noop
    log_callback_rejected = _noop
    log_callback_accepted = _noop
    log_ui_render = _noop
    log_dispatch_ok = _noop
    generate_cid = _noop

try:
    from app.telemetry.telemetry_helpers import (
        get_update_id,
        get_callback_id,
        get_user_id,
        get_chat_id,
        get_message_id,
        safe_answer_callback,
        TelemetryMiddleware,  # Re-export for backward compatibility
    )
except Exception:
    # Fail-open: provide no-op stubs if telemetry_helpers unavailable
    def _noop_util(*args, **kwargs):
        return None
    
    get_update_id = _noop_util
    get_callback_id = _noop_util
    get_user_id = _noop_util
    get_chat_id = _noop_util
    get_message_id = _noop_util
    safe_answer_callback = _noop_util
    TelemetryMiddleware = None

__all__ = [
    "log_update_received",
    "log_callback_received",
    "log_command_received",
    "log_callback_routed",
    "log_callback_rejected",
    "log_callback_accepted",
    "log_ui_render",
    "log_dispatch_ok",
    "generate_cid",
    "get_update_id",
    "get_callback_id",
    "get_user_id",
    "get_chat_id",
    "get_message_id",
    "safe_answer_callback",
    "TelemetryMiddleware",  # Re-export for backward compatibility
]

