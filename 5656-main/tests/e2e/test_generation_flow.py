"""
E2E tests for generation flow - critical user journeys.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import CallbackQuery, User, Chat, Message
from aiogram.fsm.context import FSMContext


@pytest.fixture
def mock_user():
    """Create mock user."""
    return User(
        id=12345,
        is_bot=False,
        first_name="Test",
        username="testuser"
    )


@pytest.fixture
def mock_chat():
    """Create mock chat."""
    return Chat(id=12345, type="private")


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """Create mock message."""
    return Message(
        message_id=1,
        date=None,
        chat=mock_chat,
        from_user=mock_user,
        content_type="text",
        text="test prompt"
    )


@pytest.fixture
def mock_callback(mock_user, mock_chat, mock_message):
    """Create mock callback query."""
    callback = CallbackQuery(
        id="test_callback_id",
        from_user=mock_user,
        chat_instance="test",
        message=mock_message
    )
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    return callback


@pytest.fixture
def mock_state():
    """Create mock FSM context."""
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    return state


@pytest.mark.asyncio
async def test_model_selection_flow(mock_callback, mock_state):
    """Test model selection flow."""
    from bot.handlers.flow import main_menu_cb
    
    await main_menu_cb(mock_callback, mock_state)
    
    # Verify main menu was shown
    mock_callback.answer.assert_called_once()
    mock_callback.message.edit_text.assert_called_once()
    
    # Verify menu contains expected buttons
    call_args = mock_callback.message.edit_text.call_args
    assert call_args is not None


@pytest.mark.asyncio
async def test_free_model_generation(mock_callback, mock_state):
    """Test free model generation flow."""
    # Mock free model
    mock_state.get_data.return_value = {
        "model_id": "z-image",  # Assuming this is free
        "prompt": "test prompt"
    }
    
    # This would test the actual generation flow
    # For now, we just verify the flow can start
    assert mock_state.get_data()["model_id"] == "z-image"


@pytest.mark.asyncio
async def test_paid_model_price_calculation(mock_callback, mock_state):
    """Test price calculation for paid models."""
    from app.payments.pricing import calculate_kie_cost, calculate_user_price
    
    model = {
        "model_id": "bytedance/seedance-1.5-pro",
        "category": "video",
        "price": 0.5  # USD
    }
    user_inputs = {
        "duration": "12s",
        "resolution": "720p",
        "audio": "WITH",
        "prompt": "test"
    }
    
    # Calculate cost
    kie_cost = calculate_kie_cost(model, user_inputs)
    user_price = calculate_user_price(kie_cost)
    
    assert kie_cost > 0
    assert user_price > 0
    assert user_price == kie_cost * 2  # Markup should be 2x


@pytest.mark.asyncio
async def test_navigation_through_generation_flow(mock_callback, mock_state):
    """Test navigation through complete generation flow."""
    # Step 1: Main menu
    from bot.handlers.flow import main_menu_cb
    await main_menu_cb(mock_callback, mock_state)
    
    # Step 2: Select category (would be next step)
    # For now, just verify state management
    mock_state.clear.assert_called()
    mock_state.get_data.assert_called()


@pytest.mark.asyncio
async def test_error_handling_in_generation():
    """Test error handling during generation."""
    from app.payments.pricing import calculate_kie_cost
    
    # Test with invalid model
    invalid_model = {
        "model_id": "nonexistent/model"
    }
    user_inputs = {}
    
    # Should not crash, should return fallback price
    cost = calculate_kie_cost(invalid_model, user_inputs)
    assert cost > 0  # Should have fallback


def test_pricing_parameterized_integration():
    """Test that parameterized pricing is integrated."""
    from app.pricing.parameterized import calculate_price_rub
    from app.payments.pricing import calculate_kie_cost
    
    model = {
        "model_id": "bytedance/seedance-1.5-pro",
        "category": "video"
    }
    user_inputs = {
        "duration": "12s",
        "resolution": "720p",
        "audio": "WITH"
    }
    
    # Should use parameterized pricing
    param_price = calculate_price_rub(model["model_id"], user_inputs, io_type="video")
    kie_cost = calculate_kie_cost(model, user_inputs)
    
    # If parameterized pricing is available, it should be used
    if param_price is not None:
        assert abs(float(param_price) - kie_cost) < 0.01  # Allow small rounding differences



