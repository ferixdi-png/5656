"""
Telemetry event logging with cid (correlation ID) and structured context.
All functions are fail-safe and accept optional parameters gracefully.
"""

import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_cid() -> str:
    """Generate correlation ID for event chain."""
    return f"cid_{uuid.uuid4().hex[:12]}"


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get attribute from object."""
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


def _truncate_callback_data(data: str, max_len: int = 100) -> str:
    """Truncate callback data for logging."""
    if not data:
        return ""
    if len(data) <= max_len:
        return data
    return data[:max_len] + "..."


def log_update_received(
    update_id: Optional[int] = None,
    user_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    update_type: Optional[str] = None,
    cid: Optional[str] = None,
    **extra
) -> str:
    """
    Log UPDATE_RECEIVED event.
    
    Args:
        update_id: Telegram update ID
        user_id: User ID (hashed in production)
        chat_id: Chat ID
        update_type: Type of update (message, callback_query, etc.)
        cid: Correlation ID (generated if not provided)
        **extra: Additional context
        
    Returns:
        Correlation ID (cid)
    """
    if cid is None:
        cid = generate_cid()
    
    try:
        logger.info(
            f"📥 UPDATE_RECEIVED cid={cid} update_id={update_id} "
            f"user_id={user_id} chat_id={chat_id} type={update_type}",
            extra={
                "event_type": "UPDATE_RECEIVED",
                "cid": cid,
                "update_id": update_id,
                "user_id": user_id,
                "chat_id": chat_id,
                "update_type": update_type,
                **extra,
            }
        )
    except Exception as e:
        # Fail-safe: if logging fails, at least log basic info
        logger.error(f"Failed to log UPDATE_RECEIVED: {e}")
    
    return cid


def log_callback_received(
    callback_data: Optional[str] = None,
    query_id: Optional[str] = None,
    message_id: Optional[int] = None,
    user_id: Optional[int] = None,
    update_id: Optional[int] = None,
    cid: Optional[str] = None,
    **extra
) -> str:
    """
    Log CALLBACK_RECEIVED event.
    
    Args:
        callback_data: Callback data (truncated for logging)
        query_id: Callback query ID
        message_id: Message ID
        user_id: User ID
        update_id: Update ID (optional, may be None for callbacks)
        cid: Correlation ID (generated if not provided)
        **extra: Additional context
        
    Returns:
        Correlation ID (cid)
    """
    if cid is None:
        cid = generate_cid()
    
    try:
        truncated_data = _truncate_callback_data(callback_data or "")
        # Use update_id parameter if provided, otherwise try extra
        final_update_id = update_id if update_id is not None else extra.get("update_id")
        logger.info(
            f"🔘 CALLBACK_RECEIVED cid={cid} data='{truncated_data}' "
            f"query_id={query_id} message_id={message_id} user_id={user_id} update_id={final_update_id}",
            extra={
                "event_type": "CALLBACK_RECEIVED",
                "cid": cid,
                "callback_data": truncated_data,
                "query_id": query_id,
                "message_id": message_id,
                "user_id": user_id,
                "update_id": final_update_id,
                **{k: v for k, v in extra.items() if k != "update_id"},
            }
        )
    except Exception as e:
        logger.error(f"Failed to log CALLBACK_RECEIVED: {e}")
    
    return cid


def log_command_received(
    command: Optional[str] = None,
    message_id: Optional[int] = None,
    user_id: Optional[int] = None,
    cid: Optional[str] = None,
    **extra
) -> str:
    """
    Log COMMAND_RECEIVED event.
    
    Args:
        command: Command text (e.g., "/start")
        message_id: Message ID
        user_id: User ID
        cid: Correlation ID (generated if not provided)
        **extra: Additional context
        
    Returns:
        Correlation ID (cid)
    """
    if cid is None:
        cid = generate_cid()
    
    try:
        logger.info(
            f"📨 COMMAND_RECEIVED cid={cid} command='{command}' "
            f"message_id={message_id} user_id={user_id}",
            extra={
                "event_type": "COMMAND_RECEIVED",
                "cid": cid,
                "command": command,
                "message_id": message_id,
                "user_id": user_id,
                **extra,
            }
        )
    except Exception as e:
        logger.error(f"Failed to log COMMAND_RECEIVED: {e}")
    
    return cid


def log_callback_routed(
    callback_data: Optional[str] = None,
    handler: Optional[str] = None,
    cid: Optional[str] = None,
    **extra
) -> None:
    """
    Log CALLBACK_ROUTED event.
    
    Args:
        callback_data: Callback data
        handler: Handler name that will process this callback
        cid: Correlation ID
        **extra: Additional context (ignored safely)
    """
    try:
        truncated_data = _truncate_callback_data(callback_data or "")
        logger.info(
            f"🔄 CALLBACK_ROUTED cid={cid} data='{truncated_data}' handler={handler}",
            extra={
                "event_type": "CALLBACK_ROUTED",
                "cid": cid,
                "callback_data": truncated_data,
                "handler": handler,
                **extra,
            }
        )
    except Exception as e:
        logger.error(f"Failed to log CALLBACK_ROUTED: {e}")


def log_callback_rejected(
    callback_data: Optional[str] = None,
    reason: Optional[str] = None,
    reason_detail: Optional[str] = None,
    reason_code: Optional[str] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    cid: Optional[str] = None,
    **extra
) -> None:
    """
    Log CALLBACK_REJECTED event.
    
    Args:
        callback_data: Callback data
        reason: Rejection reason code (deprecated, use reason_code)
        reason_code: Rejection reason code (e.g., "PASSIVE_REJECT", "VALIDATION_FAIL", "UNKNOWN_CALLBACK")
        reason_detail: Detailed reason (optional, backward compatible)
        error_type: Error type if rejection was due to exception
        error_message: Error message if rejection was due to exception
        cid: Correlation ID
        **extra: Additional context (ignored safely for backward compatibility)
    """
    try:
        truncated_data = _truncate_callback_data(callback_data or "")
        # Use reason_code if provided, fallback to reason for backward compatibility
        final_reason = reason_code or reason or "UNKNOWN"
        detail = reason_detail or extra.get("reason_detail") or ""
        if detail:
            detail = f" detail={detail}"
        
        # Build log message
        log_msg = f"⚠️ CALLBACK_REJECTED cid={cid} data='{truncated_data}' reason={final_reason}{detail}"
        if error_type:
            log_msg += f" error_type={error_type}"
        if error_message:
            log_msg += f" error_msg={error_message[:100]}"
        
        logger.warning(
            log_msg,
            extra={
                "event_type": "CALLBACK_REJECTED",
                "cid": cid,
                "callback_data": truncated_data,
                "reason": final_reason,
                "reason_code": final_reason,
                "reason_detail": reason_detail or extra.get("reason_detail"),
                "error_type": error_type,
                "error_message": error_message,
                **{k: v for k, v in extra.items() if k not in ("reason_detail", "reason_code", "error_type", "error_message")},
            }
        )
    except Exception as e:
        # Ultimate fail-safe: if even logging fails, at least log basic info
        try:
            logger.error(f"Failed to log CALLBACK_REJECTED: {e}")
            logger.warning(f"CALLBACK_REJECTED (fallback): cid={cid} reason={reason_code or reason}")
        except Exception:
            pass  # If even this fails, just pass silently


def log_callback_accepted(
    callback_data: Optional[str] = None,
    handler: Optional[str] = None,
    cid: Optional[str] = None,
    **extra
) -> None:
    """
    Log CALLBACK_ACCEPTED event.
    
    Args:
        callback_data: Callback data
        handler: Handler name
        cid: Correlation ID
        **extra: Additional context
    """
    try:
        truncated_data = _truncate_callback_data(callback_data or "")
        logger.info(
            f"✅ CALLBACK_ACCEPTED cid={cid} data='{truncated_data}' handler={handler}",
            extra={
                "event_type": "CALLBACK_ACCEPTED",
                "cid": cid,
                "callback_data": truncated_data,
                "handler": handler,
                **extra,
            }
        )
    except Exception as e:
        logger.error(f"Failed to log CALLBACK_ACCEPTED: {e}")


def log_ui_render(
    screen_id: Optional[str] = None,
    cid: Optional[str] = None,
    **extra
) -> None:
    """
    Log UI_RENDER event.
    
    Args:
        screen_id: Screen identifier
        cid: Correlation ID
        **extra: Additional context
    """
    try:
        logger.info(
            f"🎨 UI_RENDER cid={cid} screen_id={screen_id}",
            extra={
                "event_type": "UI_RENDER",
                "cid": cid,
                "screen_id": screen_id,
                **extra,
            }
        )
    except Exception as e:
        logger.error(f"Failed to log UI_RENDER: {e}")


def log_dispatch_ok(
    cid: Optional[str] = None,
    **extra
) -> None:
    """
    Log DISPATCH_OK event (end of successful chain).
    
    Args:
        cid: Correlation ID
        **extra: Additional context
    """
    try:
        logger.info(
            f"✅ DISPATCH_OK cid={cid}",
            extra={
                "event_type": "DISPATCH_OK",
                "cid": cid,
                **extra,
            }
        )
    except Exception as e:
        logger.error(f"Failed to log DISPATCH_OK: {e}")

