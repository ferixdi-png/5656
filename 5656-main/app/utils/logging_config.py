"""
Унифицированная конфигурация логирования
Единый логгер, уровни, формат, request-id для операций генерации
С sanitization секретов в логах
"""

import logging
import sys
import uuid
import os
import re
from contextvars import ContextVar
from typing import Optional
from app.utils.mask import mask

# Context variable для request-id (для async операций)
_request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


def get_request_id() -> Optional[str]:
    """Получить текущий request-id"""
    return _request_id.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """Установить request-id (генерирует новый если не указан)"""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    _request_id.set(request_id)
    return request_id


class RequestIdFilter(logging.Filter):
    """Фильтр для добавления request-id в логи"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = get_request_id()
        if request_id:
            record.request_id = request_id
        else:
            record.request_id = "-"
        return True


def setup_logging(level: int = logging.INFO, include_request_id: bool = True) -> None:
    """
    Настраивает унифицированное логирование
    
    Args:
        level: Уровень логирования
        include_request_id: Включать ли request-id в формат
    """
    # Формат с request-id
    if include_request_id:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
    else:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Удаляем существующие handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Создаем console handler с sanitization
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(SanitizingFormatter(log_format))
    
    # Добавляем фильтр для request-id
    if include_request_id:
        console_handler.addFilter(RequestIdFilter())
    
    root_logger.addHandler(console_handler)
    
    # Настраиваем уровни для внешних библиотек
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер с унифицированным именем
    
    Args:
        name: Имя логгера (обычно __name__)
    
    Returns:
        Настроенный логгер
    """
    return logging.getLogger(name)


def sanitize_log_message(message: str) -> str:
    """
    Маскирует секретные значения в логах.
    
    Args:
        message: Исходное сообщение
        
    Returns:
        Сообщение с замаскированными секретами
    """
    # Список ключей для маскирования
    secret_keys = [
        'TELEGRAM_BOT_TOKEN',
        'KIE_API_KEY',
        'DATABASE_URL',
        'API_KEY',
        'SECRET',
        'PASSWORD',
        'TOKEN',
    ]
    
    # Получаем значения из ENV
    env_secrets = {}
    for key in secret_keys:
        value = os.getenv(key, '')
        if value:
            env_secrets[value] = mask(value)
    
    # Маскируем в сообщении
    result = message
    for secret_value, masked_value in env_secrets.items():
        if secret_value in result:
            result = result.replace(secret_value, masked_value)
    
    # Маскируем паттерны типа "token=xxx" или "api_key=xxx"
    patterns = [
        (r'(token|api_key|secret|password|database_url)\s*[:=]\s*([^\s,;\)]+)', 
         lambda m: f"{m.group(1)}={mask(m.group(2))}"),
        (r'(Bearer|Token)\s+([A-Za-z0-9_-]+)', 
         lambda m: f"{m.group(1)} {mask(m.group(2))}"),
    ]
    
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


class SanitizingFormatter(logging.Formatter):
    """Formatter с автоматическим маскированием секретов"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись с маскированием секретов"""
        original_msg = record.getMessage()
        sanitized_msg = sanitize_log_message(original_msg)
        
        # Создаем копию записи с замаскированным сообщением
        record_copy = logging.makeLogRecord(record.__dict__)
        record_copy.msg = sanitized_msg
        record_copy.args = ()  # Очищаем args, т.к. msg уже форматирован
        
        return super().format(record_copy)


def log_error_with_stacktrace(logger: logging.Logger, error: Exception, user_message: str = "Ошибка, попробуйте ещё раз") -> None:
    """
    Логирует ошибку с полным stacktrace в логах (с маскированием секретов)
    
    Args:
        logger: Логгер
        error: Исключение
        user_message: Короткое сообщение для пользователя (не логируется)
    """
    error_msg = f"Error: {type(error).__name__}: {error}"
    sanitized_msg = sanitize_log_message(error_msg)
    
    logger.error(
        sanitized_msg,
        exc_info=True  # Включает полный stacktrace
    )
    # user_message не логируется - оно отправляется пользователю отдельно


def log_generation_operation(logger: logging.Logger, operation: str, user_id: int, model_id: str = None, **kwargs) -> None:
    """
    Логирует операцию генерации с request-id
    
    Args:
        logger: Логгер
        operation: Название операции (start, complete, error, etc.)
        user_id: ID пользователя
        model_id: ID модели (опционально)
        **kwargs: Дополнительные параметры для логирования
    """
    request_id = get_request_id() or set_request_id()
    
    log_parts = [f"GEN[{operation}]", f"user_id={user_id}"]
    if model_id:
        log_parts.append(f"model_id={model_id}")
    if kwargs:
        log_parts.extend([f"{k}={v}" for k, v in kwargs.items()])
    
    logger.info(" | ".join(log_parts))
