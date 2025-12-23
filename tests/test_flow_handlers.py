import types
from unittest.mock import AsyncMock

import pytest

from bot.handlers import core, flow, zero_silence
from bot.handlers.flow import FlowState


class FakeState:
    def __init__(self):
        self._data = {}
        self._state = None

    async def clear(self):
        self._data = {}
        self._state = None

    async def set_state(self, state):
        self._state = state

    async def get_state(self):
        return self._state

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def get_data(self):
        return dict(self._data)


class FakeMessage:
    def __init__(self, user_id=1):
        self.from_user = types.SimpleNamespace(id=user_id)
        self.chat = types.SimpleNamespace(id=123)
        self.message_id = 456
        self.answer = AsyncMock()
        self.edit_text = AsyncMock(return_value=self)


class FakeCallback:
    def __init__(self, data, user_id=1):
        self.data = data
        self.from_user = types.SimpleNamespace(id=user_id)
        self.message = FakeMessage(user_id=user_id)
        self.answer = AsyncMock()
        self.bot = types.SimpleNamespace(edit_message_text=AsyncMock())


@pytest.mark.asyncio
async def test_start_sends_home_menu(monkeypatch):
    state = FakeState()
    message = FakeMessage()
    monkeypatch.setattr(core.runtime_state, "lock_acquired", True)
    await core.start_cmd(message, state)
    assert message.answer.called
    assert await state.get_state() == FlowState.home


@pytest.mark.asyncio
async def test_unknown_callback_returns_home():
    callback = FakeCallback("unknown")
    await zero_silence.fallback_callback(callback)
    assert callback.message.answer.called


@pytest.mark.asyncio
async def test_flow_platform_goal_format_recommendations():
    state = FakeState()
    callback = FakeCallback("home:quick")
    await flow.quick_templates_cb(callback, state)
    platform_cb = FakeCallback("platform:tiktok")
    await flow.platform_cb(platform_cb, state)
    goal_cb = FakeCallback("goal:sales")
    await flow.goal_cb(goal_cb, state)
    content_cb = FakeCallback("content:video")
    await flow.content_type_cb(content_cb, state)
    data = await state.get_data()
    assert "recommendations" in data


@pytest.mark.asyncio
async def test_confirm_guard_blocks_repeat(monkeypatch):
    state = FakeState()
    model = flow._models()[0]
    await state.set_state(FlowState.generating)
    await state.update_data(model_id=model.get("model_id"), inputs={})
    callback = FakeCallback("confirm")
    generate = AsyncMock(return_value={"success": False, "message": "fail"})
    monkeypatch.setattr(flow, "generate_with_payment", generate)

    await flow.confirm_cb(callback, state)

    assert generate.call_count == 0
    assert callback.message.answer.called
