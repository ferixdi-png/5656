#!/usr/bin/env python3
"""
Minimal tests to verify telemetry fixes are working.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from app.telemetry.events import log_callback_rejected
from app.telemetry.telemetry_helpers import get_update_id, get_event_ids
from aiogram.types import CallbackQuery, Update, Message, User, Chat
from unittest.mock import Mock


def test_log_callback_rejected_signature():
    """Test that log_callback_rejected accepts all parameter variants."""
    # Test 1: Basic call with reason_code and reason_detail
    log_callback_rejected(
        callback_data="test:data",
        reason_code="TEST",
        reason_detail="Test detail",
        cid="test_cid"
    )
    
    # Test 2: Call with user_id, chat_id, bot_state (via **extra)
    log_callback_rejected(
        callback_data="test:data",
        reason_code="TEST",
        reason_detail="Test detail",
        cid="test_cid",
        user_id=12345,
        chat_id=67890,
        bot_state="ACTIVE"
    )
    
    # Test 3: Call with deprecated reason parameter
    log_callback_rejected(
        callback_data="test:data",
        reason="TEST",
        reason_detail="Test detail",
        cid="test_cid"
    )
    
    # Test 4: Call with error_type and error_message
    log_callback_rejected(
        callback_data="test:data",
        reason_code="TEST",
        reason_detail="Test detail",
        error_type="ValueError",
        error_message="Test error",
        cid="test_cid"
    )
    
    # Test 5: Call with reason_detail in extra (backward compatibility)
    log_callback_rejected(
        callback_data="test:data",
        reason_code="TEST",
        cid="test_cid",
        reason_detail="Test detail in extra"
    )
    
    # Test 6: Minimal call (all optional)
    log_callback_rejected()
    
    assert True


def test_get_update_id_safe():
    """Test that get_update_id safely handles CallbackQuery without update_id."""
    # Create a mock CallbackQuery (which doesn't have update_id)
    callback = Mock(spec=CallbackQuery)
    callback.id = "test_callback_id"
    # CRITICAL: CallbackQuery should NOT have update_id attribute
    assert not hasattr(callback, 'update_id'), "CallbackQuery should not have update_id"
    
    # Create mock Update with update_id
    update = Mock(spec=Update)
    update.update_id = 12345
    
    # Test with data containing event_update
    data = {"event_update": update}
    result = get_update_id(callback, data)
    assert result == 12345, "Should extract update_id from event_update in data"
    
    # Test without data (should return None safely, not raise AttributeError)
    result = get_update_id(callback, {})
    assert result is None, "Should return None safely when update_id not available"
    
    # Test with legacy "update" key
    data_legacy = {"update": update}
    result = get_update_id(callback, data_legacy)
    assert result == 12345, "Should extract update_id from legacy 'update' key"
    
    # Test with Update event directly
    result = get_update_id(update, {})
    assert result == 12345, "Should extract update_id from Update event directly"


def test_get_event_ids_comprehensive():
    """Test get_event_ids extracts all IDs safely."""
    callback = Mock(spec=CallbackQuery)
    callback.id = "callback_123"
    callback.from_user = Mock(spec=User)
    callback.from_user.id = 12345
    callback.message = Mock(spec=Message)
    callback.message.chat = Mock(spec=Chat)
    callback.message.chat.id = 67890
    callback.message.message_id = 111
    
    update = Mock(spec=Update)
    update.update_id = 99999
    
    data = {"event_update": update}
    
    result = get_event_ids(callback, data)
    
    assert result["update_id"] == 99999
    assert result["callback_id"] == "callback_123"
    assert result["user_id"] == 12345
    assert result["chat_id"] == 67890
    assert result["message_id"] == 111


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

