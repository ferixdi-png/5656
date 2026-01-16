"""
BATCH 48.21: Enhanced logging for maximum diagnostic value.

Логи настолько информативные, что AI может мгновенно понять что чинить.
"""

import logging
import time
import traceback
from typing import Optional, Dict, Any
from functools import wraps
from app.utils.correlation import correlation_tag, ensure_correlation_id

logger = logging.getLogger(__name__)


def log_operation(
    operation: str,
    *,
    user_id: Optional[int] = None,
    model_id: Optional[str] = None,
    update_id: Optional[int] = None,
    callback_data: Optional[str] = None,
    duration_ms: Optional[float] = None,
    status: str = "OK",
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    fix_hint: Optional[str] = None,
    check_list: Optional[str] = None,
    **kwargs
):
    """
    Структурированное логирование операций.
    
    Формат: [OPERATION] cid=X user_id=Y duration_ms=Z status=OK/FAIL error_code=... fix_hint=...
    
    Args:
        operation: Название операции (WEBHOOK_RECEIVED, GENERATION_START, DB_QUERY, etc.)
        user_id: ID пользователя
        model_id: ID модели
        update_id: Telegram update ID
        callback_data: Callback data для кнопок
        duration_ms: Время выполнения в миллисекундах
        status: OK, FAIL, TIMEOUT, SKIPPED
        error_code: Код ошибки (DB_TIMEOUT, KIE_API_ERROR, etc.)
        error_message: Сообщение об ошибке
        fix_hint: Подсказка как исправить
        check_list: Список проверок (через |)
        **kwargs: Дополнительные поля
    """
    cid = ensure_correlation_id()
    cid_tag = correlation_tag()
    
    # Базовые поля
    parts = [
        f"[{operation}]",
        f"cid={cid}",
    ]
    
    # Контекст
    if user_id:
        parts.append(f"user_id={user_id}")
    if model_id:
        parts.append(f"model_id={model_id}")
    if update_id:
        parts.append(f"update_id={update_id}")
    if callback_data:
        # Обрезаем длинные callback_data
        cb_short = callback_data[:50] + "..." if len(callback_data) > 50 else callback_data
        parts.append(f"callback_data={cb_short}")
    
    # Метрики
    if duration_ms is not None:
        parts.append(f"duration_ms={duration_ms:.2f}")
    
    # Статус
    parts.append(f"status={status}")
    
    # Ошибки
    if error_code:
        parts.append(f"error_code={error_code}")
    if error_message:
        # Обрезаем длинные сообщения
        msg_short = error_message[:200] + "..." if len(error_message) > 200 else error_message
        parts.append(f"error={msg_short}")
    if fix_hint:
        parts.append(f"fix_hint={fix_hint}")
    if check_list:
        parts.append(f"check={check_list}")
    
    # Дополнительные поля
    for key, value in kwargs.items():
        if value is not None:
            # Обрезаем длинные значения
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            parts.append(f"{key}={value}")
    
    log_line = " | ".join(parts)
    
    # Выбираем уровень логирования
    if status == "OK":
        logger.info(log_line)
    elif status in ("FAIL", "TIMEOUT", "ERROR"):
        logger.error(log_line)
    elif status == "SKIPPED":
        logger.debug(log_line)
    else:
        logger.warning(log_line)


def log_timing(operation: str, start_time: float, **context):
    """
    Логирует операцию с автоматическим расчетом времени.
    
    Usage:
        start = time.time()
        # ... do work ...
        log_timing("DB_QUERY", start, user_id=123, query="SELECT ...")
    """
    duration_ms = (time.time() - start_time) * 1000
    log_operation(operation, duration_ms=duration_ms, **context)


