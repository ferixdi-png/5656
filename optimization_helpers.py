"""
Вспомогательные функции для оптимизации производительности.
Включает логирование времени отклика, очистку старых сессий и другие утилиты.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ResponseTimeLogger:
    """Класс для логирования времени отклика API."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            if elapsed > 1.0:
                logger.warning(f"⏱️ {self.operation_name} заняло {elapsed:.2f}с (медленно)")
            elif elapsed > 0.5:
                logger.info(f"⏱️ {self.operation_name} заняло {elapsed:.2f}с")
            else:
                logger.debug(f"⏱️ {self.operation_name} заняло {elapsed:.2f}с")
        return False


def log_api_response_time(operation_name: str, elapsed_time: float):
    """Логирует время отклика API с соответствующим уровнем логирования."""
    if elapsed_time > 5.0:
        logger.error(f"❌ {operation_name} заняло {elapsed_time:.2f}с (критически медленно)")
    elif elapsed_time > 2.0:
        logger.warning(f"⚠️ {operation_name} заняло {elapsed_time:.2f}с (медленно)")
    elif elapsed_time > 1.0:
        logger.info(f"⏱️ {operation_name} заняло {elapsed_time:.2f}с")
    else:
        logger.debug(f"⏱️ {operation_name} заняло {elapsed_time:.2f}с")


def cleanup_old_sessions(user_sessions: Dict[int, Dict[str, Any]], max_age_hours: int = 24):
    """
    Очищает старые сессии пользователей.
    
    Args:
        user_sessions: Словарь сессий пользователей
        max_age_hours: Максимальный возраст сессии в часах (по умолчанию 24)
    """
    current_time = datetime.now()
    expired_sessions = []
    
    for user_id, session in user_sessions.items():
        # Проверяем время создания сессии
        session_time = session.get('created_at')
        if session_time:
            if isinstance(session_time, str):
                try:
                    session_time = datetime.fromisoformat(session_time)
                except:
                    # Если не удалось распарсить, считаем сессию устаревшей
                    expired_sessions.append(user_id)
                    continue
            
            age = current_time - session_time
            if age > timedelta(hours=max_age_hours):
                expired_sessions.append(user_id)
        else:
            # Если нет времени создания, считаем сессию устаревшей
            expired_sessions.append(user_id)
    
    # Удаляем устаревшие сессии
    for user_id in expired_sessions:
        del user_sessions[user_id]
        logger.info(f"🧹 Удалена устаревшая сессия пользователя {user_id}")
    
    if expired_sessions:
        logger.info(f"✅ Очищено {len(expired_sessions)} устаревших сессий")
    
    return len(expired_sessions)


def get_session_stats(user_sessions: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """Возвращает статистику сессий."""
    current_time = datetime.now()
    active_sessions = 0
    old_sessions = 0
    
    for session in user_sessions.values():
        session_time = session.get('created_at')
        if session_time:
            if isinstance(session_time, str):
                try:
                    session_time = datetime.fromisoformat(session_time)
                except:
                    old_sessions += 1
                    continue
            
            age = current_time - session_time
            if age < timedelta(hours=1):
                active_sessions += 1
            else:
                old_sessions += 1
        else:
            old_sessions += 1
    
    return {
        'total_sessions': len(user_sessions),
        'active_sessions': active_sessions,
        'old_sessions': old_sessions
    }

