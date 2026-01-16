"""
BUTTON TRACE - logging for critical callbacks.

Provides trace logging for key user/admin callbacks:
- received → routed → accepted/rejected → ui_render

All logs include cid/update_id for correlation.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


def log_button_received(
    cid: str,
    callback_data: str,
    update_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> None:
    """
    Log BUTTON_RECEIVED: callback received from user.
    
    Args:
        cid: Correlation ID
        callback_data: Callback data (button identifier)
        update_id: Telegram update ID
        user_id: User ID
    """
    summary = {
        "event": "BUTTON_RECEIVED",
        "cid": cid,
        "callback_data": callback_data,
        "update_id": update_id,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"BUTTON_RECEIVED cid={cid} callback={callback_data} update_id={update_id} user_id={user_id}",
        extra={"structured": summary}
    )


def log_button_routed(
    cid: str,
    callback_data: str,
    handler_name: str,
    update_id: Optional[int] = None,
) -> None:
    """
    Log BUTTON_ROUTED: callback routed to handler.
    
    Args:
        cid: Correlation ID
        callback_data: Callback data
        handler_name: Handler function name
        update_id: Telegram update ID
    """
    summary = {
        "event": "BUTTON_ROUTED",
        "cid": cid,
        "callback_data": callback_data,
        "handler_name": handler_name,
        "update_id": update_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"BUTTON_ROUTED cid={cid} callback={callback_data} handler={handler_name} update_id={update_id}",
        extra={"structured": summary}
    )


def log_button_accepted(
    cid: str,
    callback_data: str,
    handler_name: str,
    update_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Log BUTTON_ACCEPTED: callback accepted by handler.
    
    Args:
        cid: Correlation ID
        callback_data: Callback data
        handler_name: Handler function name
        update_id: Telegram update ID
        reason: Why it was accepted
    """
    summary = {
        "event": "BUTTON_ACCEPTED",
        "cid": cid,
        "callback_data": callback_data,
        "handler_name": handler_name,
        "update_id": update_id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"BUTTON_ACCEPTED cid={cid} callback={callback_data} handler={handler_name} "
        f"update_id={update_id} reason={reason or 'normal'}",
        extra={"structured": summary}
    )


def log_button_rejected(
    cid: str,
    callback_data: str,
    handler_name: Optional[str] = None,
    update_id: Optional[int] = None,
    reason: str = "unknown",
) -> None:
    """
    Log BUTTON_REJECTED: callback rejected (permission/validation/etc).
    
    Args:
        cid: Correlation ID
        callback_data: Callback data
        handler_name: Handler function name (if known)
        update_id: Telegram update ID
        reason: Why it was rejected
    """
    summary = {
        "event": "BUTTON_REJECTED",
        "cid": cid,
        "callback_data": callback_data,
        "handler_name": handler_name,
        "update_id": update_id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.warning(
        f"BUTTON_REJECTED cid={cid} callback={callback_data} handler={handler_name or 'unknown'} "
        f"update_id={update_id} reason={reason}",
        extra={"structured": summary}
    )


__all__ = [
    "log_button_received",
    "log_button_routed",
    "log_button_accepted",
    "log_button_rejected",
]

