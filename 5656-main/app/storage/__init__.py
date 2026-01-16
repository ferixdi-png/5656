"""
Storage module - единый интерфейс для хранения данных

BATCH 48.12: Conditional PostgresStorage import (NO DATABASE MODE support)
"""

from app.storage.base import BaseStorage
from app.storage.json_storage import JsonStorage
from app.storage.factory import create_storage, get_storage, reset_storage

# BATCH 48.12: Import PostgresStorage only if asyncpg available (DB mode)
try:
    from app.storage.pg_storage import PostgresStorage
    _pg_available = True
except (ImportError, NameError) as e:
    # asyncpg not installed or not configured - NO DATABASE MODE
    PostgresStorage = None  # type: ignore
    _pg_available = False

__all__ = [
    'BaseStorage',
    'JsonStorage',
    'create_storage',
    'get_storage',
    'reset_storage'
]

# Only export PostgresStorage if available
if _pg_available:
    __all__.append('PostgresStorage')
