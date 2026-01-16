"""
User service - чистые функции для работы с пользователями
БЕЗ зависимостей от bot_kie.py (устраняет circular imports)
"""

import logging
from typing import Optional
from app.storage import get_storage
from app.config import get_settings

logger = logging.getLogger(__name__)

# Глобальный кэш для admin проверок (чтобы не обращаться к storage каждый раз)
_admin_cache: dict[int, bool] = {}


def _get_storage():
    """Получить storage instance"""
    return get_storage()


async def get_user_balance(user_id: int) -> float:
    """Получить баланс пользователя"""
    storage = _get_storage()
    return await storage.get_user_balance(user_id)


async def set_user_balance(user_id: int, amount: float) -> None:
    """Установить баланс пользователя"""
    storage = _get_storage()
    await storage.set_user_balance(user_id, amount)


async def add_user_balance(user_id: int, amount: float) -> float:
    """Добавить к балансу пользователя"""
    storage = _get_storage()
    return await storage.add_user_balance(user_id, amount)


async def subtract_user_balance(user_id: int, amount: float) -> bool:
    """Вычесть из баланса пользователя"""
    storage = _get_storage()
    return await storage.subtract_user_balance(user_id, amount)


async def get_user_language(user_id: int) -> str:
    """Получить язык пользователя"""
    storage = _get_storage()
    return await storage.get_user_language(user_id)


async def set_user_language(user_id: int, language: str) -> None:
    """Установить язык пользователя"""
    storage = _get_storage()
    await storage.set_user_language(user_id, language)


async def has_claimed_gift(user_id: int) -> bool:
    """Проверить получение подарка"""
    storage = _get_storage()
    return await storage.has_claimed_gift(user_id)


async def set_gift_claimed(user_id: int) -> None:
    """Отметить получение подарка"""
    storage = _get_storage()
    await storage.set_gift_claimed(user_id)


async def get_user_free_generations_remaining(user_id: int) -> int:
    """Получить оставшиеся бесплатные генерации"""
    storage = _get_storage()
    return await storage.get_user_free_generations_remaining(user_id)


def get_is_admin(user_id: int) -> bool:
    """Проверить является ли пользователь админом (синхронно)"""
    settings = get_settings()
    return user_id == settings.admin_id


async def get_admin_limit(user_id: int) -> float:
    """Получить лимит админа"""
    storage = _get_storage()
    return await storage.get_admin_limit(user_id)


async def get_admin_spent(user_id: int) -> float:
    """Получить потраченную сумму админа"""
    storage = _get_storage()
    return await storage.get_admin_spent(user_id)


async def get_admin_remaining(user_id: int) -> float:
    """Получить оставшийся лимит админа"""
    storage = _get_storage()
    return await storage.get_admin_remaining(user_id)


# Синхронные обертки для обратной совместимости (используют asyncio.run внутри)
# ВНИМАНИЕ: Эти функции блокируют event loop! Используйте async версии в async контексте
def get_user_balance_sync(user_id: int) -> float:
    """Синхронная обертка для get_user_balance (для обратной совместимости)"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если loop уже запущен, используем run_in_executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_user_balance(user_id))
                return future.result()
        else:
            return loop.run_until_complete(get_user_balance(user_id))
    except RuntimeError:
        # Нет event loop, создаем новый
        return asyncio.run(get_user_balance(user_id))


def get_user_language_sync(user_id: int) -> str:
    """Синхронная обертка для get_user_language (для обратной совместимости)"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_user_language(user_id))
                return future.result()
        else:
            return loop.run_until_complete(get_user_language(user_id))
    except RuntimeError:
        return asyncio.run(get_user_language(user_id))


