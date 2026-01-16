"""
Retry utilities with exponential backoff
"""

import asyncio
import logging
import random
from typing import TypeVar, Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Декоратор для повторных попыток с exponential backoff
    
    Args:
        max_attempts: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
        max_delay: Максимальная задержка в секундах
        backoff_factor: Множитель для exponential backoff
        jitter: Добавлять ли случайное отклонение
        exceptions: Кортеж исключений, при которых делать retry
        on_retry: Callback функция при retry (exception, attempt_number)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        # Последняя попытка - не делаем задержку
                        logger.error(f"❌ {func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    
                    # Вычисляем задержку
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    
                    # Добавляем jitter
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"⚠️ {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    if on_retry:
                        try:
                            on_retry(e, attempt)
                        except Exception:
                            pass
                    
                    await asyncio.sleep(delay)
            
            # Не должно сюда дойти, но на всякий случай
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} failed after {max_attempts} attempts")
        
        return wrapper
    return decorator


async def retry_with_backoff(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    **kwargs: Any
) -> T:
    """
    Выполнить функцию с retry логикой
    
    Args:
        func: Асинхронная функция для выполнения
        *args: Позиционные аргументы
        max_attempts: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
        max_delay: Максимальная задержка в секундах
        backoff_factor: Множитель для exponential backoff
        jitter: Добавлять ли случайное отклонение
        exceptions: Кортеж исключений, при которых делать retry
        **kwargs: Именованные аргументы
    
    Returns:
        Результат выполнения функции
    """
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            
            if attempt == max_attempts:
                logger.error(f"❌ {func.__name__} failed after {max_attempts} attempts: {e}")
                raise
            
            # Вычисляем задержку
            delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
            
            # Добавляем jitter
            if jitter:
                delay = delay * (0.5 + random.random() * 0.5)
            
            logger.warning(
                f"⚠️ {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
    
    # Не должно сюда дойти
    if last_exception:
        raise last_exception
    raise RuntimeError(f"{func.__name__} failed after {max_attempts} attempts")


