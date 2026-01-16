"""
User state module - синхронные и async функции для работы с пользователями
БЕЗ зависимостей от bot_kie.py (устраняет circular imports)
"""

from app.state.user_state import (
    # Async версии (рекомендуется)
    get_user_balance_async,
    get_user_language_async,
    get_is_admin,
    
    # Синхронные версии (для обратной совместимости)
    get_user_balance,
    get_user_language,
    get_user_free_generations_remaining,
    has_claimed_gift,
    get_admin_limit,
    get_admin_spent,
    get_admin_remaining,
)

__all__ = [
    'get_user_balance',
    'get_user_balance_async',
    'get_user_language',
    'get_user_language_async',
    'get_is_admin',
    'get_user_free_generations_remaining',
    'has_claimed_gift',
    'get_admin_limit',
    'get_admin_spent',
    'get_admin_remaining',
]

