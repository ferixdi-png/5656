"""
Модуль для кеширования результатов генерации.
Позволяет избежать повторных запросов к API для одинаковых параметров.
"""

import time
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Кеш результатов генерации
_generation_results_cache: Dict[str, Dict[str, Any]] = {}
_cache_timestamps: Dict[str, float] = {}
RESULTS_CACHE_TTL = 3600  # 1 час (результаты генерации обычно не меняются)


def get_cache_key_for_generation(model_id: str, params: Dict[str, Any]) -> str:
    """Создает ключ кеша для генерации на основе model_id и параметров."""
    # Нормализуем параметры (сортируем, убираем None)
    normalized_params = {
        k: v for k, v in sorted(params.items())
        if v is not None
    }
    cache_input = f"{model_id}:{json.dumps(normalized_params, sort_keys=True)}"
    return hashlib.md5(cache_input.encode()).hexdigest()


def get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """Получает закешированный результат генерации."""
    current_time = time.time()
    
    if cache_key in _generation_results_cache:
        cache_time = _cache_timestamps.get(cache_key, 0)
        if (current_time - cache_time) < RESULTS_CACHE_TTL:
            logger.debug(f"✅ Использован кеш результата генерации: {cache_key[:16]}...")
            return _generation_results_cache[cache_key]
        else:
            # Удаляем устаревший кеш
            del _generation_results_cache[cache_key]
            if cache_key in _cache_timestamps:
                del _cache_timestamps[cache_key]
    
    return None


def set_cached_result(cache_key: str, result: Dict[str, Any]):
    """Сохраняет результат генерации в кеш."""
    _generation_results_cache[cache_key] = result
    _cache_timestamps[cache_key] = time.time()
    logger.debug(f"✅ Результат генерации закеширован: {cache_key[:16]}...")


def clear_old_results():
    """Очищает устаревшие результаты из кеша."""
    current_time = time.time()
    expired_keys = [
        key for key, cache_time in _cache_timestamps.items()
        if (current_time - cache_time) >= RESULTS_CACHE_TTL
    ]
    
    for key in expired_keys:
        del _generation_results_cache[key]
        del _cache_timestamps[key]
    
    if expired_keys:
        logger.info(f"🧹 Очищено {len(expired_keys)} устаревших результатов из кеша")
    
    return len(expired_keys)


def get_cache_stats() -> Dict[str, Any]:
    """Возвращает статистику кеша результатов."""
    return {
        'cached_results_count': len(_generation_results_cache),
        'cache_size_mb': sum(
            len(json.dumps(result).encode()) for result in _generation_results_cache.values()
        ) / (1024 * 1024)
    }

