"""
Services module - бизнес-логика без зависимостей от bot_kie.py
"""

from app.services.user_service import (
    get_user_balance,
    set_user_balance,
    add_user_balance,
    subtract_user_balance,
    get_user_language,
    set_user_language,
    has_claimed_gift,
    set_gift_claimed,
    get_user_free_generations_remaining,
    get_is_admin,
    get_admin_limit,
    get_admin_spent,
    get_admin_remaining,
)

__all__ = [
    'get_user_balance',
    'set_user_balance',
    'add_user_balance',
    'subtract_user_balance',
    'get_user_language',
    'set_user_language',
    'has_claimed_gift',
    'set_gift_claimed',
    'get_user_free_generations_remaining',
    'get_is_admin',
    'get_admin_limit',
    'get_admin_spent',
    'get_admin_remaining',
]


