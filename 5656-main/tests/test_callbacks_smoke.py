"""
Smoke тесты для всех callback_data.
Проверяет, что ни один callback не падает с исключением.
"""
import os
import pytest

# Disable legacy PTB-based tests in TEST_MODE (new stack uses aiogram)
if os.getenv("TEST_MODE") == "1":
    pytest.skip("Legacy PTB callbacks smoke disabled in TEST_MODE", allow_module_level=True)

import pytest
from telegram.ext import CallbackQueryHandler
from bot_kie import button_callback
from helpers import build_main_menu_keyboard
from kie_models import KIE_MODELS


def collect_callback_data_from_keyboard(keyboard):
    """Рекурсивно собирает все callback_data из клавиатуры."""
    callbacks = set()
    
    for row in keyboard:
        for button in row:
            if hasattr(button, 'callback_data') and button.callback_data:
                callbacks.add(button.callback_data)
    
    return callbacks


def get_all_known_callbacks():
    """Собирает все известные callback_data из кода."""
    callbacks = set()
    
    # Добавляем основные callback_data из паттернов в bot_kie.py
    # Это основные паттерны, которые используются в ConversationHandler
    known_patterns = [
        'show_models',
        'show_all_models_list',
        'category:',
        'all_models',
        'gen_type:',
        'free_tools',
        'check_balance',
        'language_select:',
        'change_language',
        'copy_bot',
        'claim_gift',
        'help_menu',
        'support_contact',
        'select_model:',
        'admin_stats',
        'admin_view_generations',
        'admin_gen_nav:',
        'admin_gen_view:',
        'admin_settings',
        'admin_set_currency_rate',
        'admin_search',
        'admin_add',
        'view_payment_screenshots',
        'payment_screenshot_nav:',
        'admin_payments_back',
        'admin_promocodes',
        'admin_broadcast',
        'admin_create_broadcast',
        'admin_broadcast_stats',
        'admin_test_ocr',
        'admin_user_mode',
        'admin_back_to_admin',
        'back_to_menu',
        'topup_balance',
        'topup_amount:',
        'topup_custom',
        'referral_info',
        'generate_again',
        'my_generations',
        'gen_view:',
        'gen_repeat:',
        'gen_history:',
        'tutorial_start',
        'tutorial_step',
        'tutorial_complete',
        'confirm_generate',
        'retry_generate:',
        'cancel',
        'back_to_previous_step',
        'set_param:',
        'add_image',
        'skip_image',
        'image_done',
        'add_audio',
        'skip_audio',
        'pay_stars:',
        'pay_sbp:',
    ]
    
    callbacks.update(known_patterns)
    
    # Добавляем callback_data для моделей
    for model in KIE_MODELS[:10]:  # Первые 10 для скорости
        model_id = model.get('id', '')
        if model_id:
            callbacks.add(f'select_model:{model_id}')
    
    return callbacks


@pytest.mark.asyncio
async def test_all_known_callbacks_no_crash(harness):
    """Тест, что все известные callback_data не падают."""
    harness.add_handler(CallbackQueryHandler(button_callback))
    
    known_callbacks = get_all_known_callbacks()
    
    failed_callbacks = []
    
    for callback_data in known_callbacks:
        try:
            result = await harness.process_callback(callback_data, user_id=12345)
            
            if not result['success']:
                failed_callbacks.append((callback_data, result.get('error')))
            
            # Проверяем, что callback был обработан (ответили на него)
            if len(result['outbox']['callback_answers']) == 0:
                # Это может быть нормально для некоторых callback'ов
                pass
            
        except Exception as e:
            failed_callbacks.append((callback_data, str(e)))
    
    if failed_callbacks:
        error_msg = "Failed callbacks:\n"
        for cb, error in failed_callbacks:
            error_msg += f"  - {cb}: {error}\n"
        pytest.fail(error_msg)
    
    assert len(failed_callbacks) == 0, f"{len(failed_callbacks)} callbacks failed"


@pytest.mark.asyncio
async def test_unknown_callback_handled_gracefully(harness):
    """Тест, что неизвестный callback обрабатывается корректно."""
    harness.add_handler(CallbackQueryHandler(button_callback))
    
    # Тестируем неизвестный callback
    unknown_callbacks = [
        'unknown_callback_12345',
        'old_button_data',
        'deprecated_feature',
    ]
    
    for callback_data in unknown_callbacks:
        result = await harness.process_callback(callback_data, user_id=12345)
        
        # Должен обработаться без исключения
        assert result['success'], f"Unknown callback {callback_data} should not crash"
        
        # Должен быть ответ на callback
        assert len(result['outbox']['callback_answers']) > 0, \
            f"Should answer unknown callback {callback_data}"

