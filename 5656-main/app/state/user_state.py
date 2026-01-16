"""
User state - синхронные и async функции для работы с пользователями
БЕЗ зависимостей от bot_kie.py (устраняет circular imports)

Использует app/services/user_service для async операций
и предоставляет синхронные обертки для обратной совместимости.
"""

import logging
import asyncio
from typing import Optional
from app.services.user_service import (
    get_user_balance as get_user_balance_async_service,
    get_user_language as get_user_language_async_service,
    get_user_free_generations_remaining as get_user_free_generations_remaining_service,
    has_claimed_gift as has_claimed_gift_service,
    get_admin_limit as get_admin_limit_service,
    get_admin_spent as get_admin_spent_service,
    get_admin_remaining as get_admin_remaining_service,
    get_is_admin as get_is_admin_service,
)

logger = logging.getLogger(__name__)


def _run_async_safe(coro):
    """
    Безопасный запуск async функции в синхронном контексте.
    Пытается использовать существующий event loop, если возможно.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если loop уже запущен, используем run_in_executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # Нет event loop, создаем новый
        return asyncio.run(coro)
    except Exception as e:
        logger.error(f"Error running async function: {e}", exc_info=True)
        # Fallback: создаем новый event loop
        return asyncio.run(coro)


# ==================== Async версии (рекомендуется для async контекста) ====================

async def get_user_balance_async(user_id: int) -> float:
    """Получить баланс пользователя (async)"""
    return await get_user_balance_async_service(user_id)


async def get_user_language_async(user_id: int) -> str:
    """Получить язык пользователя (async)"""
    return await get_user_language_async_service(user_id)


# get_is_admin уже синхронный
def get_is_admin(user_id: int) -> bool:
    """Проверить является ли пользователь админом (синхронно)"""
    return get_is_admin_service(user_id)


# ==================== Синхронные версии (для обратной совместимости) ====================

def get_user_balance(user_id: int) -> float:
    """
    Получить баланс пользователя (синхронная обертка).
    
    ВНИМАНИЕ: Эта функция блокирует event loop!
    Используйте get_user_balance_async() в async контексте.
    """
    return _run_async_safe(get_user_balance_async_service(user_id))


def get_user_language(user_id: int) -> str:
    """
    Получить язык пользователя (синхронная обертка).
    
    ВНИМАНИЕ: Эта функция блокирует event loop!
    Используйте get_user_language_async() в async контексте.
    """
    return _run_async_safe(get_user_language_async_service(user_id))


def get_user_free_generations_remaining(user_id: int) -> int:
    """
    Получить оставшиеся бесплатные генерации (синхронная обертка).
    
    ВНИМАНИЕ: Эта функция блокирует event loop!
    Используйте async версию в async контексте.
    """
    return _run_async_safe(get_user_free_generations_remaining_service(user_id))


def has_claimed_gift(user_id: int) -> bool:
    """
    Проверить получение подарка (синхронная обертка).
    
    ВНИМАНИЕ: Эта функция блокирует event loop!
    Используйте async версию в async контексте.
    """
    return _run_async_safe(has_claimed_gift_service(user_id))


def get_admin_limit(user_id: int) -> float:
    """
    Получить лимит админа (синхронная обертка).
    
    ВНИМАНИЕ: Эта функция блокирует event loop!
    Используйте async версию в async контексте.
    """
    return _run_async_safe(get_admin_limit_service(user_id))


def get_admin_spent(user_id: int) -> float:
    """
    Получить потраченную сумму админа (синхронная обертка).
    
    ВНИМАНИЕ: Эта функция блокирует event loop!
    Используйте async версию в async контексте.
    """
    return _run_async_safe(get_admin_spent_service(user_id))


def get_admin_remaining(user_id: int) -> float:
    """
    Получить оставшийся лимит админа (синхронная обертка).
    
    ВНИМАНИЕ: Эта функция блокирует event loop!
    Используйте async версию в async контексте.
    """
    return _run_async_safe(get_admin_remaining_service(user_id))

