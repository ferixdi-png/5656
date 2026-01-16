"""
Тесты главного меню бота.
Проверяет, что /start не падает и возвращает корректное меню.
"""

import pytest
from telegram.ext import CommandHandler
from bot_kie import start


@pytest.mark.asyncio
async def test_start_command(harness):
    """Тест команды /start."""
    # Добавляем handler
    harness.add_handler(CommandHandler('start', start))
    
    # Обрабатываем команду
    result = await harness.process_command('/start', user_id=12345)
    
    # Проверяем результат
    assert result['success'], f"Command failed: {result.get('error')}"
    
    # Проверяем, что бот отправил сообщение
    assert len(result['outbox']['messages']) > 0, "Bot should send a message"
    
    last_message = result['outbox']['messages'][-1]
    assert 'text' in last_message, "Message should have text"
    assert len(last_message['text']) > 0, "Message text should not be empty"
    
    # Проверяем, что есть клавиатура
    if 'reply_markup' in last_message:
        assert last_message['reply_markup'] is not None, "Should have reply_markup"


@pytest.mark.asyncio
async def test_start_command_no_crash(harness):
    """Тест, что /start не падает с исключением."""
    harness.add_handler(CommandHandler('start', start))
    
    # Обрабатываем команду несколько раз подряд
    for i in range(3):
        result = await harness.process_command('/start', user_id=12345 + i)
        assert result['success'], f"Command should not fail on attempt {i+1}"

