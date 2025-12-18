"""
Модуль для предобработки запросов для часто используемых операций.
"""

import logging
from typing import Dict, Any, Optional
import hashlib
import json
import time

logger = logging.getLogger(__name__)

# Кеш предобработанных запросов
_preprocessed_cache: Dict[str, Dict[str, Any]] = {}
_cache_timestamps: Dict[str, float] = {}
PREPROCESSING_CACHE_TTL = 300  # 5 минут


def preprocess_request(request_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Предобрабатывает запрос для оптимизации.
    
    Args:
        request_type: Тип запроса
        params: Параметры запроса
    
    Returns:
        Предобработанные параметры
    """
    # Создаем ключ кеша
    cache_key = _create_cache_key(request_type, params)
    
    # Проверяем кеш
    current_time = time.time()
    if cache_key in _preprocessed_cache:
        cache_time = _cache_timestamps.get(cache_key, 0)
        if (current_time - cache_time) < PREPROCESSING_CACHE_TTL:
            logger.debug(f"✅ Использован предобработанный запрос: {request_type}")
            return _preprocessed_cache[cache_key]
    
    # Предобрабатываем запрос
    preprocessed = params.copy()
    
    # Оптимизация для разных типов запросов
    if request_type == 'list_models':
        # Для списка моделей можно добавить фильтрацию
        pass
    
    elif request_type == 'create_task':
        # Для создания задачи можно оптимизировать параметры
        preprocessed = _optimize_generation_params(preprocessed)
    
    # Сохраняем в кеш
    _preprocessed_cache[cache_key] = preprocessed
    _cache_timestamps[cache_key] = current_time
    
    return preprocessed


def _create_cache_key(request_type: str, params: Dict[str, Any]) -> str:
    """Создает ключ кеша для запроса."""
    sorted_params = json.dumps(params, sort_keys=True)
    cache_input = f"{request_type}:{sorted_params}"
    return hashlib.md5(cache_input.encode()).hexdigest()


def _optimize_generation_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Оптимизирует параметры генерации."""
    optimized = params.copy()
    
    # Оптимизация разрешения
    if 'resolution' in optimized:
        resolution = str(optimized['resolution']).lower()
        # Нормализуем разрешение
        if '1080' in resolution:
            optimized['resolution'] = '1080p'
        elif '720' in resolution:
            optimized['resolution'] = '720p'
        elif '480' in resolution:
            optimized['resolution'] = '480p'
    
    # Оптимизация aspect_ratio
    if 'aspect_ratio' in optimized:
        aspect_ratio = str(optimized['aspect_ratio']).lower()
        # Нормализуем соотношение сторон
        if '16:9' in aspect_ratio or '16/9' in aspect_ratio:
            optimized['aspect_ratio'] = '16:9'
        elif '1:1' in aspect_ratio or '1/1' in aspect_ratio:
            optimized['aspect_ratio'] = '1:1'
        elif '4:3' in aspect_ratio or '4/3' in aspect_ratio:
            optimized['aspect_ratio'] = '4:3'
    
    return optimized


def clear_preprocessing_cache():
    """Очищает кеш предобработанных запросов."""
    _preprocessed_cache.clear()
    _cache_timestamps.clear()
    logger.info("🧹 Кеш предобработки очищен")

