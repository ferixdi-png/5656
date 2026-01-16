"""
Operations observability module.

Read-only tools for monitoring and diagnostics.
"""

from app.ops.observer_config import load_config, ObserverConfig

__all__ = ["load_config", "ObserverConfig"]

