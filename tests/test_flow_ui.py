from app.kie.builder import load_source_of_truth
from bot.handlers import flow


def _flatten_buttons(markup):
    return [
        (button.text, button.callback_data)
        for row in markup.inline_keyboard
        for button in row
    ]


def test_main_menu_buttons():
    markup = flow._main_menu_keyboard()
    buttons = _flatten_buttons(markup)
    callbacks = [cb for _, cb in buttons]
    # Check callback_data instead of text (emoji issues in terminal)
    assert "cat:t2v" in callbacks
    assert "cat:t2i" in callbacks
    assert "menu:balance" in callbacks
    assert "menu:search" in callbacks
    assert "menu:history" in callbacks


def test_categories_cover_registry():
    source = load_source_of_truth()
    # Only valid models (filtered)
    models = [m for m in source.get("models", []) if flow._is_valid_model(m)]
    model_categories = {
        (model.get("category", "other") or "other")
        for model in models
    }
    registry_categories = {category for category, _ in flow._categories_from_registry()}
    # All model categories should be in registry
    assert model_categories <= registry_categories


def test_category_keyboard_contains_registry_categories():
    category_markup = flow._category_keyboard()
    category_buttons = {
        callback_data
        for _, callback_data in _flatten_buttons(category_markup)
        if callback_data and callback_data.startswith("cat:")
    }
    registry_categories = {
        f"cat:{category}" for category, _ in flow._categories_from_registry()
    }
    assert registry_categories <= category_buttons
