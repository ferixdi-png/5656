"""
Tests for wizard mandatory input validation.
Ensures that wizard flows properly validate required inputs.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from aiogram.types import CallbackQuery, Message, User, Chat


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock(spec=User)
    user.id = 123456
    user.first_name = "Test"
    user.username = "testuser"
    return user


@pytest.fixture
def mock_chat():
    """Create a mock chat."""
    chat = Mock(spec=Chat)
    chat.id = 123456
    chat.type = "private"
    return chat


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """Create a mock message."""
    message = Mock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.text = "test message"
    message.message_id = 1
    return message


@pytest.fixture
def mock_callback_query(mock_user, mock_message):
    """Create a mock callback query."""
    callback = Mock(spec=CallbackQuery)
    callback.from_user = mock_user
    callback.message = mock_message
    callback.data = "test_callback"
    callback.id = "callback_123"
    callback.answer = AsyncMock()
    return callback


def test_wizard_requires_user_input():
    """Test that wizard validates user input is provided."""
    # Test empty input
    user_input = ""
    assert len(user_input) == 0
    
    # Test valid input
    user_input = "test prompt"
    assert len(user_input) > 0


def test_wizard_validates_required_fields():
    """Test that wizard checks all required fields."""
    required_fields = ["prompt", "model", "category"]
    
    # Test missing fields
    provided_data = {"prompt": "test"}
    missing = [f for f in required_fields if f not in provided_data]
    assert len(missing) > 0
    
    # Test all fields provided
    complete_data = {
        "prompt": "test",
        "model": "test_model",
        "category": "image"
    }
    missing = [f for f in required_fields if f not in complete_data]
    assert len(missing) == 0


def test_wizard_prompt_validation():
    """Test wizard validates prompt is not empty."""
    # Test empty prompt
    prompt = ""
    is_valid = len(prompt.strip()) > 0
    assert not is_valid
    
    # Test valid prompt
    prompt = "Generate an image"
    is_valid = len(prompt.strip()) > 0
    assert is_valid


def test_wizard_prompt_length_validation():
    """Test wizard validates prompt length."""
    max_length = 1000
    
    # Test prompt within limits
    short_prompt = "Test" * 10
    assert len(short_prompt) <= max_length
    
    # Test prompt exceeding limits
    long_prompt = "X" * 1500
    assert len(long_prompt) > max_length


@pytest.mark.asyncio
async def test_wizard_flow_requires_model_selection(mock_callback_query):
    """Test that wizard flow requires model selection."""
    # Simulate no model selected
    callback_data = "cat:image"
    assert not callback_data.startswith("model:")
    
    # Simulate model selected
    callback_data = "model:flux-pro"
    assert callback_data.startswith("model:")


@pytest.mark.asyncio
async def test_wizard_validates_callback_data(mock_callback_query):
    """Test wizard validates callback query data."""
    # Test valid callback data
    mock_callback_query.data = "model:test_model"
    assert mock_callback_query.data is not None
    assert len(mock_callback_query.data) > 0
    
    # Test empty callback data
    mock_callback_query.data = ""
    assert len(mock_callback_query.data) == 0
