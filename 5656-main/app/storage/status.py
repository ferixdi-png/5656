"""Job status normalization helpers."""

from __future__ import annotations

from typing import Optional

VALID_JOB_STATUSES = {"queued", "running", "done", "failed", "canceled"}
TERMINAL_JOB_STATUSES = {"done", "failed", "canceled"}
STATUS_ALIASES = {
    "pending": "queued",
    "processing": "running",
    "completed": "done",
    "succeeded": "done",
    "success": "done",
    "failed": "failed",
    "error": "failed",
    "exception": "failed",
    "timeout": "failed",
    "cancelled": "canceled",
    "canceled": "canceled",
}


def normalize_job_status(status: Optional[str]) -> str:
    """Normalize job status values to the standard set."""
    if not status:
        return "failed"
    normalized = STATUS_ALIASES.get(status, status)
    if normalized not in VALID_JOB_STATUSES:
        return "failed"
    return normalized


def is_terminal_status(status: Optional[str]) -> bool:
    """Return True when status represents a finished job."""
    return normalize_job_status(status) in TERMINAL_JOB_STATUSES
