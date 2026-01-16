"""
Golden-path tests for core flows (start + generation outcomes).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot_kie
from app.payments import integration


@pytest.mark.asyncio
async def test_start_command_replies(monkeypatch):
    user = MagicMock()
    user.id = 123
    user.language_code = "ru"
    user.mention_html.return_value = "Test User"

    message = MagicMock()
    message.reply_html = AsyncMock()

    update = MagicMock()
    update.effective_user = user
    update.message = message

    monkeypatch.setattr(bot_kie, "has_user_language_set", lambda user_id: True)
    monkeypatch.setattr(bot_kie, "get_user_language", lambda user_id: "ru")
    monkeypatch.setattr(bot_kie, "get_generation_types", lambda: ["image"])
    monkeypatch.setattr(bot_kie, "get_models_sync", lambda: [{"id": "model"}])
    monkeypatch.setattr(bot_kie, "get_user_free_generations_remaining", lambda user_id: 1)
    monkeypatch.setattr(bot_kie, "is_new_user", lambda user_id: True)
    monkeypatch.setattr(bot_kie, "get_user_referral_link", lambda user_id: "link")
    monkeypatch.setattr(bot_kie, "get_user_referrals", lambda user_id: [])
    monkeypatch.setattr(bot_kie, "get_fake_online_count", lambda: 5)
    monkeypatch.setattr(bot_kie, "t", lambda key, lang, **kwargs: "welcome")
    monkeypatch.setattr(bot_kie, "build_main_menu_keyboard", lambda *args, **kwargs: MagicMock())

    await bot_kie.start(update, MagicMock())

    message.reply_html.assert_awaited()


@pytest.mark.asyncio
async def test_generation_success_commits_charge(monkeypatch):
    class DummyGenerator:
        async def generate(self, *args, **kwargs):
            return {"success": True, "result_urls": ["https://example.com"]}

    charge_manager = MagicMock()
    charge_manager.create_pending_charge = AsyncMock(return_value={"status": "pending"})
    charge_manager.commit_charge = AsyncMock(return_value={"status": "committed", "message": "ok"})
    charge_manager.release_charge = AsyncMock(return_value={"status": "released", "message": "ok"})
    charge_manager.add_to_history = MagicMock()

    monkeypatch.setattr(integration, "KieGenerator", DummyGenerator)
    monkeypatch.setattr(integration, "is_free_model", lambda model_id: False)
    monkeypatch.setattr(integration, "track_generation", AsyncMock())

    result = await integration.generate_with_payment(
        model_id="model",
        user_inputs={"prompt": "hi"},
        user_id=1,
        amount=10.0,
        charge_manager=charge_manager,
        reserve_balance=True,
    )

    assert result["payment_status"] == "committed"
    charge_manager.commit_charge.assert_awaited_once()
    charge_manager.release_charge.assert_not_awaited()


@pytest.mark.asyncio
async def test_generation_failure_releases_charge(monkeypatch):
    class DummyGenerator:
        async def generate(self, *args, **kwargs):
            return {"success": False, "message": "fail", "error_code": "ERR", "result_urls": []}

    charge_manager = MagicMock()
    charge_manager.create_pending_charge = AsyncMock(return_value={"status": "pending"})
    charge_manager.commit_charge = AsyncMock(return_value={"status": "committed", "message": "ok"})
    charge_manager.release_charge = AsyncMock(return_value={"status": "released", "message": "ok"})
    charge_manager.add_to_history = MagicMock()

    monkeypatch.setattr(integration, "KieGenerator", DummyGenerator)
    monkeypatch.setattr(integration, "is_free_model", lambda model_id: False)
    monkeypatch.setattr(integration, "track_generation", AsyncMock())

    result = await integration.generate_with_payment(
        model_id="model",
        user_inputs={"prompt": "hi"},
        user_id=1,
        amount=10.0,
        charge_manager=charge_manager,
        reserve_balance=True,
    )

    assert result["payment_status"] == "released"
    charge_manager.release_charge.assert_awaited_once()
    charge_manager.commit_charge.assert_not_awaited()
