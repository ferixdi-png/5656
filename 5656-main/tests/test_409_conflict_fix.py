#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для проверки исправления 409 Conflict
НИКОГДА не использует реальный Telegram API
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.singleton_lock import SingletonLock
from app.bot_mode import get_bot_mode, ensure_polling_mode, ensure_webhook_mode, handle_conflict_gracefully
from telegram.error import Conflict


def test_singleton_lock_prevents_duplicate():
    """Тест: singleton lock предотвращает запуск второго экземпляра"""
    lock1 = SingletonLock("test_lock")
    lock2 = SingletonLock("test_lock")
    
    # Первый экземпляр получает lock
    assert lock1.acquire() is True
    
    # Второй экземпляр НЕ получает lock
    assert lock2.acquire() is False
    
    # Освобождаем lock
    lock1.release()
    
    # Теперь второй может получить lock
    assert lock2.acquire() is True
    lock2.release()


def test_bot_mode_polling():
    """Тест: BOT_MODE=polling возвращает polling"""
    with patch.dict(os.environ, {"BOT_MODE": "polling"}):
        mode = get_bot_mode()
        assert mode == "polling"


def test_bot_mode_webhook():
    """Тест: BOT_MODE=webhook возвращает webhook"""
    with patch.dict(os.environ, {"BOT_MODE": "webhook"}):
        mode = get_bot_mode()
        assert mode == "webhook"


def test_bot_mode_default():
    """Тест: без BOT_MODE возвращает polling по умолчанию"""
    with patch.dict(os.environ, {}, clear=True):
        mode = get_bot_mode()
        assert mode == "polling"


@pytest.mark.asyncio
async def test_ensure_polling_mode_removes_webhook():
    """Тест: ensure_polling_mode удаляет webhook"""
    mock_bot = AsyncMock()
    mock_webhook_info = Mock()
    mock_webhook_info.url = "https://example.com/webhook"
    mock_bot.get_webhook_info.return_value = mock_webhook_info
    mock_bot.delete_webhook.return_value = True
    
    # После удаления webhook должен быть пустым
    mock_webhook_info_after = Mock()
    mock_webhook_info_after.url = None
    mock_bot.get_webhook_info.side_effect = [mock_webhook_info, mock_webhook_info_after]
    
    result = await ensure_polling_mode(mock_bot)
    assert result is True
    mock_bot.delete_webhook.assert_called_once_with(drop_pending_updates=True)


@pytest.mark.asyncio
async def test_ensure_polling_mode_no_webhook():
    """Тест: ensure_polling_mode работает если webhook не установлен"""
    mock_bot = AsyncMock()
    mock_webhook_info = Mock()
    mock_webhook_info.url = None
    mock_bot.get_webhook_info.return_value = mock_webhook_info
    
    result = await ensure_polling_mode(mock_bot)
    assert result is True
    # delete_webhook не должен вызываться если webhook не установлен
    mock_bot.delete_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_polling_mode_conflict():
    """Тест: ensure_polling_mode обрабатывает Conflict"""
    mock_bot = AsyncMock()
    mock_bot.get_webhook_info.side_effect = Conflict("Conflict detected")
    
    with pytest.raises(Conflict):
        await ensure_polling_mode(mock_bot)


@pytest.mark.asyncio
async def test_ensure_webhook_mode_sets_webhook():
    """Тест: ensure_webhook_mode устанавливает webhook"""
    mock_bot = AsyncMock()
    mock_webhook_info = Mock()
    mock_webhook_info.url = "https://example.com/webhook"
    mock_bot.set_webhook.return_value = True
    mock_bot.get_webhook_info.return_value = mock_webhook_info
    
    result = await ensure_webhook_mode(mock_bot, "https://example.com/webhook")
    assert result is True
    # secret_token может быть добавлен в реальном коде, поэтому проверяем параметры гибко
    called_kwargs = mock_bot.set_webhook.call_args.kwargs
    assert called_kwargs["url"] == "https://example.com/webhook"
    assert called_kwargs.get("drop_pending_updates") is True
    # Если секрет задан, он должен быть строкой
    if "secret_token" in called_kwargs:
        assert isinstance(called_kwargs["secret_token"], str)


def test_handle_conflict_gracefully_exits():
    """Тест: handle_conflict_gracefully завершает процесс"""
    conflict = Conflict("terminated by other getUpdates request")
    
    with patch('sys.exit') as mock_exit:
        handle_conflict_gracefully(conflict, "polling")
        mock_exit.assert_called_once_with(0)


def test_no_real_telegram_network():
    """Тест: нет реальных HTTP запросов к Telegram API"""
    import re
    test_files = list(Path(__file__).parent.glob("test_*.py"))
    
    for test_file in test_files:
        content = test_file.read_text(encoding='utf-8', errors='ignore')
        # Проверяем что нет реальных запросов к api.telegram.org
        if 'api.telegram.org' in content.lower():
            # Проверяем что это не просто проверка или комментарий
            if 'fake' not in content.lower() and 'mock' not in content.lower():
                # Проверяем контекст
                if 'requests.get' in content or 'httpx.get' in content or 'aiohttp.get' in content:
                    pytest.fail(f"Real HTTP request to api.telegram.org found in {test_file.name}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])






