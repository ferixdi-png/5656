"""
BATCH 48: Compatibility layer for NO DATABASE MODE.
"""

from app.compat.no_db_compat import (
    get_user_balance,
    get_user_balance_async,
    add_user_balance,
    subtract_user_balance,
    set_user_balance,
    get_connection_pool,
    close_connection_pool,
    init_db,
    get_db_storage,
)

__all__ = [
    "get_user_balance",
    "get_user_balance_async",
    "add_user_balance",
    "subtract_user_balance",
    "set_user_balance",
    "get_connection_pool",
    "close_connection_pool",
    "init_db",
    "get_db_storage",
]

