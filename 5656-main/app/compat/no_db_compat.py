"""
BATCH 48: NO DATABASE COMPATIBILITY LAYER

Перенаправляет все вызовы database функций на FileStorage.
Полная совместимость со старым кодом без изменения каждого файла.
"""

import logging
from typing import Optional
from app.storage.file_storage import get_file_storage

logger = logging.getLogger(__name__)


# ============================================================================
# BALANCE OPERATIONS
# ============================================================================

async def get_user_balance(user_id: int) -> float:
    """Get user balance from FileStorage."""
    storage = get_file_storage()
    return await storage.get_balance(user_id)


async def get_user_balance_async(user_id: int) -> float:
    """Async version - same as get_user_balance."""
    return await get_user_balance(user_id)


async def add_user_balance(user_id: int, amount: float):
    """Add to user balance in FileStorage."""
    storage = get_file_storage()
    await storage.add_balance(user_id, amount, auto_commit=True)


async def subtract_user_balance(user_id: int, amount: float) -> bool:
    """Subtract from user balance in FileStorage."""
    storage = get_file_storage()
    return await storage.subtract_balance(user_id, amount, auto_commit=True)


async def set_user_balance(user_id: int, amount: float):
    """Set user balance in FileStorage."""
    storage = get_file_storage()
    await storage.set_balance(user_id, amount, auto_commit=True)


# ============================================================================
# DATABASE INFO (NO-OP для совместимости)
# ============================================================================

def get_connection_pool():
    """NO-OP: No database connection needed."""
    logger.debug("[NO_DB_COMPAT] get_connection_pool called (NO-OP)")
    return None


def close_connection_pool():
    """NO-OP: No database connection to close."""
    logger.debug("[NO_DB_COMPAT] close_connection_pool called (NO-OP)")


async def init_db():
    """NO-OP: No database migrations needed."""
    logger.info("[NO_DB_COMPAT] ✅ init_db called (NO-OP - using FileStorage)")


# ============================================================================
# MOCK STORAGE для тестов
# ============================================================================

class MockDBStorage:
    """Mock DB storage - redirects to FileStorage."""
    
    async def get_user_balance(self, user_id: int) -> float:
        return await get_user_balance(user_id)
    
    async def add_user_balance(self, user_id: int, amount: float):
        await add_user_balance(user_id, amount)
    
    async def subtract_user_balance(self, user_id: int, amount: float) -> bool:
        return await subtract_user_balance(user_id, amount)
    
    async def set_user_balance(self, user_id: int, amount: float):
        await set_user_balance(user_id, amount)


def get_db_storage() -> MockDBStorage:
    """Get mock DB storage."""
    return MockDBStorage()

