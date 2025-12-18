"""
Модуль для оптимизации взаимодействия с API.
Включает кеширование, устранение дубликатов и оптимизацию запросов.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Set
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

# Отслеживание активных запросов для предотвращения дубликатов
_active_requests: Dict[str, asyncio.Task] = {}
_request_lock = asyncio.Lock()


async def deduplicate_api_request(
    request_key: str,
    request_func,
    timeout: float = 30.0
) -> Any:
    """
    Предотвращает дублирование одинаковых API запросов.
    
    Args:
        request_key: Уникальный ключ запроса
        request_func: Функция для выполнения запроса
        timeout: Таймаут для ожидания результата
    
    Returns:
        Результат запроса
    """
    async with _request_lock:
        # Проверяем, есть ли уже активный запрос с таким ключом
        if request_key in _active_requests:
            existing_task = _active_requests[request_key]
            
            # Если задача еще выполняется, ждем её результат
            if not existing_task.done():
                logger.debug(f"🔄 Ожидание результата существующего запроса: {request_key}")
                try:
                    result = await asyncio.wait_for(existing_task, timeout=timeout)
                    return result
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Таймаут ожидания запроса {request_key}")
                    # Удаляем задачу из активных
                    del _active_requests[request_key]
                except Exception as e:
                    logger.error(f"❌ Ошибка при ожидании запроса {request_key}: {e}")
                    del _active_requests[request_key]
        
        # Создаем новую задачу
        task = asyncio.create_task(request_func())
        _active_requests[request_key] = task
        
        try:
            result = await task
            return result
        finally:
            # Удаляем задачу после завершения
            if request_key in _active_requests:
                del _active_requests[request_key]


def create_request_key(operation: str, **kwargs) -> str:
    """
    Создает уникальный ключ для запроса.
    
    Args:
        operation: Тип операции
        **kwargs: Параметры запроса
    
    Returns:
        Уникальный ключ
    """
    import hashlib
    import json
    
    # Сортируем параметры для консистентности
    sorted_params = json.dumps(kwargs, sort_keys=True)
    key_input = f"{operation}:{sorted_params}"
    return hashlib.md5(key_input.encode()).hexdigest()


async def cached_api_request(
    cache_key: str,
    request_func,
    cache_ttl: float = 300.0,
    use_cache: bool = True
) -> Any:
    """
    Выполняет API запрос с кешированием.
    
    Args:
        cache_key: Ключ кеша
        request_func: Функция для выполнения запроса
        cache_ttl: Время жизни кеша в секундах
        use_cache: Использовать ли кеш
    
    Returns:
        Результат запроса
    """
    try:
        from optimization_cache import get_cached_request, set_cached_request
        
        if use_cache:
            # Проверяем кеш
            cached = get_cached_request(cache_key)
            if cached is not None:
                logger.debug(f"✅ Использован кеш для запроса: {cache_key[:16]}...")
                return cached
        
        # Выполняем запрос
        result = await request_func()
        
        # Сохраняем в кеш
        if use_cache and result:
            set_cached_request(cache_key, result, cache_ttl)
        
        return result
        
    except ImportError:
        # Если кеш не доступен, просто выполняем запрос
        return await request_func()
    except Exception as e:
        logger.error(f"❌ Ошибка при кешированном запросе: {e}", exc_info=True)
        return await request_func()


def validate_api_params_before_request(model_id: str, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Валидирует параметры перед отправкой запроса к API.
    
    Args:
        model_id: ID модели
        params: Параметры
    
    Returns:
        (валидно, сообщение_об_ошибке)
    """
    # Проверяем обязательные параметры
    if not model_id:
        return False, "Model ID не может быть пустым"
    
    # Проверяем наличие промпта для текстовых моделей
    if 'prompt' not in params and 'text' not in params:
        # Для некоторых моделей промпт не обязателен
        if 'image' not in params and 'video' not in params:
            return False, "Необходимо указать промпт, изображение или видео"
    
    # Проверяем длину промпта
    prompt = params.get('prompt') or params.get('text', '')
    if prompt and len(prompt) > 5000:
        return False, "Промпт слишком длинный (максимум 5000 символов)"
    
    return True, None

