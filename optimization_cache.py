"""
Модуль для кеширования данных KIE API и оптимизации производительности.
Включает кеширование моделей, параметров и результатов запросов.
"""

import time
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from functools import lru_cache
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Кеш для моделей из KIE API
_models_cache: Optional[List[Dict[str, Any]]] = None
_models_cache_time: float = 0
MODELS_CACHE_TTL = 300  # 5 минут

# Кеш для информации о конкретных моделях
_model_info_cache: Dict[str, Dict[str, Any]] = {}
_model_info_cache_time: Dict[str, float] = {}
MODEL_INFO_CACHE_TTL = 600  # 10 минут

# Кеш для параметров моделей (input_schema)
_model_params_cache: Dict[str, Dict[str, Any]] = {}
_model_params_cache_time: Dict[str, float] = {}
MODEL_PARAMS_CACHE_TTL = 600  # 10 минут

# Кеш для результатов запросов (для одинаковых параметров)
_request_cache: Dict[str, Dict[str, Any]] = {}
_request_cache_time: Dict[str, float] = {}
REQUEST_CACHE_TTL = 60  # 1 минута (для предотвращения дублирующих запросов)


def get_cache_key_for_request(model_id: str, params: Dict[str, Any]) -> str:
    """Создает ключ кеша для запроса на основе model_id и параметров."""
    # Сортируем параметры для консистентности
    sorted_params = json.dumps(params, sort_keys=True)
    cache_input = f"{model_id}:{sorted_params}"
    return hashlib.md5(cache_input.encode()).hexdigest()


def get_cached_models() -> Optional[List[Dict[str, Any]]]:
    """Получает закешированный список моделей, если он еще актуален."""
    current_time = time.time()
    if _models_cache is not None and (current_time - _models_cache_time) < MODELS_CACHE_TTL:
        return _models_cache
    return None


def set_cached_models(models: List[Dict[str, Any]]):
    """Сохраняет список моделей в кеш."""
    global _models_cache, _models_cache_time
    _models_cache = models
    _models_cache_time = time.time()
    logger.info(f"✅ Кеш моделей обновлен: {len(models)} моделей")


def get_cached_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Получает закешированную информацию о модели."""
    current_time = time.time()
    if model_id in _model_info_cache:
        cache_time = _model_info_cache_time.get(model_id, 0)
        if (current_time - cache_time) < MODEL_INFO_CACHE_TTL:
            return _model_info_cache[model_id]
    return None


def set_cached_model_info(model_id: str, model_info: Dict[str, Any]):
    """Сохраняет информацию о модели в кеш."""
    _model_info_cache[model_id] = model_info
    _model_info_cache_time[model_id] = time.time()
    logger.debug(f"✅ Кеш информации о модели обновлен: {model_id}")


def get_cached_model_params(model_id: str) -> Optional[Dict[str, Any]]:
    """Получает закешированные параметры модели (input_schema)."""
    current_time = time.time()
    if model_id in _model_params_cache:
        cache_time = _model_params_cache_time.get(model_id, 0)
        if (current_time - cache_time) < MODEL_PARAMS_CACHE_TTL:
            return _model_params_cache[model_id]
    return None


def set_cached_model_params(model_id: str, params: Dict[str, Any]):
    """Сохраняет параметры модели в кеш."""
    _model_params_cache[model_id] = params
    _model_params_cache_time[model_id] = time.time()
    logger.debug(f"✅ Кеш параметров модели обновлен: {model_id}")


def get_cached_request(cache_key: str) -> Optional[Dict[str, Any]]:
    """Получает закешированный результат запроса."""
    current_time = time.time()
    if cache_key in _request_cache:
        cache_time = _request_cache_time.get(cache_key, 0)
        if (current_time - cache_time) < REQUEST_CACHE_TTL:
            return _request_cache[cache_key]
        else:
            # Удаляем устаревший кеш
            del _request_cache[cache_key]
            if cache_key in _request_cache_time:
                del _request_cache_time[cache_key]
    return None


def set_cached_request(cache_key: str, result: Dict[str, Any]):
    """Сохраняет результат запроса в кеш."""
    _request_cache[cache_key] = result
    _request_cache_time[cache_key] = time.time()
    logger.debug(f"✅ Результат запроса закеширован: {cache_key[:16]}...")


def clear_cache():
    """Очищает весь кеш."""
    global _models_cache, _models_cache_time
    global _model_info_cache, _model_info_cache_time
    global _model_params_cache, _model_params_cache_time
    global _request_cache, _request_cache_time
    
    _models_cache = None
    _models_cache_time = 0
    _model_info_cache.clear()
    _model_info_cache_time.clear()
    _model_params_cache.clear()
    _model_params_cache_time.clear()
    _request_cache.clear()
    _request_cache_time.clear()
    
    logger.info("✅ Весь кеш очищен")


def clear_old_cache():
    """Очищает устаревшие записи из кеша."""
    current_time = time.time()
    
    # Очистка кеша моделей
    if _models_cache is not None and (current_time - _models_cache_time) >= MODELS_CACHE_TTL:
        global _models_cache, _models_cache_time
        _models_cache = None
        _models_cache_time = 0
    
    # Очистка кеша информации о моделях
    expired_models = [
        model_id for model_id, cache_time in _model_info_cache_time.items()
        if (current_time - cache_time) >= MODEL_INFO_CACHE_TTL
    ]
    for model_id in expired_models:
        del _model_info_cache[model_id]
        del _model_info_cache_time[model_id]
    
    # Очистка кеша параметров моделей
    expired_params = [
        model_id for model_id, cache_time in _model_params_cache_time.items()
        if (current_time - cache_time) >= MODEL_PARAMS_CACHE_TTL
    ]
    for model_id in expired_params:
        del _model_params_cache[model_id]
        del _model_params_cache_time[model_id]
    
    # Очистка кеша запросов
    expired_requests = [
        cache_key for cache_key, cache_time in _request_cache_time.items()
        if (current_time - cache_time) >= REQUEST_CACHE_TTL
    ]
    for cache_key in expired_requests:
        del _request_cache[cache_key]
        del _request_cache_time[cache_key]
    
    if expired_models or expired_params or expired_requests:
        logger.info(f"✅ Очищено устаревших записей: models={len(expired_models)}, params={len(expired_params)}, requests={len(expired_requests)}")


def get_cache_stats() -> Dict[str, Any]:
    """Возвращает статистику кеша."""
    current_time = time.time()
    
    return {
        'models_cached': _models_cache is not None,
        'models_cache_age': current_time - _model_info_cache_time if _models_cache_time else None,
        'model_info_count': len(_model_info_cache),
        'model_params_count': len(_model_params_cache),
        'request_cache_count': len(_request_cache),
        'total_cache_size': (
            len(_model_info_cache) +
            len(_model_params_cache) +
            len(_request_cache)
        )
    }