def log_error(
    operation: str,
    error: Exception,
    *,
    error_code: Optional[str] = None,
    fix_hint: Optional[str] = None,
    check_list: Optional[str] = None,
    **context
):
    """
    Логирует ошибку с полным контекстом.
    
    Args:
        operation: Название операции
        error: Исключение
        error_code: Код ошибки
        fix_hint: Подсказка как исправить
        check_list: Список проверок
        **context: Дополнительный контекст
    """
    # Определяем error_code если не указан
    if not error_code:
        error_code = type(error).__name__
    
    # Определяем fix_hint на основе типа ошибки
    if not fix_hint:
        error_name = type(error).__name__
        if "Timeout" in error_name or "timeout" in str(error).lower():
            fix_hint = "Check timeout settings, network connectivity"
            error_code = error_code or "TIMEOUT"
        elif "Connection" in error_name or "connection" in str(error).lower():
            fix_hint = "Check network connectivity, service availability"
            error_code = error_code or "CONNECTION_ERROR"
        elif "Database" in error_name or "database" in str(error).lower():
            fix_hint = "Check database connection, query syntax"
            error_code = error_code or "DB_ERROR"
        else:
            fix_hint = "Check logs for details, verify input parameters"
    
    log_operation(
        operation,
        status="FAIL",
        error_code=error_code,
        error_message=str(error),
        fix_hint=fix_hint,
        check_list=check_list,
        **context
    )
    
    # Дополнительно логируем stacktrace для критичных ошибок
    logger.error(f"Stacktrace for {operation}:", exc_info=error)


def timed_operation(operation_name: str, log_args: bool = False):
    """
    Декоратор для автоматического логирования операций с timing.
    
    Usage:
        @timed_operation("DB_QUERY", log_args=True)
        async def get_user(user_id: int):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            cid = ensure_correlation_id()
            
            # Логируем начало
            context = {"cid": cid}
            if log_args:
                if args:
                    context["args"] = str(args)[:100]
                if kwargs:
                    context["kwargs"] = str(kwargs)[:100]
            
            log_operation(f"{operation_name}_START", **context)
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                log_operation(f"{operation_name}_END", duration_ms=duration_ms, status="OK", **context)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_error(f"{operation_name}_END", e, duration_ms=duration_ms, **context)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            cid = ensure_correlation_id()
            
            context = {"cid": cid}
            if log_args:
                if args:
                    context["args"] = str(args)[:100]
                if kwargs:
                    context["kwargs"] = str(kwargs)[:100]
            
            log_operation(f"{operation_name}_START", **context)
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                log_operation(f"{operation_name}_END", duration_ms=duration_ms, status="OK", **context)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                log_error(f"{operation_name}_END", e, duration_ms=duration_ms, **context)
                raise
        
        # Определяем async или sync
        if hasattr(func, '__code__'):
            import inspect
            if inspect.iscoroutinefunction(func):
                return async_wrapper
        return sync_wrapper
    
    return decorator


# Предопределенные операции для частых случаев
def log_webhook_received(update_id: int, user_id: Optional[int] = None, **kwargs):
    """Логирует получение webhook."""
    log_operation("WEBHOOK_RECEIVED", update_id=update_id, user_id=user_id, **kwargs)


def log_generation_start(user_id: int, model_id: str, **kwargs):
    """Логирует начало генерации."""
    log_operation("GENERATION_START", user_id=user_id, model_id=model_id, **kwargs)


def log_generation_complete(user_id: int, model_id: str, duration_ms: float, **kwargs):
    """Логирует завершение генерации."""
    log_operation("GENERATION_COMPLETE", user_id=user_id, model_id=model_id, duration_ms=duration_ms, status="OK", **kwargs)


def log_generation_error(user_id: int, model_id: str, error: Exception, **kwargs):
    """Логирует ошибку генерации."""
    log_error("GENERATION_ERROR", error, user_id=user_id, model_id=model_id, **kwargs)


def log_db_query(operation: str, duration_ms: float, user_id: Optional[int] = None, **kwargs):
    """Логирует запрос к БД."""
    log_operation("DB_QUERY", operation=operation, duration_ms=duration_ms, user_id=user_id, **kwargs)


def log_kie_api_request(model_id: str, duration_ms: float, status: str = "OK", **kwargs):
    """Логирует запрос к KIE API."""
    log_operation("KIE_API_REQUEST", model_id=model_id, duration_ms=duration_ms, status=status, **kwargs)


def log_button_click(callback_data: str, user_id: int, **kwargs):
    """Логирует клик по кнопке."""
    log_operation("BUTTON_CLICK", callback_data=callback_data, user_id=user_id, **kwargs)

