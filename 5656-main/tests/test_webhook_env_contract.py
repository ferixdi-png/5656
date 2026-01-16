"""
Tests for webhook environment contract.
"""

import os
import pytest

from app.utils.startup_validation import validate_webhook_requirements


@pytest.fixture(autouse=True)
def clear_webhook_env():
    old_env = {
        "BOT_MODE": os.environ.get("BOT_MODE"),
        "WEBHOOK_BASE_URL": os.environ.get("WEBHOOK_BASE_URL"),
        "WEBHOOK_URL": os.environ.get("WEBHOOK_URL"),
    }
    for key in old_env:
        os.environ.pop(key, None)
    yield
    for key, value in old_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_webhook_mode_accepts_base_url_only():
    os.environ["BOT_MODE"] = "webhook"
    os.environ["WEBHOOK_BASE_URL"] = "https://example.com"

    validate_webhook_requirements()


def test_webhook_mode_requires_base_url():
    os.environ["BOT_MODE"] = "webhook"

    with pytest.raises(ValueError, match="WEBHOOK_BASE_URL"):
        validate_webhook_requirements()
