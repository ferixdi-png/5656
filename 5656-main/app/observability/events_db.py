"""
Database-driven event logging for observability.

Best-effort, async, non-blocking: errors are swallowed to prevent breaking user flows.
"""

import logging
import json
import traceback
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Global pool reference (set by init)
_db_pool = None


def init_events_db(pool):
    """Initialize events DB with connection pool."""
    global _db_pool
    _db_pool = pool
    logger.info("[OBSERVABILITY] ✅ Events DB initialized")


async def log_event(
    level: str,
    event: str,
    cid: Optional[str] = None,
    user_id: Optional[int] = None,
    chat_id: Optional[int] = None,
    update_id: Optional[int] = None,
    task_id: Optional[int] = None,
    model: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None,
    tags: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Log event to app_events table (best-effort, non-blocking).
    
    Args:
        level: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
        event: Event name (e.g., 'UPDATE_RECEIVED', 'DISPATCH_OK', 'KIE_JOB_CREATED')
        cid: Correlation ID
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        update_id: Telegram update ID
        task_id: Job ID (FK to jobs table)
        model: Model ID
        payload: Event-specific data (will be JSON-serialized)
        error: Exception object (stack trace will be extracted)
        tags: Additional tags for filtering
    
    Returns:
        True if logged successfully, False otherwise (errors are swallowed)
    """
    if _db_pool is None:
        # Not initialized yet, skip silently
        return False
    
    try:
        err_stack = None
        if error:
            err_stack = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        
        payload_json = json.dumps(payload) if payload else "{}"
        tags_json = json.dumps(tags) if tags else "{}"
        
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO app_events (
                    ts, level, event, cid, user_id, chat_id, update_id,
                    task_id, model, payload_json, err_stack, tags
                ) VALUES (
                    NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11::jsonb
                )
                """,
                level,
                event,
                cid,
                user_id,
                chat_id,
                update_id,
                task_id,
                model,
                payload_json,
                err_stack,
                tags_json,
            )
        return True
    
    except Exception as e:
        # Swallow errors to prevent breaking user flows
        logger.warning(f"[OBSERVABILITY] Failed to log event {event}: {e}", exc_info=False)
        return False


# Convenience functions for common events
async def log_update_received(update_id: int, cid: str, update_type: str) -> bool:
    """Log UPDATE_RECEIVED event."""
    return await log_event(
        level="INFO",
        event="UPDATE_RECEIVED",
        cid=cid,
        update_id=update_id,
        payload={"update_type": update_type},
    )


async def log_callback_received(cid: str, callback_data: str, user_id: int, update_id: int) -> bool:
    """Log CALLBACK_RECEIVED event."""
    return await log_event(
        level="INFO",
        event="CALLBACK_RECEIVED",
        cid=cid,
        user_id=user_id,
        update_id=update_id,
        payload={"callback_data": callback_data},
    )


async def log_dispatch_ok(cid: str, handler: str, user_id: Optional[int] = None) -> bool:
    """Log DISPATCH_OK event."""
    return await log_event(
        level="INFO",
        event="DISPATCH_OK",
        cid=cid,
        user_id=user_id,
        payload={"handler": handler},
    )


async def log_dispatch_fail(cid: str, handler: str, error: Exception, user_id: Optional[int] = None) -> bool:
    """Log DISPATCH_FAIL event."""
    return await log_event(
        level="ERROR",
        event="DISPATCH_FAIL",
        cid=cid,
        user_id=user_id,
        error=error,
        payload={"handler": handler},
    )


async def log_passive_reject(cid: str, update_id: int, update_type: str) -> bool:
    """Log PASSIVE_REJECT event."""
    return await log_event(
        level="WARNING",
        event="PASSIVE_REJECT",
        cid=cid,
        update_id=update_id,
        payload={"update_type": update_type},
    )


async def log_unknown_callback(cid: str, callback_data: str, user_id: int) -> bool:
    """Log UNKNOWN_CALLBACK event."""
    return await log_event(
        level="WARNING",
        event="UNKNOWN_CALLBACK",
        cid=cid,
        user_id=user_id,
        payload={"callback_data": callback_data},
    )


async def log_kie_job_created(task_id: int, model: str, cid: str, user_id: int, kie_task_id: str) -> bool:
    """Log KIE_JOB_CREATED event."""
    return await log_event(
        level="INFO",
        event="KIE_JOB_CREATED",
        cid=cid,
        user_id=user_id,
        task_id=task_id,
        model=model,
        payload={"kie_task_id": kie_task_id},
    )


async def log_kie_job_polled(task_id: int, model: str, kie_status: str, cid: Optional[str] = None) -> bool:
    """Log KIE_JOB_POLLED event."""
    return await log_event(
        level="DEBUG",
        event="KIE_JOB_POLLED",
        cid=cid,
        task_id=task_id,
        model=model,
        payload={"kie_status": kie_status},
    )


async def log_kie_job_completed(task_id: int, model: str, success: bool, cid: Optional[str] = None, error: Optional[Exception] = None) -> bool:
    """Log KIE_JOB_COMPLETED event."""
    return await log_event(
        level="INFO" if success else "ERROR",
        event="KIE_JOB_COMPLETED",
        cid=cid,
        task_id=task_id,
        model=model,
        error=error,
        payload={"success": success},
    )


