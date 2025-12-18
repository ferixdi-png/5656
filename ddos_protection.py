"""
Модуль для защиты от DDOS-атак.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from collections import defaultdict, deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Хранилище для отслеживания запросов
_request_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
_rate_limits: Dict[str, Dict[str, Any]] = {}


def check_rate_limit(
    user_id: int,
    action: str = 'generation',
    max_requests: int = 10,
    time_window: int = 60
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, не превышен ли лимит запросов для пользователя.
    
    Args:
        user_id: ID пользователя
        action: Тип действия
        max_requests: Максимальное количество запросов
        time_window: Временное окно в секундах
    
    Returns:
        (разрешено, сообщение_об_ошибке)
    """
    current_time = time.time()
    key = f"{user_id}:{action}"
    
    # Получаем историю запросов
    if key not in _request_history:
        _request_history[key] = deque(maxlen=max_requests * 2)
    
    request_times = _request_history[key]
    
    # Удаляем старые запросы
    while request_times and current_time - request_times[0] > time_window:
        request_times.popleft()
    
    # Проверяем лимит
    if len(request_times) >= max_requests:
        wait_time = int(time_window - (current_time - request_times[0]))
        return False, f"Превышен лимит запросов. Попробуйте через {wait_time} секунд."
    
    # Добавляем текущий запрос
    request_times.append(current_time)
    
    return True, None


def check_suspicious_activity(user_id: int) -> bool:
    """
    Проверяет наличие подозрительной активности.
    
    Args:
        user_id: ID пользователя
    
    Returns:
        True, если активность подозрительна
    """
    current_time = time.time()
    
    # Проверяем различные типы действий
    actions = ['generation', 'api_call', 'message']
    suspicious_count = 0
    
    for action in actions:
        key = f"{user_id}:{action}"
        if key in _request_history:
            request_times = _request_history[key]
            
            # Проверяем количество запросов за последнюю минуту
            recent_requests = [
                t for t in request_times
                if current_time - t < 60
            ]
            
            if len(recent_requests) > 20:  # Более 20 запросов в минуту
                suspicious_count += 1
    
    # Если подозрительная активность в нескольких типах действий
    return suspicious_count >= 2


def require_captcha(user_id: int, action: str = 'generation') -> bool:
    """
    Определяет, требуется ли CAPTCHA для действия.
    
    Args:
        user_id: ID пользователя
        action: Тип действия
    
    Returns:
        True, если требуется CAPTCHA
    """
    # CAPTCHA требуется для:
    # - Подозрительной активности
    # - Высоких цен генераций
    # - Важных операций
    
    if check_suspicious_activity(user_id):
        return True
    
    important_actions = ['settings_change', 'balance_transfer', 'admin_action']
    if action in important_actions:
        return True
    
    return False


def verify_captcha(user_id: int, captcha_response: str) -> bool:
    """
    Проверяет ответ CAPTCHA.
    
    Args:
        user_id: ID пользователя
        captcha_response: Ответ пользователя на CAPTCHA
    
    Returns:
        True, если CAPTCHA верна
    """
    # В реальной реализации здесь будет проверка через сервис CAPTCHA
    # Пока простая проверка
    if captcha_response and len(captcha_response) > 0:
        logger.info(f"✅ CAPTCHA проверена для пользователя {user_id}")
        return True
    
    return False


def get_rate_limit_info(user_id: int, action: str = 'generation') -> Dict[str, Any]:
    """
    Возвращает информацию о лимитах для пользователя.
    
    Args:
        user_id: ID пользователя
        action: Тип действия
    
    Returns:
        Словарь с информацией о лимитах
    """
    key = f"{user_id}:{action}"
    
    if key not in _request_history:
        return {
            'current_requests': 0,
            'max_requests': 10,
            'time_window': 60,
            'remaining': 10
        }
    
    request_times = _request_history[key]
    current_time = time.time()
    
    # Подсчитываем запросы за последнюю минуту
    recent_requests = [
        t for t in request_times
        if current_time - t < 60
    ]
    
    return {
        'current_requests': len(recent_requests),
        'max_requests': 10,
        'time_window': 60,
        'remaining': max(0, 10 - len(recent_requests))
    }

