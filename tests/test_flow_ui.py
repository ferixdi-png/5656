from bot.handlers import flow


def _flatten_buttons(markup):
    return [
        (button.text, button.callback_data)
        for row in markup.inline_keyboard
        for button in row
    ]


def test_home_menu_buttons():
    markup = flow._home_keyboard()
    buttons = _flatten_buttons(markup)
    assert ("🚀 Быстрый старт (3 шага)", "home:quick") in buttons
    assert ("🎬 Видео для соцсетей", "home:video") in buttons
    assert ("🎨 Креативы/баннеры", "home:image") in buttons
    assert ("🔥 Топ инструменты", "home:top") in buttons
    assert ("⭐ Баланс / Оплата", "home:balance") in buttons
    assert ("🆘 Поддержка", "home:support") in buttons


def test_quick_templates_contains_catalog():
    markup = flow._quick_templates_keyboard()
    buttons = _flatten_buttons(markup)
    assert any(callback_data == "catalog:all:0" for _, callback_data in buttons)
