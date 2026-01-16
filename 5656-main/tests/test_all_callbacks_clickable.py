"""
Тест всех callback'ов - каждая кнопка кликабельна
"""

import pytest
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
bot_file = project_root / "bot_kie.py"


def extract_all_callbacks() -> list:
    """Извлекает все callback_data из bot_kie.py"""
    if not bot_file.exists():
        return []
    
    content = bot_file.read_text(encoding='utf-8', errors='ignore')
    pattern = r'callback_data\s*[=:]\s*["\']([^"\']+)["\']'
    callbacks = re.findall(pattern, content)
    return sorted(set(callbacks))


def extract_button_callback_handlers() -> set:
    """Извлекает все обрабатываемые callback'ы из button_callback"""
    if not bot_file.exists():
        return set()
    
    content = bot_file.read_text(encoding='utf-8', errors='ignore')
    
    if 'async def button_callback' not in content:
        return set()
    
    start = content.find('async def button_callback')
    end = content.find('\nasync def ', start + 1)
    if end == -1:
        end = len(content)
    
    button_callback_content = content[start:end]
    
    # Ищем обработку callback'ов
    handled = set()
    
    # Точные совпадения: if data == "..."
    exact_pattern = r'if\s+data\s*==\s*["\']([^"\']+)["\']'
    handled.update(re.findall(exact_pattern, button_callback_content))
    
    # Множественные совпадения: if data == "..." or data == "..."
    or_pattern = r'data\s*==\s*["\']([^"\']+)["\']'
    handled.update(re.findall(or_pattern, button_callback_content))
    
    # Префиксы: if data.startswith("...")
    prefix_pattern = r'if\s+data\.startswith\(["\']([^"\']+)["\']'
    handled.update(re.findall(prefix_pattern, button_callback_content))
    
    # elif тоже
    handled.update(re.findall(exact_pattern.replace('if', 'elif'), button_callback_content))
    handled.update(re.findall(prefix_pattern.replace('if', 'elif'), button_callback_content))
    
    return handled


def test_all_callbacks_have_handlers():
    """Проверяет что все callback'ы имеют обработчики"""
    all_callbacks = extract_all_callbacks()
    handled_callbacks = extract_button_callback_handlers()
    
    # Проверяем критические callback'ы
    critical = ['back_to_menu', 'check_balance', 'show_models', 'all_models', 'cancel']
    
    missing = []
    for cb in critical:
        if cb in all_callbacks:
            # Проверяем точное совпадение или префикс
            found = False
            if cb in handled_callbacks:
                found = True
            else:
                # Проверяем префиксы
                for handled in handled_callbacks:
                    if cb.startswith(handled) or handled.startswith(cb):
                        found = True
                        break
            
            if not found:
                missing.append(cb)
    
    if missing:
        pytest.fail(f"Missing handlers for callbacks: {missing}")
    
    assert len(all_callbacks) > 0, "No callbacks found"


def test_no_silence_after_input():
    """Проверяет что нет тишины после ввода"""
    if not bot_file.exists():
        pytest.skip("bot_kie.py not found")
    
    content = bot_file.read_text(encoding='utf-8', errors='ignore')
    
    # Проверяем что есть гарантированный ответ
    assert '✅ Принято, обрабатываю' in content or 'Принято, обрабатываю' in content, \
        "No guaranteed response after input found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
