"""Webhook receiver smoke test (no network)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from aiohttp.test_utils import make_mocked_request

from app.utils.healthcheck import webhook_handler


@pytest.mark.asyncio
async def test_webhook_handler_processes_update():
    app = MagicMock()
    app.bot = MagicMock()
    app.process_update = AsyncMock()

    payload = {"update_id": 1, "message": {"message_id": 1, "text": "hi"}}
    request = make_mocked_request("POST", "/webhook/secret", payload=payload)
    request._match_info = {"secret": "secret"}

    response = await webhook_handler(
        request,
        application=app,
        secret_path="secret",
        secret_token="",
    )

    assert response.status == 200
    app.process_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_handler_ignores_duplicate_update():
    app = MagicMock()
    app.bot = MagicMock()
    app.process_update = AsyncMock()

    payload = {"update_id": 42, "message": {"message_id": 1, "text": "hi"}}
    # First request
    req1 = make_mocked_request("POST", "/webhook/secret", payload=payload, headers={"X-Forwarded-For": "1.2.3.4"})
    req1._match_info = {"secret": "secret"}

    resp1 = await webhook_handler(req1, application=app, secret_path="secret", secret_token="")
    assert resp1.status == 200
    app.process_update.assert_awaited_once()

    # Second request with same update_id should be ignored
    req2 = make_mocked_request("POST", "/webhook/secret", payload=payload, headers={"X-Forwarded-For": "1.2.3.4"})
    req2._match_info = {"secret": "secret"}

    resp2 = await webhook_handler(req2, application=app, secret_path="secret", secret_token="")
    assert resp2.status == 200
    # Still only once
    app.process_update.assert_awaited_once()
