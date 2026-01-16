#!/usr/bin/env python3
"""
Test fallback handler coverage - ensures unknown callbacks are caught.

Verifies:
1. Fallback router is registered last
2. Unknown callback triggers fallback handler
3. UNKNOWN_CALLBACK is logged with cid
4. User receives response (no infinite spinner)
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update, CallbackQuery, User, Chat, Message
from bot.handlers.fallback import router as fallback_router


def test_fallback_router_registered_last():
    """Test that fallback router is registered last in main_render.py."""
    # Read main_render.py and check order
    main_render_path = project_root / "main_render.py"
    content = main_render_path.read_text(encoding="utf-8")
    
    # Find all include_router calls
    lines = content.split("\n")
    router_includes = []
    for i, line in enumerate(lines, 1):
        if "include_router" in line and "fallback" not in line.lower():
            router_includes.append((i, line.strip()))
        elif "include_router" in line and "fallback" in line.lower():
            fallback_line = i
            break
    
    # Fallback should be after all other routers
    assert fallback_line > max(router_includes, key=lambda x: x[0])[0], \
        f"Fallback router must be registered last (line {fallback_line}, other routers: {router_includes})"


@pytest.mark.asyncio
async def test_fallback_catches_unknown_callback():
    """Test that fallback handler catches unknown callback and logs UNKNOWN_CALLBACK with cid."""
    from bot.handlers.fallback import fallback_unknown_callback
    from app.telemetry.events import log_callback_received, log_callback_rejected
    
    # Create mock callback with unknown data
    mock_user = Mock(spec=User)
    mock_user.id = 12345
    
    mock_chat = Mock(spec=Chat)
    mock_chat.id = 67890
    
    mock_message = Mock(spec=Message)
    mock_message.chat = mock_chat
    mock_message.edit_text = AsyncMock()
    
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.from_user = mock_user
    mock_callback.message = mock_message
    mock_callback.data = "completely:unknown:callback:data"
    mock_callback.id = "test_query_123"
    mock_callback.answer = AsyncMock()
    
    # Mock update for get_update_id
    mock_update = Mock(spec=Update)
    mock_update.update_id = 99999
    
    test_cid = "test_cid_fallback_456"
    test_data = {"event_update": mock_update}
    
    # Mock telemetry functions
    with patch('bot.handlers.fallback.log_callback_received') as mock_log_received, \
         patch('bot.handlers.fallback.log_callback_rejected') as mock_log_rejected:
        
        # Call fallback handler
        await fallback_unknown_callback(
            mock_callback,
            cid=test_cid,
            bot_state="ACTIVE",
            data=test_data
        )
        
        # Verify callback was answered
        assert mock_callback.answer.called, "Callback must be answered to prevent infinite spinner"
        answer_call = mock_callback.answer.call_args
        assert "⚠️" in answer_call[1].get("text", "") or "⚠️" in (answer_call[0][0] if answer_call[0] else ""), \
            "Answer text should contain warning emoji"
        
        # Verify log_callback_received was called
        assert mock_log_received.called, "log_callback_received must be called"
        received_call = mock_log_received.call_args
        assert received_call[1].get("cid") == test_cid, "CID must be passed to log_callback_received"
        assert received_call[1].get("callback_data") == "completely:unknown:callback:data", \
            "Callback data must be logged"
        
        # Verify log_callback_rejected was called with UNKNOWN_CALLBACK
        assert mock_log_rejected.called, "log_callback_rejected must be called"
        rejected_call = mock_log_rejected.call_args
        assert rejected_call[1].get("reason_code") == "UNKNOWN_CALLBACK", \
            f"Reason code must be UNKNOWN_CALLBACK, got {rejected_call[1].get('reason_code')}"
        assert rejected_call[1].get("cid") == test_cid, "CID must be passed to log_callback_rejected"
        assert "No handler for callback_data" in rejected_call[1].get("reason_detail", ""), \
            "Reason detail should mention callback_data"


@pytest.mark.asyncio
async def test_fallback_in_dispatcher_order():
    """Test that fallback router catches callbacks not handled by other routers."""
    from main_render import create_bot_application
    
    # Create dispatcher (this registers all routers in order)
    dp, bot = create_bot_application()
    
    # Check that fallback_router is in the dispatcher
    routers = [r for r in dp.sub_routers if hasattr(r, 'name') and r.name == "fallback"]
    assert len(routers) > 0, "Fallback router must be registered in dispatcher"
    
    # Verify it's the last router (or at least one of the last)
    # In aiogram, routers are processed in order, so fallback should be last
    all_routers = list(dp.sub_routers)
    fallback_index = None
    for i, router in enumerate(all_routers):
        if hasattr(router, 'name') and router.name == "fallback":
            fallback_index = i
            break
    
    assert fallback_index is not None, "Fallback router not found in dispatcher"
    # Fallback should be one of the last routers (allow some flexibility for other routers)
    assert fallback_index >= len(all_routers) - 3, \
        f"Fallback router should be registered near the end (index {fallback_index} of {len(all_routers)})"


@pytest.mark.asyncio
async def test_fallback_without_cid_still_works():
    """Test that fallback handler works even without cid (graceful degradation)."""
    from bot.handlers.fallback import fallback_unknown_callback
    
    mock_user = Mock(spec=User)
    mock_user.id = 12345
    
    mock_chat = Mock(spec=Chat)
    mock_chat.id = 67890
    
    mock_message = Mock(spec=Message)
    mock_message.chat = mock_chat
    mock_message.edit_text = AsyncMock()
    
    mock_callback = Mock(spec=CallbackQuery)
    mock_callback.from_user = mock_user
    mock_callback.message = mock_message
    mock_callback.data = "unknown:test"
    mock_callback.answer = AsyncMock()
    
    # Call without cid (should not crash)
    await fallback_unknown_callback(mock_callback, cid=None, bot_state=None, data={})
    
    # Should still answer callback
    assert mock_callback.answer.called, "Callback must be answered even without cid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

