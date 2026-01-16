"""
Observability V2: Ultra-explanatory logging for Render production.

Key features:
- Unified correlation ID (CID) propagation
- Structured JSON logs + human-readable summaries
- Clear ACTIVE vs PASSIVE boundaries
- Handler-level explain logs (UI_RENDER, DECISION, DEPENDENCY, SAFE_ERROR)
- DB/pool observability
- Webhook/queue trace
- Rate-limited PASSIVE_WAIT logs
"""

import json
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Rate limiting for PASSIVE_WAIT logs
_last_passive_log_time: float = 0.0
_PASSIVE_LOG_INTERVAL = 30.0  # Log once per 30 seconds


def _mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask secret value, showing only last N chars."""
    if not value:
        return "[EMPTY]"
    if len(value) <= show_chars:
        return "****"
    return f"****{value[-show_chars:]}"


def _mask_url(url: str) -> str:
    """Mask credentials in URL, keep protocol and hostname."""
    if not url:
        return "[EMPTY]"
    if "://" not in url:
        return url
    parts = url.split("://", 1)
    if len(parts) != 2:
        return url
    protocol, rest = parts
    if "@" in rest:
        # postgresql://user:pass@host:port/db -> postgresql://***@host:port/db
        auth, location = rest.split("@", 1)
        return f"{protocol}://***@{location}"
    return url


def log_startup_summary(
    version: str = "unknown",
    git_sha: Optional[str] = None,
    bot_mode: str = "webhook",
    port: int = 10000,
    webhook_base_url: Optional[str] = None,
    dry_run: bool = False,
    subsystems: Dict[str, bool] = None,
    lock_state: str = "UNKNOWN",
) -> None:
    """
    Log STARTUP_SUMMARY: single-line diagnostic header at startup.
    
    Args:
        version: App version
        git_sha: Git commit SHA (if available)
        bot_mode: BOT_MODE (webhook/polling)
        port: HTTP server port
        webhook_base_url: Webhook base URL (masked)
        dry_run: DRY_RUN flag
        subsystems: Dict of subsystem availability (db, telemetry, admin, queue)
        lock_state: Initial lock state (ACTIVE/PASSIVE/UNKNOWN)
    """
    if subsystems is None:
        subsystems = {}
    
    summary = {
        "event": "STARTUP_SUMMARY",
        "version": version,
        "git_sha": git_sha or "unknown",
        "bot_mode": bot_mode,
        "port": port,
        "webhook_base_url": _mask_url(webhook_base_url) if webhook_base_url else None,
        "dry_run": dry_run,
        "subsystems": {
            "db": subsystems.get("db", False),
            "telemetry": subsystems.get("telemetry", False),
            "admin": subsystems.get("admin", False),
            "queue": subsystems.get("queue", False),
        },
        "lock_state": lock_state,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Human-readable summary line
    subsystems_str = ",".join([k for k, v in summary["subsystems"].items() if v])
    logger.info(
        f"STARTUP_SUMMARY version={version} git={git_sha or 'unknown'} "
        f"mode={bot_mode} port={port} subsystems=[{subsystems_str}] lock={lock_state}",
        extra={"structured": summary}
    )


def log_boot_result(success: bool, reason: Optional[str] = None, next_step: Optional[str] = None) -> None:
    """
    Log BOOT_OK or BOOT_FAIL with reason and next step.
    
    Args:
        success: True if boot successful, False otherwise
        reason: Why boot succeeded/failed
        next_step: What to do next (if failed)
    """
    event = "BOOT_OK" if success else "BOOT_FAIL"
    summary = {
        "event": event,
        "success": success,
        "reason": reason or ("All checks passed" if success else "Check failed"),
        "next_step": next_step,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if success:
        logger.info(f"BOOT_OK reason={reason or 'All checks passed'}", extra={"structured": summary})
    else:
        logger.error(f"BOOT_FAIL reason={reason} next_step={next_step}", extra={"structured": summary})


def log_webhook_in(
    cid: str,
    update_id: Optional[int] = None,
    update_type: Optional[str] = None,
    size_bytes: Optional[int] = None,
    ip: Optional[str] = None,
) -> None:
    """
    Log WEBHOOK_IN: incoming webhook request.
    
    Args:
        cid: Correlation ID
        update_id: Telegram update ID
        update_type: Type of update (message, callback_query, etc.)
        size_bytes: Payload size in bytes
        ip: Client IP (masked)
    """
    summary = {
        "event": "WEBHOOK_IN",
        "cid": cid,
        "update_id": update_id,
        "update_type": update_type or "unknown",
        "size_bytes": size_bytes,
        "ip": ip.split(".")[0] + ".***" if ip else None,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"WEBHOOK_IN cid={cid} update_id={update_id} type={update_type or 'unknown'} "
        f"size={size_bytes or 'unknown'}B",
        extra={"structured": summary}
    )


def log_enqueue_ok(
    cid: str,
    update_id: Optional[int] = None,
    queue_depth: int = 0,
    queue_max: int = 100,
) -> None:
    """
    Log ENQUEUE_OK: update successfully enqueued.
    
    Args:
        cid: Correlation ID
        update_id: Telegram update ID
        queue_depth: Current queue depth
        queue_max: Maximum queue size
    """
    summary = {
        "event": "ENQUEUE_OK",
        "cid": cid,
        "update_id": update_id,
        "queue_depth": queue_depth,
        "queue_max": queue_max,
        "queue_utilization_pct": round((queue_depth / queue_max * 100) if queue_max > 0 else 0, 1),
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"ENQUEUE_OK cid={cid} update_id={update_id} queue={queue_depth}/{queue_max}",
        extra={"structured": summary}
    )


def log_worker_pick(
    cid: str,
    update_id: Optional[int] = None,
    worker_id: int = 0,
) -> None:
    """
    Log WORKER_PICK: worker picked update from queue.
    
    Args:
        cid: Correlation ID
        update_id: Telegram update ID
        worker_id: Worker identifier
    """
    summary = {
        "event": "WORKER_PICK",
        "cid": cid,
        "update_id": update_id,
        "worker_id": worker_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.debug(
        f"WORKER_PICK cid={cid} update_id={update_id} worker={worker_id}",
        extra={"structured": summary}
    )


def log_dispatch_start(
    cid: str,
    update_id: Optional[int] = None,
    handler_name: Optional[str] = None,
    route: Optional[str] = None,
) -> None:
    """
    Log DISPATCH_START: handler dispatch started.
    
    Args:
        cid: Correlation ID
        update_id: Telegram update ID
        handler_name: Handler function name
        route: Route/screen ID (if applicable)
    """
    summary = {
        "event": "DISPATCH_START",
        "cid": cid,
        "update_id": update_id,
        "handler_name": handler_name,
        "route": route,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"DISPATCH_START cid={cid} update_id={update_id} handler={handler_name} route={route or 'none'}",
        extra={"structured": summary}
    )


def log_dispatch_ok(
    cid: str,
    update_id: Optional[int] = None,
    handler_name: Optional[str] = None,
    duration_ms: float = 0.0,
) -> None:
    """
    Log DISPATCH_OK: handler completed successfully.
    
    Args:
        cid: Correlation ID
        update_id: Telegram update ID
        handler_name: Handler function name
        duration_ms: Handler execution duration in milliseconds
    """
    summary = {
        "event": "DISPATCH_OK",
        "cid": cid,
        "update_id": update_id,
        "handler_name": handler_name,
        "duration_ms": round(duration_ms, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"DISPATCH_OK cid={cid} update_id={update_id} handler={handler_name} duration={duration_ms:.1f}ms",
        extra={"structured": summary}
    )


def log_dispatch_fail(
    cid: str,
    update_id: Optional[int] = None,
    handler_name: Optional[str] = None,
    error_type: str = "Exception",
    safe_message: str = "Handler failed",
    file_line: Optional[str] = None,
    duration_ms: float = 0.0,
    next_step: Optional[str] = None,
) -> None:
    """
    Log DISPATCH_FAIL: handler failed with error.
    
    Args:
        cid: Correlation ID
        update_id: Telegram update ID
        handler_name: Handler function name
        error_type: Type of error (Exception class name)
        safe_message: Safe error message (no secrets)
        file_line: File:line or module+func
        duration_ms: Handler execution duration before failure
        next_step: Recommended next step
    """
    summary = {
        "event": "DISPATCH_FAIL",
        "cid": cid,
        "update_id": update_id,
        "handler_name": handler_name,
        "error_type": error_type,
        "safe_message": safe_message,
        "file_line": file_line,
        "duration_ms": round(duration_ms, 2),
        "next_step": next_step,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.error(
        f"DISPATCH_FAIL cid={cid} update_id={update_id} handler={handler_name} "
        f"error={error_type} msg={safe_message} file={file_line or 'unknown'} "
        f"duration={duration_ms:.1f}ms next_step={next_step or 'check logs'}",
        extra={"structured": summary}
    )


def log_ui_render(
    cid: str,
    screen_id: str,
    user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> None:
    """
    Log UI_RENDER: screen/menu rendered.
    
    Args:
        cid: Correlation ID
        screen_id: Screen/menu identifier
        user_id: User ID
        reason: Why this screen was rendered
    """
    summary = {
        "event": "UI_RENDER",
        "cid": cid,
        "screen_id": screen_id,
        "user_id": user_id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"UI_RENDER cid={cid} screen={screen_id} user_id={user_id} reason={reason or 'user_action'}",
        extra={"structured": summary}
    )


def log_decision(
    cid: str,
    decision_point: str,
    chosen_branch: str,
    parameters: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log DECISION: conditional branch chosen.
    
    Args:
        cid: Correlation ID
        decision_point: Decision point name
        chosen_branch: Which branch was chosen
        parameters: Parameters that influenced the decision
    """
    summary = {
        "event": "DECISION",
        "cid": cid,
        "decision_point": decision_point,
        "chosen_branch": chosen_branch,
        "parameters": parameters or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    params_str = ",".join([f"{k}={v}" for k, v in (parameters or {}).items()])
    logger.debug(
        f"DECISION cid={cid} point={decision_point} branch={chosen_branch} params=[{params_str}]",
        extra={"structured": summary}
    )


def log_dependency(
    cid: str,
    dependency_type: str,
    dependency_name: str,
    available: bool,
    reason: Optional[str] = None,
) -> None:
    """
    Log DEPENDENCY: external dependency check.
    
    Args:
        cid: Correlation ID
        dependency_type: Type (db, api, file, etc.)
        dependency_name: Dependency name/identifier
        available: Whether dependency is available
        reason: Why it's available/unavailable
    """
    summary = {
        "event": "DEPENDENCY",
        "cid": cid,
        "dependency_type": dependency_type,
        "dependency_name": dependency_name,
        "available": available,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    status = "AVAILABLE" if available else "UNAVAILABLE"
    logger.info(
        f"DEPENDENCY cid={cid} type={dependency_type} name={dependency_name} "
        f"status={status} reason={reason or 'unknown'}",
        extra={"structured": summary}
    )


def log_safe_error(
    cid: str,
    error_type: str,
    safe_message: str,
    file_line: Optional[str] = None,
    update_id: Optional[int] = None,
    next_step: Optional[str] = None,
) -> None:
    """
    Log SAFE_ERROR: error without secrets, with next step.
    
    Args:
        cid: Correlation ID
        error_type: Error type (Exception class name)
        safe_message: Safe error message (no secrets)
        file_line: File:line or module+func
        update_id: Telegram update ID
        next_step: Recommended next step
    """
    summary = {
        "event": "SAFE_ERROR",
        "cid": cid,
        "error_type": error_type,
        "safe_message": safe_message,
        "file_line": file_line,
        "update_id": update_id,
        "next_step": next_step,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.error(
        f"SAFE_ERROR cid={cid} type={error_type} msg={safe_message} "
        f"file={file_line or 'unknown'} update_id={update_id} next_step={next_step or 'check logs'}",
        extra={"structured": summary}
    )


def log_db_observability(
    pool_config: Dict[str, Any],
    read_only_check: bool = False,
    error_type: Optional[str] = None,
    next_step: Optional[str] = None,
) -> None:
    """
    Log DB observability: pool config and health.
    
    Args:
        pool_config: Pool configuration (maxconn, timeout, etc.) - NO URL
        read_only_check: Result of read-only connection test
        error_type: Error type if DB unavailable
        next_step: Recommended next step if error
    """
    summary = {
        "event": "DB_OBSERVABILITY",
        "pool_config": {k: v for k, v in pool_config.items() if k != "dsn" and k != "url"},
        "read_only_check": read_only_check,
        "error_type": error_type,
        "next_step": next_step,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if error_type:
        logger.warning(
            f"DB_OBSERVABILITY error={error_type} read_only={read_only_check} "
            f"next_step={next_step or 'check DATABASE_URL'}",
            extra={"structured": summary}
        )
    else:
        logger.info(
            f"DB_OBSERVABILITY pool_maxconn={pool_config.get('maxconn', 'unknown')} "
            f"read_only={read_only_check}",
            extra={"structured": summary}
        )


def log_db_degraded(
    cid: str,
    operation: str,
    reason: str,
    fallback_used: bool = False,
) -> None:
    """
    Log DB_DEGRADED: DB unavailable, operating in degraded mode.
    
    Args:
        cid: Correlation ID
        operation: Operation that failed
        reason: Why DB is unavailable
        fallback_used: Whether fallback was used
    """
    summary = {
        "event": "DB_DEGRADED",
        "cid": cid,
        "operation": operation,
        "reason": reason,
        "fallback_used": fallback_used,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.warning(
        f"DB_DEGRADED cid={cid} operation={operation} reason={reason} fallback={fallback_used}",
        extra={"structured": summary}
    )


def log_passive_wait(
    lock_holder_pid: Optional[int] = None,
    lock_holder_host: Optional[str] = None,
    idle_duration: Optional[float] = None,
) -> None:
    """
    Log PASSIVE_WAIT: PASSIVE instance waiting (rate-limited).
    
    Args:
        lock_holder_pid: PID of lock holder
        lock_holder_host: Hostname of lock holder
        idle_duration: How long lock has been idle
    """
    global _last_passive_log_time
    
    now = time.time()
    if now - _last_passive_log_time < _PASSIVE_LOG_INTERVAL:
        return  # Rate limit: skip this log
    
    _last_passive_log_time = now
    
    summary = {
        "event": "PASSIVE_WAIT",
        "lock_holder_pid": lock_holder_pid,
        "lock_holder_host": lock_holder_host,
        "idle_duration": idle_duration,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    holder_info = f"pid={lock_holder_pid}" if lock_holder_pid else "unknown"
    logger.info(
        f"PASSIVE_WAIT lock_holder={holder_info} idle={idle_duration or 'unknown'}s",
        extra={"structured": summary}
    )


def log_deploy_phase(phase: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log DEPLOY_PHASE: deployment phase marker.
    
    Args:
        phase: Phase name (image_pull, build, starting, lock_acquire, init_services, webhook_ensure, ready)
        details: Additional phase details
    """
    summary = {
        "event": "DEPLOY_PHASE",
        "phase": phase,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    details_str = ",".join([f"{k}={v}" for k, v in (details or {}).items()])
    logger.info(
        f"DEPLOY_PHASE phase={phase} {details_str}",
        extra={"structured": summary}
    )


def log_ready_summary(
    endpoints: List[str],
    webhook_url: Optional[str] = None,
    callback_url: Optional[str] = None,
) -> None:
    """
    Log READY_SUMMARY: application ready for requests.
    
    Args:
        endpoints: List of available endpoints
        webhook_url: Webhook URL (masked)
        callback_url: KIE callback URL (masked)
    """
    summary = {
        "event": "READY_SUMMARY",
        "endpoints": endpoints,
        "webhook_url": _mask_url(webhook_url) if webhook_url else None,
        "callback_url": _mask_url(callback_url) if callback_url else None,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    endpoints_str = ",".join(endpoints)
    logger.info(
        f"READY_SUMMARY endpoints=[{endpoints_str}] webhook={'SET' if webhook_url else 'NOT_SET'} "
        f"callback={'SET' if callback_url else 'NOT_SET'}",
        extra={"structured": summary}
    )


__all__ = [
    "log_startup_summary",
    "log_boot_result",
    "log_webhook_in",
    "log_enqueue_ok",
    "log_worker_pick",
    "log_dispatch_start",
    "log_dispatch_ok",
    "log_dispatch_fail",
    "log_ui_render",
    "log_decision",
    "log_dependency",
    "log_safe_error",
    "log_db_observability",
    "log_db_degraded",
    "log_passive_wait",
    "log_deploy_phase",
    "log_ready_summary",
]


