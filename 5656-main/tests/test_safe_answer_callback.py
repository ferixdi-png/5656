#!/usr/bin/env python3
"""
Test safe_answer_callback helper - ensures no infinite spinner.

Verifies:
1. Helper handles CallbackQuery correctly
2. Helper handles errors gracefully
3. Helper works with bot.answer_callback_query fallback
4. Helper never raises exceptions
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram.types import CallbackQuery
from app.telemetry.telemetry_helpers import safe_answer_callback


@pytest.mark.asyncio
async def test_safe_answer_callback_success():
    """Test that safe_answer_callback works with valid callback."""
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.answer = AsyncMock()
    
    result = await safe_answer_callback(mock_callback, text="Test", show_alert=False)
    
    assert result is True, "Should return True on success"
    assert mock_callback.answer.called, "callback.answer() should be called"
    call_args = mock_callback.answer.call_args
    assert call_args[1]["text"] == "Test", "Text should be passed correctly"
    assert call_args[1]["show_alert"] is False, "show_alert should be passed correctly"


@pytest.mark.asyncio
async def test_safe_answer_callback_with_alert():
    """Test that safe_answer_callback works with show_alert=True."""
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.answer = AsyncMock()
    
    result = await safe_answer_callback(mock_callback, text="Alert", show_alert=True)
    
    assert result is True, "Should return True on success"
    call_args = mock_callback.answer.call_args
    assert call_args[1]["show_alert"] is True, "show_alert should be True"


@pytest.mark.asyncio
async def test_safe_answer_callback_handles_exception():
    """Test that safe_answer_callback handles exceptions gracefully."""
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.answer = AsyncMock(side_effect=Exception("Test error"))
    mock_callback.id = "test_id"
    mock_callback.bot = None  # No bot fallback
    
    # Should not raise exception
    result = await safe_answer_callback(mock_callback, text="Test")
    
    assert result is False, "Should return False on failure"
    assert mock_callback.answer.called, "Should have tried to call answer()"


@pytest.mark.asyncio
async def test_safe_answer_callback_with_bot_fallback():
    """Test that safe_answer_callback uses bot.answer_callback_query as fallback."""
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.answer = AsyncMock(side_effect=Exception("answer() failed"))
    mock_callback.id = "test_callback_id"
    mock_callback.bot = Mock()
    mock_callback.bot.answer_callback_query = AsyncMock()
    
    result = await safe_answer_callback(mock_callback, text="Fallback", show_alert=False)
    
    # Should try bot.answer_callback_query after callback.answer() fails
    assert mock_callback.bot.answer_callback_query.called, "Should use bot fallback"
    call_args = mock_callback.bot.answer_callback_query.call_args
    assert call_args[1]["callback_query_id"] == "test_callback_id"
    assert call_args[1]["text"] == "Fallback"


@pytest.mark.asyncio
async def test_safe_answer_callback_none_callback():
    """Test that safe_answer_callback handles None callback gracefully."""
    result = await safe_answer_callback(None, text="Test")
    
    assert result is False, "Should return False for None callback"


@pytest.mark.asyncio
async def test_safe_answer_callback_no_text():
    """Test that safe_answer_callback works without text."""
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.answer = AsyncMock()
    
    result = await safe_answer_callback(mock_callback, text=None, show_alert=False)
    
    assert result is True, "Should work without text"
    assert mock_callback.answer.called


@pytest.mark.asyncio
async def test_safe_answer_callback_all_failures():
    """Test that safe_answer_callback never raises even if all methods fail."""
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.answer = AsyncMock(side_effect=Exception("answer() failed"))
    mock_callback.id = "test_id"
    mock_callback.bot = Mock()
    mock_callback.bot.answer_callback_query = AsyncMock(side_effect=Exception("bot method failed"))
    
    # Should not raise, should return False
    result = await safe_answer_callback(mock_callback, text="Test")
    
    assert result is False, "Should return False when all methods fail"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

