"""
Тесты для startup validation
"""

import os
import pytest
from app.utils.startup_validation import (
    validate_env_keys,
    validate_env_key_format,
    REQUIRED_ENV_KEYS
)


def test_validate_env_keys_all_present():
    """Тест: все ключи присутствуют"""
    # Сохраняем текущие значения
    saved = {}
    for key in REQUIRED_ENV_KEYS:
        saved[key] = os.getenv(key, '')
        os.environ[key] = 'test_value'
    
    try:
        is_valid, missing = validate_env_keys()
        assert is_valid is True
        assert len(missing) == 0
    finally:
        # Восстанавливаем
        for key, value in saved.items():
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)


def test_validate_env_keys_missing():
    """Тест: отсутствуют некоторые ключи"""
    # Сохраняем текущие значения
    saved = {}
    for key in REQUIRED_ENV_KEYS:
        saved[key] = os.getenv(key, '')
        os.environ.pop(key, None)
    
    try:
        is_valid, missing = validate_env_keys()
        assert is_valid is False
        assert len(missing) == len(REQUIRED_ENV_KEYS)
        assert set(missing) == set(REQUIRED_ENV_KEYS)
    finally:
        # Восстанавливаем
        for key, value in saved.items():
            if value:
                os.environ[key] = value


def test_validate_env_key_format_admin_id():
    """Тест: формат ADMIN_ID"""
    saved = os.getenv('ADMIN_ID', '')
    try:
        os.environ['ADMIN_ID'] = '123456789'
        assert validate_env_key_format('ADMIN_ID') is True
        
        os.environ['ADMIN_ID'] = 'invalid'
        assert validate_env_key_format('ADMIN_ID') is False
        
        os.environ['ADMIN_ID'] = ''
        assert validate_env_key_format('ADMIN_ID') is False
    finally:
        if saved:
            os.environ['ADMIN_ID'] = saved
        else:
            os.environ.pop('ADMIN_ID', None)


def test_validate_env_key_format_port():
    """Тест: формат PORT"""
    saved = os.getenv('PORT', '')
    try:
        os.environ['PORT'] = '8000'
        assert validate_env_key_format('PORT') is True
        
        os.environ['PORT'] = '0'
        assert validate_env_key_format('PORT') is False
        
        os.environ['PORT'] = '70000'
        assert validate_env_key_format('PORT') is False
        
        os.environ['PORT'] = 'invalid'
        assert validate_env_key_format('PORT') is False
    finally:
        if saved:
            os.environ['PORT'] = saved
        else:
            os.environ.pop('PORT', None)


def test_validate_env_key_format_bot_mode():
    """Тест: формат BOT_MODE"""
    saved = os.getenv('BOT_MODE', '')
    try:
        for mode in ['polling', 'webhook', 'auto', 'passive']:
            os.environ['BOT_MODE'] = mode
            assert validate_env_key_format('BOT_MODE') is True
        
        os.environ['BOT_MODE'] = 'invalid'
        assert validate_env_key_format('BOT_MODE') is False
    finally:
        if saved:
            os.environ['BOT_MODE'] = saved
        else:
            os.environ.pop('BOT_MODE', None)

