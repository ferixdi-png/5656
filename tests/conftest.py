"""
Pytest configuration и фикстуры для тестов.
"""

import os
import pytest
from tests.ptb_harness import PTBHarness


@pytest.fixture(scope="function")
def test_env():
    """Устанавливает тестовые переменные окружения."""
    old_env = {}
    test_vars = {
        'TEST_MODE': '1',
        'DRY_RUN': '1',
        'ALLOW_REAL_GENERATION': '0',
        'TELEGRAM_BOT_TOKEN': 'test_token_12345',
        'KIE_API_KEY': 'test_api_key',
        'ADMIN_ID': '12345',
    }
    
    # Сохраняем старые значения
    for key in test_vars:
        old_env[key] = os.environ.get(key)
        os.environ[key] = test_vars[key]
    
    yield
    
    # Восстанавливаем старые значения
    for key, value in old_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="function")
async def harness(test_env):
    """Создает и возвращает PTBHarness для тестов."""
    h = PTBHarness()
    await h.setup()
    yield h
    await h.teardown()

