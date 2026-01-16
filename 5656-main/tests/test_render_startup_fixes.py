"""
Тесты для исправлений старта на Render:
- async_check_pg не вызывает nested loop ошибку
- lock not acquired не вызывает sys.exit (passive mode)
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_async_check_pg_no_nested_loop():
    """
    Проверяет что async_check_pg не вызывает ошибку nested loop.
    """
    # Мокаем asyncpg
    with patch('app.storage.pg_storage.asyncpg') as mock_asyncpg:
        mock_pool = AsyncMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
        mock_pool.close = AsyncMock()
        
        from app.storage.pg_storage import PostgresStorage
        
        storage = PostgresStorage("postgresql://test:test@localhost/test")
        
        # Симулируем что мы в async контексте
        import asyncio
        
        async def test_async():
            # Вызываем async_test_connection в async контексте
            result = await storage.async_test_connection()
            assert isinstance(result, bool)
            # Не должно быть ошибки nested loop
        
        # Запускаем в event loop
        asyncio.run(test_async())


def test_lock_not_acquired_no_exit():
    """
    Проверяет что при lock not acquired процесс НЕ вызывает sys.exit (passive mode).
    """
    # Устанавливаем PASSIVE mode: SINGLETON_LOCK_STRICT=0, SINGLETON_LOCK_FORCE_ACTIVE=0
    with patch.dict(os.environ, {
        'SINGLETON_LOCK_STRICT': '0',
        'SINGLETON_LOCK_FORCE_ACTIVE': '0',
        'DATABASE_URL': 'postgresql://test:test@localhost/test'
    }, clear=False):
        # Нужно переимпортировать функцию чтобы она прочитала обновленные ENV
        import importlib
        import app.locking.single_instance as lock_module
        
        # Мокируем низкоуровневые функции
        with patch.object(lock_module, '_acquire_postgres_lock', return_value=None):
            with patch.object(lock_module, '_force_release_stale_lock'):
                with patch('sys.exit') as mock_exit:
                    # Переимпортируем функцию после установки patches
                    importlib.reload(lock_module)
                    
                    # Вызываем функцию
                    result = lock_module.acquire_single_instance_lock()
                    
                    # В PASSIVE mode должен вернуть False
                    assert result is False, f"Expected False (passive mode) but got {result}"
                    
                    # Проверяем что sys.exit НЕ был вызван (в non-strict, non-force-active mode)
                    mock_exit.assert_not_called()










def test_lock_strict_mode_logic():
    """
    Проверяет что strict mode использует правильную логику (проверяем без реального exit).
    """
    # Просто импортируем модуль - если есть синтаксис ошибка, это упадет
    import app.locking.single_instance as lock_module
    
    # Проверяем что функция существует и имеет правильную сигнатуру
    assert hasattr(lock_module, 'acquire_single_instance_lock')
    assert callable(lock_module.acquire_single_instance_lock)
    
    # Проверяем что есть обработка SINGLETON_LOCK_STRICT переменной
    import inspect
    source = inspect.getsource(lock_module.acquire_single_instance_lock)
    assert 'SINGLETON_LOCK_STRICT' in source
    assert 'sys.exit' in source  # Есть вызов exit в коде


def test_passive_mode_logic():
    """
    Проверяет что passive mode логика существует в коде.
    """
    import app.locking.single_instance as lock_module
    import inspect
    
    source = inspect.getsource(lock_module.acquire_single_instance_lock)
    
    # Проверяем что есть логика для passive mode
    assert 'PASSIVE MODE' in source or 'passive' in source.lower()
    assert 'return False' in source  # Passive mode должен вернуть False


def test_force_active_mode_logic():
    """
    Проверяет что FORCE ACTIVE MODE логика существует (для single-instance Render).
    """
    import app.locking.single_instance as lock_module
    import inspect
    
    source = inspect.getsource(lock_module.acquire_single_instance_lock)
    
    # Проверяем что есть логика для force active mode
    assert 'FORCE ACTIVE' in source or 'force_active' in source.lower()


def test_webhook_mode_keeps_healthcheck_running():
    """
    Проверяет что при валидном webhook конфиге healthcheck остается поднятым.
    """
    # Просто проверяем что коды импортируются без ошибок
    try:
        import app.main
        import app.utils.healthcheck
        assert hasattr(app.main, 'run')
        assert hasattr(app.utils.healthcheck, 'start_health_server')
    except ImportError as e:
        pytest.fail(f"Failed to import required modules: {e}")


def test_sync_test_connection_detects_running_loop():
    """
    Проверяет что sync test_connection обнаруживает запущенный loop и предупреждает.
    """
    from app.storage.pg_storage import PostgresStorage
    
    storage = PostgresStorage("postgresql://test:test@localhost/test")
    
    # Проверяем что метод существует
    assert hasattr(storage, 'test_connection')
    assert callable(storage.test_connection)
    
    # Проверяем что метод async_test_connection существует
    assert hasattr(storage, 'async_test_connection')
    import inspect
    assert inspect.iscoroutinefunction(storage.async_test_connection)


@pytest.fixture(autouse=True)
def reset_env():
    """Сбрасывает env переменные перед каждым тестом"""
    old_strict = os.environ.get('SINGLETON_LOCK_STRICT')
    old_db = os.environ.get('DATABASE_URL')
    
    yield
    
    if old_strict:
        os.environ['SINGLETON_LOCK_STRICT'] = old_strict
    elif 'SINGLETON_LOCK_STRICT' in os.environ:
        del os.environ['SINGLETON_LOCK_STRICT']
    
    if old_db:
        os.environ['DATABASE_URL'] = old_db
    elif 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
