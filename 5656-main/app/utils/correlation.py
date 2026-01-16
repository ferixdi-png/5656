"""
Correlation ID helpers for log tracing.
"""
from __future__ import annotations

import hashlib
import uuid
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


def ensure_correlation_id(seed: str | None = None) -> str:
    current = _correlation_id.get()
    if current:
        return current
    if seed:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
        _correlation_id.set(digest)
        return digest
    generated = uuid.uuid4().hex[:8]
    _correlation_id.set(generated)
    return generated


def correlation_tag() -> str:
    corr = get_correlation_id()
    return f"[corr={corr}]" if corr else "[corr=none]"
