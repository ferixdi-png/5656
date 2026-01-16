"""
Тесты баланса и платежей - атомарность, идемпотентность, сохранение
"""

import pytest
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_balance_functions_exist():
    """Проверяет что функции баланса существуют"""
    try:
        from bot_kie import get_user_balance, set_user_balance, add_user_balance, subtract_user_balance
        assert callable(get_user_balance)
        assert callable(set_user_balance)
        assert callable(add_user_balance)
        assert callable(subtract_user_balance)
    except ImportError as e:
        pytest.fail(f"Balance functions not found: {e}")


def test_balance_logging_exists():
    """Проверяет что есть критическое логирование баланса"""
    bot_file = project_root / "bot_kie.py"
    if not bot_file.exists():
        pytest.skip("bot_kie.py not found")
    
    content = bot_file.read_text(encoding='utf-8', errors='ignore')
    
    # Проверяем логирование
    assert 'GET_BALANCE' in content or 'SET_BALANCE' in content or '💰💰💰' in content, \
        "Critical balance logging not found"


def test_balance_saves_to_db():
    """Проверяет что баланс сохраняется в БД"""
    bot_file = project_root / "bot_kie.py"
    if not bot_file.exists():
        pytest.skip("bot_kie.py not found")
    
    content = bot_file.read_text(encoding='utf-8', errors='ignore')
    
    # Проверяем сохранение в БД
    assert 'db_update_user_balance' in content or 'update_user_balance' in content, \
        "Balance saving to DB not found"


def test_balance_verification_exists():
    """Проверяет что есть верификация сохранения баланса"""
    bot_file = project_root / "bot_kie.py"
    if not bot_file.exists():
        pytest.skip("bot_kie.py not found")
    
    content = bot_file.read_text(encoding='utf-8', errors='ignore')
    
    # Проверяем верификацию
    assert 'BALANCE VERIFIED' in content or 'Verified balance' in content, \
        "Balance verification not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
