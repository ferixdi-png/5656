"""
DEPRECATED: Этот модуль существует только для обратной совместимости.
Используйте app.locking.single_instance вместо этого.

Thin wrapper вокруг app.locking.single_instance для обратной совместимости.
"""

import sys
from app.locking.single_instance import (
    acquire_single_instance_lock,
    release_single_instance_lock as _release_single_instance_lock,
    is_lock_held,
)
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def acquire_singleton_lock_sync() -> bool:
    """
    DEPRECATED: Используйте app.locking.single_instance.acquire_single_instance_lock()
    
    Синхронная версия acquire_singleton_lock() для обратной совместимости.
    
    Попытаться получить singleton lock (PostgreSQL или filelock)
    
    Returns:
        True если lock получен, False если нет
    
    Side effect:
        Если lock не получен, вызывает sys.exit(0) (не бесконечные рестарты)
    """
    if acquire_single_instance_lock():
        return True
    
    # Lock не получен - другой экземпляр запущен
    logger.error("=" * 60)
    logger.error("[LOCK] FAILED: Another bot instance is already running")
    logger.error("[LOCK] Exiting gracefully (exit code 0) to prevent restart loop")
    logger.error("=" * 60)
    sys.exit(0)  # exit(0) чтобы Render не считал это ошибкой


def release_singleton_lock_sync() -> None:
    """
    DEPRECATED: Используйте app.locking.single_instance.release_single_instance_lock()
    
    Синхронная версия release_singleton_lock() для обратной совместимости.
    
    Освободить singleton lock
    """
    _release_single_instance_lock()


# Module-global для хранения lock объекта (для async обёрток)
_lock_instance = None


async def acquire_singleton_lock() -> bool:
    """
    Async обёртка для acquire_singleton_lock().
    Используется в main_render.py для совместимости.
    
    Returns:
        True если lock получен, False если нет
    """
    global _lock_instance
    
    # Используем синхронную версию (lock механизм сам по себе синхронный)
    # Но оборачиваем в async для совместимости с async кодом
    import asyncio
    
    # Запускаем синхронную функцию в executor
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, acquire_singleton_lock_sync)
    
    if result:
        # Сохраняем информацию о lock для последующего release
        _lock_instance = True
    
    return result


async def release_singleton_lock() -> None:
    """
    Async обёртка для release_singleton_lock().
    Используется в main_render.py для совместимости.
    """
    global _lock_instance
    
    if _lock_instance:
        import asyncio
        
        # Запускаем синхронную функцию в executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, release_singleton_lock_sync)
        
        _lock_instance = None

