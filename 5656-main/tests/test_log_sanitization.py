"""
Тесты для sanitization логов (маскирование секретов)
"""

import os
import pytest
from app.utils.logging_config import sanitize_log_message, setup_logging, get_logger
from app.utils.mask import mask


def test_sanitize_log_message_no_secrets():
    """Тест: сообщение без секретов не изменяется"""
    message = "User 12345 started generation"
    result = sanitize_log_message(message)
    assert result == message


def test_sanitize_log_message_env_token():
    """Тест: маскирование токена из ENV"""
    # Устанавливаем тестовый токен
    test_token = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
    os.environ['TELEGRAM_BOT_TOKEN'] = test_token
    
    try:
        message = f"Using token {test_token} for request"
        result = sanitize_log_message(message)
        
        # Проверяем что токен замаскирован
        assert test_token not in result
        assert mask(test_token) in result
    finally:
        os.environ.pop('TELEGRAM_BOT_TOKEN', None)


def test_sanitize_log_message_api_key_pattern():
    """Тест: маскирование паттерна api_key=xxx"""
    message = "api_key=secret123456789"
    result = sanitize_log_message(message)
    
    # Проверяем что значение замаскировано
    assert "api_key=" in result
    assert "secret123456789" not in result
    assert "****" in result


def test_sanitize_log_message_bearer_token():
    """Тест: маскирование Bearer токена"""
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    message = f"Authorization: Bearer {token}"
    result = sanitize_log_message(message)
    
    # Проверяем что токен замаскирован
    assert "Bearer" in result
    assert token not in result
    assert "****" in result


def test_sanitize_log_message_database_url():
    """Тест: маскирование DATABASE_URL"""
    test_url = "postgresql://user:password@host:5432/db"
    os.environ['DATABASE_URL'] = test_url
    
    try:
        message = f"Connecting to {test_url}"
        result = sanitize_log_message(message)
        
        # Проверяем что URL замаскирован
        assert test_url not in result
        assert mask(test_url) in result
    finally:
        os.environ.pop('DATABASE_URL', None)


def test_logger_sanitization_integration():
    """Интеграционный тест: логгер автоматически маскирует секреты"""
    test_token = "test_token_123456789"
    os.environ['TELEGRAM_BOT_TOKEN'] = test_token
    
    try:
        setup_logging()
        logger = get_logger(__name__)
        
        # Логируем сообщение с токеном
        log_capture = []
        handler = logging.Handler()
        handler.emit = lambda record: log_capture.append(record.getMessage())
        logger.addHandler(handler)
        
        logger.info(f"Token is {test_token}")
        
        # Проверяем что в логах токен замаскирован
        assert len(log_capture) > 0
        log_message = log_capture[0]
        assert test_token not in log_message
        assert mask(test_token) in log_message
        
        logger.removeHandler(handler)
    finally:
        os.environ.pop('TELEGRAM_BOT_TOKEN', None)
        import logging
        logging.getLogger().handlers.clear()

