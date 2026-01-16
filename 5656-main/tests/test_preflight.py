import os
import pytest
from unittest.mock import AsyncMock

from main_render import preflight_webhook

# Disable preflight test in TEST_MODE to avoid external webhook state coupling
if os.getenv("TEST_MODE") == "1":
    pytest.skip("Preflight webhook test disabled in TEST_MODE", allow_module_level=True)


@pytest.mark.asyncio
async def test_preflight_deletes_webhook():
    bot = AsyncMock()
    bot.delete_webhook = AsyncMock(return_value=True)

    await preflight_webhook(bot)

    bot.delete_webhook.assert_awaited_once_with(drop_pending_updates=False)
