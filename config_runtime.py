"""
Runtime configuration для режимов тестирования и dry-run.
Определяет, какие операции разрешены, какие gateway использовать и т.д.
"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    """
    Читает булево значение из переменной окружения.
    Поддерживает: 1, true, yes, on (case-insensitive) = True
    Остальное = False
    """
    value = os.getenv(name)
    if not value:
        return default
    
    value_lower = value.lower().strip()
    return value_lower in ('1', 'true', 'yes', 'on')


def is_test_mode() -> bool:
    """Проверяет, включен ли тестовый режим."""
    return env_bool('TEST_MODE', default=False)


def is_dry_run() -> bool:
    """Проверяет, включен ли режим dry-run (симуляция без реальных операций)."""
    return env_bool('DRY_RUN', default=False)


def allow_real_generation() -> bool:
    """
    Проверяет, разрешены ли реальные генерации.
    По умолчанию False (безопасно).
    В проде должно быть 1.
    """
    return env_bool('ALLOW_REAL_GENERATION', default=False)


def should_use_mock_gateway() -> bool:
    """
    Определяет, нужно ли использовать mock gateway вместо реального.
    Использует mock если:
    - TEST_MODE=1, или
    - ALLOW_REAL_GENERATION=0
    """
    return is_test_mode() or not allow_real_generation()


def get_config_summary() -> dict:
    """Возвращает словарь с текущей конфигурацией для отладки."""
    return {
        'TEST_MODE': is_test_mode(),
        'DRY_RUN': is_dry_run(),
        'ALLOW_REAL_GENERATION': allow_real_generation(),
        'USE_MOCK_GATEWAY': should_use_mock_gateway(),
    }

