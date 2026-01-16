"""
Интеграция Button Registry с существующим bot_kie.py
Этот модуль можно постепенно интегрировать в button_callback
"""

import logging
from pathlib import Path
from typing import Optional

from .registry import ButtonRegistry, CallbackRouter, CallbackType
from .validator import ButtonValidator
from .fallback import fallback_callback_handler

logger = logging.getLogger(__name__)

# Глобальные экземпляры (инициализируются при первом использовании)
_registry: Optional[ButtonRegistry] = None
_router: Optional[CallbackRouter] = None
_validator: Optional[ButtonValidator] = None


def get_button_system(project_root: Path) -> tuple[ButtonRegistry, CallbackRouter, ButtonValidator]:
    """Получает или создаёт систему кнопок"""
    global _registry, _router, _validator
    
    if _registry is None:
        _registry = ButtonRegistry()
        _router = CallbackRouter(_registry)
        _router.set_fallback_handler(fallback_callback_handler)
        _validator = ButtonValidator(project_root)
        
        # Регистрируем все известные callback'ы из bot_kie.py
        _register_all_callbacks(_registry)
        
        logger.info("✅ Button System инициализирован")
    
    return _registry, _router, _validator


def _register_all_callbacks(registry: ButtonRegistry):
    """Регистрирует все callback'ы из bot_kie.py"""
    # Это будет заполняться при интеграции
    # Пока регистрируем основные паттерны
    
    # Точные совпадения
    exact_callbacks = [
        "back_to_menu", "check_balance", "show_models", "all_models",
        "help_menu", "support_contact", "change_language", "admin_stats",
        "claim_gift", "cancel", "topup_balance", "my_generations"
    ]
    
    # Префиксы
    prefix_callbacks = [
        "language_select:", "gen_type:", "category:", "set_param:",
        "select_model:", "retry_generate:", "gen_view:", "gen_repeat:",
        "admin_gen_nav:", "admin_gen_view:", "payment_screenshot_nav:",
        "topup_amount:", "pay_stars:", "pay_sbp:", "set_language:"
    ]
    
    # Пока регистрируем как заглушки - реальные обработчики будут из bot_kie.py
    for callback in exact_callbacks:
        registry.register(
            callback,
            lambda update, context: None,  # Заглушка
            f"{callback}_handler",
            CallbackType.EXACT,
            f"Handler for {callback}"
        )
    
    for callback in prefix_callbacks:
        registry.register(
            callback,
            lambda update, context: None,  # Заглушка
            f"{callback}_handler",
            CallbackType.PREFIX,
            f"Handler for {callback} prefix"
        )


def validate_buttons_on_startup(project_root: Path):
    """Валидирует все кнопки при старте бота"""
    try:
        registry, router, validator = get_button_system(project_root)
        issues = validator.validate(registry)
        validator.print_report(issues)
        
        if issues["unhandled_callbacks"]:
            logger.warning(f"⚠️ Найдено {len(issues['unhandled_callbacks'])} необработанных callback'ов")
        else:
            logger.info("✅ Все callback'ы обработаны")
        
        return issues
    except Exception as e:
        logger.error(f"❌ Ошибка при валидации кнопок: {e}", exc_info=True)
        return {}


async def route_callback_with_fallback(
    callback_data: str,
    update,
    context,
    user_id: int = None,
    user_lang: str = 'ru',
    project_root: Path = None
) -> bool:
    """
    Роутит callback через новую систему с fallback
    
    Returns:
        bool: True если обработано, False если использован fallback
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    try:
        registry, router, validator = get_button_system(project_root)
        return await router.route(callback_data, update, context, user_id, user_lang)
    except Exception as e:
        logger.error(f"❌ Ошибка в route_callback_with_fallback: {e}", exc_info=True)
        # Используем fallback напрямую
        await fallback_callback_handler(callback_data, update, context, user_id, user_lang)
        return False







