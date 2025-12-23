import types
from unittest.mock import AsyncMock

import pytest

from bot.handlers import zero_silence


class FakeCallback:
    def __init__(self):
        self.data = "unknown"
        self.from_user = types.SimpleNamespace(id=1)
        self.message = types.SimpleNamespace(answer=AsyncMock())
        self.answer = AsyncMock()


@pytest.mark.asyncio
async def test_unknown_callback_message():
    callback = FakeCallback()
    await zero_silence.fallback_callback(callback)
    assert callback.message.answer.called
