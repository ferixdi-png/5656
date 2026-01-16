"""
Observability module for structured event logging and diagnostics.
"""

from app.observability.events_db import (
    init_events_db,
    log_event,
    log_update_received,
    log_callback_received,
    log_dispatch_ok,
    log_dispatch_fail,
    log_passive_reject,
    log_unknown_callback,
    log_kie_job_created,
    log_kie_job_polled,
    log_kie_job_completed,
)

__all__ = [
    "init_events_db",
    "log_event",
    "log_update_received",
    "log_callback_received",
    "log_dispatch_ok",
    "log_dispatch_fail",
    "log_passive_reject",
    "log_unknown_callback",
    "log_kie_job_created",
    "log_kie_job_polled",
    "log_kie_job_completed",
]
