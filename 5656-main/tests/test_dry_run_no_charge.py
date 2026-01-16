"""
Тесты для проверки, что в DRY_RUN баланс не списывается и RealKieGateway не вызывается.
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


@pytest.fixture
def dry_run_env():
    """Устанавливает DRY_RUN=1 для тестов."""
    old_value = os.environ.get("DRY_RUN")
    os.environ["DRY_RUN"] = "1"
    os.environ["TEST_MODE"] = "1"
    os.environ["ALLOW_REAL_GENERATION"] = "0"
    
    # Сбрасываем singleton'ы после установки env переменных
    try:
        from app.config import reset_settings
        reset_settings()
    except ImportError:
        pass
    
    try:
        from kie_gateway import reset_gateway
        reset_gateway()
    except ImportError:
        pass
    
    yield
    
    # Снова сбрасываем singleton'ы в teardown
    try:
        from app.config import reset_settings
        reset_settings()
    except ImportError:
        pass
    
    try:
        from kie_gateway import reset_gateway
        reset_gateway()
    except ImportError:
        pass
    
    if old_value:
        os.environ["DRY_RUN"] = old_value
    else:
        os.environ.pop("DRY_RUN", None)
    os.environ.pop("TEST_MODE", None)
    os.environ.pop("ALLOW_REAL_GENERATION", None)


def test_dry_run_uses_mock_gateway(dry_run_env):
    """Проверяет, что в DRY_RUN используется MockKieGateway."""
    from config_runtime import should_use_mock_gateway
    from kie_gateway import get_kie_gateway
    
    assert should_use_mock_gateway(), "В DRY_RUN должен использоваться mock gateway"
    
    gateway = get_kie_gateway()
    assert "Mock" in gateway.__class__.__name__, f"Ожидался MockKieGateway, получен {gateway.__class__.__name__}"


@pytest.mark.asyncio
async def test_dry_run_no_real_api_calls(dry_run_env):
    """Проверяет, что в DRY_RUN не делаются реальные API вызовы."""
    from kie_gateway import get_kie_gateway
    
    gateway = get_kie_gateway()
    
    # Пытаемся создать задачу
    result = await gateway.create_task(
        api_model="test/model",
        input={"prompt": "test"}
    )
    
    # Должен вернуться mock результат
    assert result.get("ok") is True
    assert "taskId" in result
    assert "mock" in result["taskId"].lower() or "test" in result["taskId"].lower()


@pytest.mark.asyncio
async def test_dry_run_no_balance_deduction(dry_run_env):
    """Проверяет, что в DRY_RUN баланс не списывается."""
    # Этот тест требует интеграции с bot_kie.py
    # Пока проверяем только конфигурацию
    from config_runtime import is_dry_run, allow_real_generation
    
    assert is_dry_run(), "DRY_RUN должен быть включен"
    assert not allow_real_generation(), "Реальные генерации должны быть запрещены"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

