"""
Safe access helpers for Telegram objects to prevent AttributeError.

CRITICAL: All handlers should use these helpers to safely access
callback.from_user, message.from_user, etc.
"""
import logging
from typing import Optional
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger(__name__)


def safe_get_user_id(callback: Optional[CallbackQuery] = None, message: Optional[Message] = None) -> Optional[int]:
    """
    Safely get user_id from callback or message.
    
    Returns:
        user_id if available, None otherwise
    """
    if callback and callback.from_user:
        return callback.from_user.id
    if message and message.from_user:
        return message.from_user.id
    return None


def safe_get_chat_id(callback: Optional[CallbackQuery] = None, message: Optional[Message] = None) -> Optional[int]:
    """
    Safely get chat_id from callback or message.
    
    Returns:
        chat_id if available, None otherwise
    """
    if callback and callback.message and callback.message.chat:
        return callback.message.chat.id
    if message and message.chat:
        return message.chat.id
    return None


def safe_get_username(callback: Optional[CallbackQuery] = None, message: Optional[Message] = None) -> Optional[str]:
    """
    Safely get username from callback or message.
    
    Returns:
        username if available, None otherwise
    """
    if callback and callback.from_user:
        return callback.from_user.username
    if message and message.from_user:
        return message.from_user.username
    return None


def safe_get_first_name(callback: Optional[CallbackQuery] = None, message: Optional[Message] = None) -> Optional[str]:
    """
    Safely get first_name from callback or message.
    
    Returns:
        first_name if available, None otherwise
    """
    if callback and callback.from_user:
        return callback.from_user.first_name
    if message and message.from_user:
        return message.from_user.first_name
    return None


def validate_callback(callback: CallbackQuery) -> tuple[bool, Optional[str]]:
    """
    Validate callback has required fields.
    
    Returns:
        (is_valid, error_message)
    """
    if not callback:
        return False, "Callback is None"
    if not callback.from_user:
        return False, "callback.from_user is None"
    if not callback.message:
        return False, "callback.message is None"
    return True, None


def validate_message(message: Message) -> tuple[bool, Optional[str]]:
    """
    Validate message has required fields.
    
    Returns:
        (is_valid, error_message)
    """
    if not message:
        return False, "Message is None"
    if not message.from_user:
        return False, "message.from_user is None"
    return True, None

