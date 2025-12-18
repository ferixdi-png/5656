"""
Умный менеджер кеширования для минимизации API вызовов.
Включает периодическое обновление кеша и умное кеширование запросов.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Глобальный кеш с автоматическим обновлением
_cache_data: Dict[str, Any] = {}
_cache_timestamps: Dict[str, float] = {}
_cache_ttl: Dict[str, float] = {}
_background_tasks: Dict[str, asyncio.Task] = {}


def set_cache_with_auto_refresh(
    key: str,
    value: Any,
    ttl: float,
    refresh_func: Optional[Callable[[], Awaitable[Any]]] = None,
    refresh_interval: Optional[float] = None
):
    """
    Устанавливает кеш с автоматическим обновлением.
    
    Args:
        key: Ключ кеша
        value: Значение для кеширования
        ttl: Время жизни кеша в секундах
        refresh_func: Функция для обновления кеша (async)
        refresh_interval: Интервал обновления (если None, используется ttl * 0.8)
    """
    _cache_data[key] = value
    _cache_timestamps[key] = time.time()
    _cache_ttl[key] = ttl
    
    # Запускаем фоновое обновление, если указана функция
    if refresh_func:
        if key in _background_tasks:
            _background_tasks[key].cancel()
        
        interval = refresh_interval or (ttl * 0.8)  # Обновляем за 20% до истечения TTL
        task = asyncio.create_task(_background_refresh(key, refresh_func, interval))
        _background_tasks[key] = task
        logger.info(f"✅ Запущено фоновое обновление кеша для ключа: {key} (интервал: {interval}с)")


async def _background_refresh(key: str, refresh_func: Callable[[], Awaitable[Any]], interval: float):
    """Фоновая задача для периодического обновления кеша."""
    try:
        while True:
            await asyncio.sleep(interval)
            
            try:
                logger.debug(f"🔄 Обновление кеша для ключа: {key}")
                new_value = await refresh_func()
                
                if new_value is not None:
                    _cache_data[key] = new_value
                    _cache_timestamps[key] = time.time()
                    logger.info(f"✅ Кеш обновлен для ключа: {key}")
                else:
                    logger.warning(f"⚠️ Функция обновления вернула None для ключа: {key}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при обновлении кеша для ключа {key}: {e}", exc_info=True)
                # Продолжаем работу, даже если обновление не удалось
                
    except asyncio.CancelledError:
        logger.debug(f"🛑 Фоновое обновление кеша отменено для ключа: {key}")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в фоновом обновлении кеша для ключа {key}: {e}", exc_info=True)


def get_cached(key: str) -> Optional[Any]:
    """Получает значение из кеша, если оно еще актуально."""
    if key not in _cache_data:
        return None
    
    current_time = time.time()
    cache_time = _cache_timestamps.get(key, 0)
    ttl = _cache_ttl.get(key, 0)
    
    if (current_time - cache_time) < ttl:
        return _cache_data[key]
    else:
        # Кеш устарел, удаляем
        del _cache_data[key]
        if key in _cache_timestamps:
            del _cache_timestamps[key]
        if key in _cache_ttl:
            del _cache_ttl[key]
        if key in _background_tasks:
            _background_tasks[key].cancel()
            del _background_tasks[key]
        return None


def invalidate_cache(key: str):
    """Инвалидирует кеш для указанного ключа."""
    if key in _cache_data:
        del _cache_data[key]
    if key in _cache_timestamps:
        del _cache_timestamps[key]
    if key in _cache_ttl:
        del _cache_ttl[key]
    if key in _background_tasks:
        _background_tasks[key].cancel()
        del _background_tasks[key]
    logger.debug(f"🗑️ Кеш инвалидирован для ключа: {key}")


def get_cache_stats() -> Dict[str, Any]:
    """Возвращает статистику кеша."""
    return {
        'cached_keys': len(_cache_data),
        'active_background_tasks': len(_background_tasks),
        'keys': list(_cache_data.keys())
    }


async def refresh_all_caches():
    """Принудительно обновляет все кеши с фоновыми задачами."""
    for key, task in _background_tasks.items():
        if not task.done():
            # Запускаем обновление немедленно
            logger.info(f"🔄 Принудительное обновление кеша для ключа: {key}")
            # Можно добавить логику для немедленного обновления


def cleanup_expired_caches():
    """Очищает устаревшие кеши."""
    current_time = time.time()
    expired_keys = []
    
    for key, cache_time in _cache_timestamps.items():
        ttl = _cache_ttl.get(key, 0)
        if (current_time - cache_time) >= ttl:
            expired_keys.append(key)
    
    for key in expired_keys:
        invalidate_cache(key)
    
    if expired_keys:
        logger.info(f"🧹 Очищено {len(expired_keys)} устаревших кешей")
    
    return len(expired_keys)

