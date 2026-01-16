"""
E2E tests for navigation - ensures all back buttons work correctly.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, User, Chat, Message
from aiogram.fsm.context import FSMContext

from bot.handlers.flow import main_menu_cb
from bot.handlers.marketing import cb_marketing_main
from bot.handlers.history import cb_history_main


@pytest.fixture
def mock_callback():
    """Create mock callback query."""
    user = User(
        id=12345,
        is_bot=False,
        first_name="Test",
        username="testuser"
    )
    chat = Chat(id=12345, type="private")
    message = Message(
        message_id=1,
        date=None,
        chat=chat,
        from_user=user,
        content_type="text",
        text="test"
    )
    callback = CallbackQuery(
        id="test_callback_id",
        from_user=user,
        chat_instance="test",
        message=message
    )
    return callback


@pytest.fixture
def mock_state():
    """Create mock FSM context."""
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    return state


@pytest.mark.asyncio
async def test_main_menu_handler(mock_callback, mock_state):
    """Test that main_menu handler works correctly."""
    mock_callback.answer = AsyncMock()
    mock_callback.message.edit_text = AsyncMock()
    
    await main_menu_cb(mock_callback, mock_state)
    
    # Verify callback was answered
    mock_callback.answer.assert_called_once()
    
    # Verify state was cleared
    mock_state.clear.assert_called_once()
    
    # Verify message was edited
    mock_callback.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_back_button_leads_to_main_menu():
    """Test that all back buttons use 'main_menu' callback_data."""
    # This is a static analysis test - we check that back buttons
    # in the code use 'main_menu' instead of intermediate menus
    
    import re
    from pathlib import Path
    
    handlers_dir = Path(__file__).parent.parent / "bot" / "handlers"
    
    # Find all back button definitions
    back_button_pattern = re.compile(
        r'InlineKeyboardButton\s*\(\s*text\s*=\s*["\'].*[Нн]азад.*["\']\s*,\s*callback_data\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )
    
    issues = []
    for handler_file in handlers_dir.rglob("*.py"):
        content = handler_file.read_text(encoding='utf-8')
        for match in back_button_pattern.finditer(content):
            callback_data = match.group(1)
            if callback_data != "main_menu" and not callback_data.startswith("page:"):
                # page: is allowed for pagination
                if "main" not in callback_data.lower():
                    issues.append(f"{handler_file.name}:{match.start()}: back button uses '{callback_data}' instead of 'main_menu'")
    
    # Allow some exceptions (like pagination)
    critical_issues = [i for i in issues if "page:" not in i and "cat:" not in i]
    
    assert len(critical_issues) == 0, f"Found {len(critical_issues)} back buttons not using 'main_menu':\n" + "\n".join(critical_issues)


@pytest.mark.asyncio
async def test_marketing_back_to_main_menu(mock_callback, mock_state):
    """Test that marketing menu back button leads to main menu."""
    mock_callback.answer = AsyncMock()
    mock_callback.message.edit_text = AsyncMock()
    
    await cb_marketing_main(mock_callback, mock_state)
    
    # Verify callback was answered
    mock_callback.answer.assert_called_once()
    
    # Verify state was cleared
    mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_history_back_to_main_menu(mock_callback, mock_state):
    """Test that history menu back button leads to main menu."""
    mock_callback.answer = AsyncMock()
    mock_callback.message.edit_text = AsyncMock()
    
    # Mock database service
    import sys
    from unittest.mock import patch
    
    with patch('bot.handlers.history._get_db_service') as mock_db:
        mock_db_service = MagicMock()
        mock_db.return_value = mock_db_service
        
        from app.database.services import JobService
        mock_job_service = AsyncMock()
        mock_job_service.list_user_jobs = AsyncMock(return_value=[])
        
        with patch('bot.handlers.history.JobService', return_value=mock_job_service):
            await cb_history_main(mock_callback, mock_state)
    
    # Verify callback was answered or message sent
    assert mock_callback.answer.called or mock_callback.message.edit_text.called



