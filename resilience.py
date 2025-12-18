"""
Модуль для отказоустойчивости: retry логика, fallback и обработка сетевых ошибок.
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, Callable, List
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Настройки retry
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_TIMEOUT = 30.0


async def retry_with_backoff(
    func: Callable,
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_RETRY_DELAY,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    timeout: float = DEFAULT_TIMEOUT,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
) -> Any:
    """
    Выполняет функцию с повторными попытками и экспоненциальной задержкой.
    
    Args:
        func: Асинхронная функция для выполнения
        max_retries: Максимальное количество попыток
        initial_delay: Начальная задержка в секундах
        backoff_multiplier: Множитель для экспоненциальной задержки
        timeout: Таймаут для каждой попытки
        exceptions: Кортеж исключений, при которых нужно повторять
        on_retry: Функция обратного вызова при повторной попытке
    
    Returns:
        Результат выполнения функции
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            # Выполняем функцию с таймаутом
            result = await asyncio.wait_for(func(), timeout=timeout)
            if attempt > 0:
                logger.info(f"✅ Успешно после {attempt} повторных попыток")
            return result
            
        except exceptions as e:
            last_exception = e
            
            if attempt < max_retries:
                if on_retry:
                    try:
                        await on_retry(attempt + 1, max_retries, str(e))
                    except:
                        pass
                
                logger.warning(
                    f"⚠️ Попытка {attempt + 1}/{max_retries + 1} не удалась: {e}. "
                    f"Повтор через {delay:.1f}с..."
                )
                
                await asyncio.sleep(delay)
                delay *= backoff_multiplier
            else:
                logger.error(f"❌ Все {max_retries + 1} попыток не удались. Последняя ошибка: {e}")
                raise
    
    # Не должно достичь сюда, но на всякий случай
    if last_exception:
        raise last_exception


def circuit_breaker(max_failures: int = 5, timeout: float = 60.0):
    """
    Декоратор Circuit Breaker для предотвращения каскадных отказов.
    
    Args:
        max_failures: Максимальное количество последовательных ошибок
        timeout: Время в секундах до попытки восстановления
    """
    failures = {}
    last_failure_time = {}
    circuit_open = {}
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Проверяем, открыт ли circuit breaker
            if func_name in circuit_open and circuit_open[func_name]:
                if time.time() - last_failure_time.get(func_name, 0) < timeout:
                    logger.warning(f"🔴 Circuit breaker открыт для {func_name}. Пропускаем запрос.")
                    raise Exception(f"Circuit breaker открыт для {func_name}")
                else:
                    # Пробуем восстановить
                    logger.info(f"🟡 Пробуем восстановить circuit breaker для {func_name}")
                    circuit_open[func_name] = False
                    failures[func_name] = 0
            
            try:
                result = await func(*args, **kwargs)
                
                # Успешный вызов - сбрасываем счетчик ошибок
                if func_name in failures:
                    failures[func_name] = 0
                    circuit_open[func_name] = False
                
                return result
                
            except Exception as e:
                # Увеличиваем счетчик ошибок
                if func_name not in failures:
                    failures[func_name] = 0
                
                failures[func_name] += 1
                last_failure_time[func_name] = time.time()
                
                # Если достигли лимита, открываем circuit breaker
                if failures[func_name] >= max_failures:
                    circuit_open[func_name] = True
                    logger.error(
                        f"🔴 Circuit breaker открыт для {func_name} после {failures[func_name]} ошибок"
                    )
                
                raise
        
        return wrapper
    return decorator


async def fallback_request(
    primary_func: Callable,
    fallback_func: Optional[Callable] = None,
    fallback_data: Optional[Any] = None
) -> Any:
    """
    Выполняет запрос с fallback на альтернативный источник данных.
    
    Args:
        primary_func: Основная функция для выполнения
        fallback_func: Функция fallback (опционально)
        fallback_data: Данные fallback (если функция не указана)
    
    Returns:
        Результат выполнения основной функции или fallback
    """
    try:
        result = await primary_func()
        return result
        
    except Exception as e:
        logger.warning(f"⚠️ Основной запрос не удался: {e}. Используем fallback.")
        
        if fallback_func:
            try:
                return await fallback_func()
            except Exception as fallback_error:
                logger.error(f"❌ Fallback функция также не удалась: {fallback_error}")
                if fallback_data is not None:
                    return fallback_data
                raise
        
        if fallback_data is not None:
            return fallback_data
        
        raise


async def health_check(endpoint: str, timeout: float = 5.0) -> bool:
    """
    Проверяет доступность endpoint.
    
    Args:
        endpoint: URL для проверки
        timeout: Таймаут в секундах
    
    Returns:
        True, если endpoint доступен
    """
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                return response.status == 200
                
    except Exception as e:
        logger.debug(f"⚠️ Health check для {endpoint} не удался: {e}")
        return False


async def batch_request_with_retry(
    requests: List[Callable],
    max_concurrent: int = 5,
    max_retries: int = 3
) -> List[Any]:
    """
    Выполняет батч запросов с retry логикой.
    
    Args:
        requests: Список функций для выполнения
        max_concurrent: Максимальное количество одновременных запросов
        max_retries: Максимальное количество повторных попыток
    
    Returns:
        Список результатов
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_with_retry(func: Callable, index: int) -> Dict[str, Any]:
        async with semaphore:
            try:
                result = await retry_with_backoff(func, max_retries=max_retries)
                return {'index': index, 'result': result, 'success': True}
            except Exception as e:
                logger.error(f"❌ Запрос {index} не удался после {max_retries} попыток: {e}")
                return {'index': index, 'result': None, 'success': False, 'error': str(e)}
    
    tasks = [execute_with_retry(req, idx) for idx, req in enumerate(requests)]
    results = await asyncio.gather(*tasks)
    
    # Сортируем по индексу
    results.sort(key=lambda x: x['index'])
    
    return [r['result'] if r['success'] else None for r in results]

