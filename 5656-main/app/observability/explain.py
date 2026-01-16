"""
Ultra-explanatory logging format: WHAT/WHY/STATE/NEXT.

This module provides structured logging that explains:
- WHAT: What action is being performed
- WHY: Why this action is happening
- STATE: Current context (ACTIVE/PASSIVE, cid, update_id, etc.)
- NEXT: What to do if something goes wrong

Example:
    [EXPLAIN][WEBHOOK_IN] WHAT=received_update WHY=telegram_delivery STATE=ACTIVE cid=abc123 update_id=456 NEXT=watch DISPATCH_OK or DISPATCH_FAIL
"""
import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def log_explain(
    event_type: str,
    what: str,
    why: str,
    state: Dict[str, Any],
    next_step: Optional[str] = None,
    level: int = logging.INFO,
    **kwargs: Any
) -> None:
    """
    Log an EXPLAIN event with structured format.
    
    Args:
        event_type: Event type (e.g., WEBHOOK_IN, DISPATCH_START, BOOT_CHECK)
        what: What action is being performed
        why: Why this action is happening
        state: Current context dict (will be merged with kwargs)
        next_step: What to do if something goes wrong (optional)
        level: Logging level (default: INFO)
        **kwargs: Additional context fields
    """
    # Merge state with kwargs
    full_state = {**state, **kwargs}
    
    # Build human-readable message
    state_str = " ".join(f"{k}={v}" for k, v in sorted(full_state.items()) if v is not None)
    message = (
        f"[EXPLAIN][{event_type}] "
        f"WHAT={what} "
        f"WHY={why} "
        f"STATE={state_str}"
    )
    if next_step:
        message += f" NEXT={next_step}"
    
    # Structured data for JSON logs
    structured_data = {
        "event_type": f"EXPLAIN_{event_type}",
        "what": what,
        "why": why,
        "state": full_state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if next_step:
        structured_data["next_step"] = next_step
    
    logger.log(level, message, extra={"json": json.dumps(structured_data)})


def log_deploy_topology(
    instance_id: str,
    pid: int,
    boot_time: str,
    commit_sha: str,
    is_active: bool,
    lock_key: Optional[int] = None,
    lock_holder_pid: Optional[int] = None,
    render_service_name: Optional[str] = None,
    **kwargs: Any
) -> None:
    """
    Log DEPLOY_TOPOLOGY event explaining why there might be 2 instances.
    
    Args:
        instance_id: Unique instance identifier
        pid: Process ID
        boot_time: Boot timestamp (ISO format)
        commit_sha: Git commit SHA
        is_active: Whether this instance is ACTIVE
        lock_key: Advisory lock key (if available)
        lock_holder_pid: PID of lock holder (if available)
        render_service_name: Render service name (if available)
        **kwargs: Additional context
    """
    lock_state = "ACTIVE" if is_active else "PASSIVE"
    
    # Build explanation text
    explanation = (
        "Render rolling deploy: new version starts parallel to old; "
        "advisory lock ensures only one ACTIVE handles side effects. "
        "PASSIVE only serves HTTP/health."
    )
    
    state = {
        "instance_id": instance_id,
        "pid": pid,
        "boot_time": boot_time,
        "commit_sha": commit_sha,
        "is_active_state": lock_state,
        "lock_key": lock_key,
        "lock_holder_pid": lock_holder_pid,
    }
    if render_service_name:
        state["render_service_name"] = render_service_name
    
    state.update(kwargs)
    
    log_explain(
        event_type="DEPLOY_TOPOLOGY",
        what=f"Instance started as {lock_state}",
        why=explanation,
        state=state,
        next_step="Monitor logs for PASSIVE_WAIT or ACTIVE takeover events",
        level=logging.INFO
    )


def log_passive_drop(
    cid: str,
    update_id: Optional[int],
    update_type: str,
    reason: str = "not_active",
    **kwargs: Any
) -> None:
    """
    Log when PASSIVE instance drops a webhook update.
    
    Args:
        cid: Correlation ID
        update_id: Update ID
        update_type: Type of update (message, callback_query, etc.)
        reason: Reason for dropping (default: "not_active")
        **kwargs: Additional context
    """
    state = {
        "cid": cid,
        "update_id": update_id,
        "update_type": update_type,
        "reason": reason,
    }
    state.update(kwargs)
    
    log_explain(
        event_type="PASSIVE_DROP",
        what="Webhook update dropped by PASSIVE instance",
        why="PASSIVE instances do not process updates to avoid double processing",
        state=state,
        next_step="Update will be processed by ACTIVE instance",
        level=logging.INFO
    )


def log_startup_phase(
    phase: str,
    status: str,  # START, IN_PROGRESS, DONE, FAIL
    details: Optional[str] = None,
    next_step: Optional[str] = None,
    **kwargs: Any
) -> None:
    """
    Log a startup phase event.
    
    Args:
        phase: Phase name (BOOT_CHECK, LOCK_STATE, WEBHOOK_ENSURE, DB_INIT, ROUTERS_INIT, READY)
        status: Phase status (START, IN_PROGRESS, DONE, FAIL)
        details: Additional details (optional)
        next_step: What to do if phase fails (optional)
        **kwargs: Additional context
    """
    state = {
        "phase": phase,
        "status": status,
    }
    if details:
        state["details"] = details
    state.update(kwargs)
    
    level = logging.INFO
    if status == "FAIL":
        level = logging.ERROR
        if not next_step:
            next_step = f"Review logs for {phase} failure and fix root cause"
    
    log_explain(
        event_type=f"STARTUP_PHASE_{phase}",
        what=f"Startup phase {phase}",
        why=f"Application initialization step: {phase}",
        state=state,
        next_step=next_step,
        level=level
    )


__all__ = [
    "log_explain",
    "log_deploy_topology",
    "log_passive_drop",
    "log_startup_phase",
]

