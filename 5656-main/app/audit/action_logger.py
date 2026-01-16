"""
Action audit logger - tracks user actions (button clicks, bot responses) for admin review.

Stores last 10 actions per user for quick admin diagnostics.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from collections import deque
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# In-memory storage for recent actions (last 100 actions total)
# In production, could be moved to DB
_action_log: deque = deque(maxlen=100)


@dataclass
class ActionLogEntry:
    """Single action log entry."""
    timestamp: str
    user_id: int
    chat_id: int
    action_type: str  # "button_click", "command", "message"
    action_data: str  # callback_data, command, or message text
    bot_response: Optional[str] = None  # What bot responded
    handler_name: Optional[str] = None  # Handler that processed the action
    success: bool = True  # Whether action succeeded
    error: Optional[str] = None  # Error message if failed


def log_action(
    user_id: int,
    chat_id: int,
    action_type: str,
    action_data: str,
    bot_response: Optional[str] = None,
    handler_name: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None
) -> None:
    """
    Log a user action for audit trail.
    
    Args:
        user_id: User ID
        chat_id: Chat ID
        action_type: Type of action ("button_click", "command", "message")
        action_data: Action data (callback_data, command, message text)
        bot_response: What bot responded (optional)
        handler_name: Handler that processed the action (optional)
        success: Whether action succeeded
        error: Error message if failed (optional)
    """
    entry = ActionLogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id=user_id,
        chat_id=chat_id,
        action_type=action_type,
        action_data=action_data,
        bot_response=bot_response,
        handler_name=handler_name,
        success=success,
        error=error
    )
    
    _action_log.append(entry)
    
    logger.debug(
        f"[AUDIT] Action logged | User: {user_id} | Type: {action_type} | "
        f"Data: {action_data[:50]} | Success: {success}"
    )


def get_recent_actions(limit: int = 10, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get recent actions for audit.
    
    Args:
        limit: Maximum number of actions to return
        user_id: Filter by user ID (optional)
    
    Returns:
        List of action log entries (most recent first)
    """
    actions = list(_action_log)
    
    # Filter by user if specified
    if user_id is not None:
        actions = [a for a in actions if a.user_id == user_id]
    
    # Sort by timestamp (most recent first)
    actions.sort(key=lambda x: x.timestamp, reverse=True)
    
    # Return limited results
    return [asdict(a) for a in actions[:limit]]


def get_user_recent_actions(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent actions for specific user.
    
    Args:
        user_id: User ID
        limit: Maximum number of actions to return
    
    Returns:
        List of action log entries (most recent first)
    """
    return get_recent_actions(limit=limit, user_id=user_id)


def format_actions_for_admin(actions: List[Dict[str, Any]]) -> str:
    """
    Format action log for admin display.
    
    Args:
        actions: List of action log entries
    
    Returns:
        Formatted string for Telegram message
    """
    if not actions:
        return "📜 <b>Лог действий пуст</b>\n\nНет зарегистрированных действий."
    
    text = f"📜 <b>Последние {len(actions)} действий</b>\n\n"
    
    for i, action in enumerate(actions, 1):
        timestamp = action.get("timestamp", "unknown")
        # Parse timestamp and format for display
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%H:%M:%S")
        except:
            time_str = timestamp[:8] if len(timestamp) >= 8 else timestamp
        
        user_id = action.get("user_id", "unknown")
        action_type = action.get("action_type", "unknown")
        action_data = action.get("action_data", "")[:50]  # Truncate long data
        success = action.get("success", True)
        bot_response = action.get("bot_response")
        error = action.get("error")
        
        status_emoji = "✅" if success else "❌"
        type_emoji = {
            "button_click": "🔘",
            "command": "⌨️",
            "message": "💬"
        }.get(action_type, "📝")
        
        text += (
            f"{i}. {status_emoji} {type_emoji} <b>{time_str}</b>\n"
            f"   User: <code>{user_id}</code> | {action_type}\n"
            f"   Действие: <code>{action_data}</code>\n"
        )
        
        if bot_response:
            response_preview = bot_response[:40] + "..." if len(bot_response) > 40 else bot_response
            text += f"   Ответ: {response_preview}\n"
        
        if error:
            text += f"   ⚠️ Ошибка: {error[:50]}\n"
        
        text += "\n"
    
    return text

