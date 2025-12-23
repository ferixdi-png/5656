import importlib
import os
import sys


def test_main_render_imports_aiogram_only():
    os.environ.setdefault("DRY_RUN", "1")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
    import main_render  # noqa: F401

    assert "telegram" not in sys.modules
    assert "telegram.ext" not in sys.modules


def test_python_telegram_bot_not_required():
    spec = importlib.util.find_spec("telegram")
    if spec is None:
        assert spec is None
    else:
        assert "telegram" not in sys.modules
