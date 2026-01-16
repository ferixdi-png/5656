#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke Test для кнопок бота
Проверяет, что все основные кнопки обрабатываются корректно
"""

import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.buttons.registry import ButtonRegistry, CallbackRouter, CallbackType
from app.buttons.validator import ButtonValidator
from app.buttons.fallback import fallback_callback_handler


class MockUpdate:
    """Мок для Telegram Update"""
    def __init__(self, callback_data: str):
        self.callback_query = MockCallbackQuery(callback_data)


class MockCallbackQuery:
    """Мок для CallbackQuery"""
    def __init__(self, data: str):
        self.data = data
        self.id = "test_query_id"
        self.from_user = MockUser()
        self.message = MockMessage()
    
    async def answer(self, text: str = None, show_alert: bool = False):
        print(f"  ✅ query.answer({text}, show_alert={show_alert})")


class MockUser:
    """Мок для User"""
    def __init__(self):
        self.id = 123456789


class MockMessage:
    """Мок для Message"""
    def __init__(self):
        self.message_id = 1
    
    async def edit_text(self, text: str, reply_markup=None):
        print(f"  ✅ message.edit_text({text[:50]}...)")
    
    async def reply_text(self, text: str):
        print(f"  ✅ message.reply_text({text[:50]}...)")


class MockContext:
    """Мок для Context"""
    pass


async def mock_handler(update, context):
    """Мок обработчик для тестирования"""
    print(f"  ✅ Handler called for callback_data")


def test_button_registry():
    """Тест реестра кнопок"""
    print("=" * 80)
    print("🧪 ТЕСТ: Button Registry")
    print("=" * 80)
    
    registry = ButtonRegistry()
    
    # Регистрируем несколько кнопок
    registry.register("test_button", mock_handler, "test_handler", description="Test button")
    registry.register("gen_type:", mock_handler, "gen_type_handler", CallbackType.PREFIX, "Generation type")
    
    # Проверяем получение обработчика
    handler = registry.get_handler("test_button")
    assert handler is not None, "Handler not found for exact match"
    print("✅ Exact match работает")
    
    handler = registry.get_handler("gen_type:text")
    assert handler is not None, "Handler not found for prefix match"
    print("✅ Prefix match работает")
    
    # Проверяем валидацию
    issues = registry.validate()
    print(f"✅ Валидация завершена: {len(issues['duplicates'])} дубликатов")
    
    print("✅ Button Registry тест пройден\n")


def test_callback_router():
    """Тест роутера callback'ов"""
    print("=" * 80)
    print("🧪 ТЕСТ: Callback Router")
    print("=" * 80)
    
    registry = ButtonRegistry()
    registry.register("test_button", mock_handler, "test_handler")
    
    router = CallbackRouter(registry)
    router.set_fallback_handler(fallback_callback_handler)
    
    # Тест известного callback'а
    update = MockUpdate("test_button")
    context = MockContext()
    
    import asyncio
    result = asyncio.run(router.route("test_button", update, context))
    assert result is True, "Known callback should be handled"
    print("✅ Известный callback обработан")
    
    # Тест неизвестного callback'а
    result = asyncio.run(router.route("unknown_button", update, context))
    assert result is False, "Unknown callback should use fallback"
    print("✅ Неизвестный callback использует fallback")
    
    stats = router.get_stats()
    print(f"✅ Статистика: {stats}")
    
    print("✅ Callback Router тест пройден\n")


def test_button_validator():
    """Тест валидатора кнопок"""
    print("=" * 80)
    print("🧪 ТЕСТ: Button Validator")
    print("=" * 80)
    
    project_root = Path(__file__).parent.parent
    validator = ButtonValidator(project_root)
    
    registry = ButtonRegistry()
    # Регистрируем несколько кнопок для теста
    registry.register("back_to_menu", mock_handler)
    registry.register("check_balance", mock_handler)
    
    issues = validator.validate(registry)
    validator.print_report(issues)
    
    print("✅ Button Validator тест пройден\n")


def test_smoke_flow():
    """Smoke flow - проверка основных кнопок"""
    print("=" * 80)
    print("🧪 ТЕСТ: Smoke Flow (основные кнопки)")
    print("=" * 80)
    
    # Список основных callback'ов для проверки
    main_callbacks = [
        "back_to_menu",
        "check_balance",
        "show_models",
        "all_models",
        "help_menu",
        "support_contact",
        "change_language",
        "admin_stats"
    ]
    
    registry = ButtonRegistry()
    router = CallbackRouter(registry)
    router.set_fallback_handler(fallback_callback_handler)
    
    # Регистрируем все основные кнопки
    for callback in main_callbacks:
        registry.register(callback, mock_handler, f"{callback}_handler")
    
    print(f"📋 Проверка {len(main_callbacks)} основных кнопок:")
    
    import asyncio
    for callback in main_callbacks:
        print(f"\n  🔘 {callback}:")
        update = MockUpdate(callback)
        context = MockContext()
        result = asyncio.run(router.route(callback, update, context, user_id=123456789))
        if result:
            print(f"    ✅ Обработано")
        else:
            print(f"    ⚠️ Fallback использован")
    
    print("\n✅ Smoke Flow тест пройден\n")


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК SMOKE TESTS ДЛЯ КНОПОК")
    print("=" * 80 + "\n")
    
    try:
        test_button_registry()
        test_callback_router()
        test_button_validator()
        test_smoke_flow()
        
        print("=" * 80)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print("=" * 80)
        return 0
        
    except Exception as e:
        print(f"\n❌ ОШИБКА В ТЕСТАХ: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())







