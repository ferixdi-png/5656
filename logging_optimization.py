"""
Модуль для оптимизации логирования.
Включает фильтрацию дубликатов, структурированное логирование и управление уровнем логирования.
"""

import logging
from typing import Dict, Any, Optional
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Отслеживание последних логов для предотвращения дубликатов
_recent_logs: deque = deque(maxlen=100)
_log_counts: Dict[str, int] = {}
_log_threshold = 5  # Максимальное количество одинаковых логов за период


def should_log_message(message: str, level: str = 'INFO') -> bool:
    """
    Определяет, нужно ли логировать сообщение (предотвращает дубликаты).
    
    Args:
        message: Текст сообщения
        level: Уровень логирования
    
    Returns:
        True, если нужно логировать
    """
    import time
    
    current_time = time.time()
    message_hash = hash(f"{level}:{message}")
    
    # Удаляем старые записи (старше 60 секунд)
    while _recent_logs and current_time - _recent_logs[0]['time'] > 60:
        old_log = _recent_logs.popleft()
        old_hash = old_log['hash']
        if old_hash in _log_counts:
            _log_counts[old_hash] -= 1
            if _log_counts[old_hash] <= 0:
                del _log_counts[old_hash]
    
    # Проверяем количество одинаковых логов
    count = _log_counts.get(message_hash, 0)
    if count >= _log_threshold:
        return False  # Слишком много одинаковых логов
    
    # Добавляем в историю
    _recent_logs.append({
        'hash': message_hash,
        'time': current_time,
        'message': message
    })
    _log_counts[message_hash] = count + 1
    
    return True


def log_optimized(level: str, message: str, *args, **kwargs):
    """
    Оптимизированное логирование с фильтрацией дубликатов.
    
    Args:
        level: Уровень логирования
        message: Сообщение
        *args: Дополнительные аргументы
        **kwargs: Дополнительные ключевые аргументы
    """
    if not should_log_message(message, level):
        return
    
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, *args, **kwargs)


def log_error_structured(
    error: Exception,
    context: Dict[str, Any],
    user_id: Optional[int] = None,
    operation: Optional[str] = None
):
    """
    Структурированное логирование ошибок.
    
    Args:
        error: Исключение
        context: Контекст ошибки
        user_id: ID пользователя (опционально)
        operation: Операция, при которой произошла ошибка (опционально)
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context,
        'timestamp': datetime.now().isoformat()
    }
    
    if user_id:
        error_info['user_id'] = user_id
    
    if operation:
        error_info['operation'] = operation
    
    # Логируем только если не было слишком много похожих ошибок
    message = f"❌ {operation or 'Error'}: {error_info['error_type']} - {error_info['error_message']}"
    if should_log_message(message, 'ERROR'):
        logger.error(
            f"❌ {operation or 'Error'}: {error_info}",
            exc_info=True
        )


def log_api_call_optimized(
    endpoint: str,
    method: str,
    duration: float,
    success: bool,
    error: Optional[str] = None
):
    """
    Оптимизированное логирование API вызовов.
    
    Args:
        endpoint: Endpoint API
        method: HTTP метод
        duration: Длительность запроса
        success: Успешность запроса
        error: Сообщение об ошибке (если есть)
    """
    if success:
        if duration > 2.0:
            message = f"⏱️ API {method} {endpoint}: {duration:.2f}с (медленно)"
            log_optimized('WARNING', message)
        else:
            message = f"✅ API {method} {endpoint}: {duration:.2f}с"
            log_optimized('DEBUG', message)
    else:
        message = f"❌ API {method} {endpoint} failed: {error}"
        log_optimized('ERROR', message)


def cleanup_log_history():
    """Очищает историю логов."""
    _recent_logs.clear()
    _log_counts.clear()
    logger.debug("🧹 История логов очищена")

