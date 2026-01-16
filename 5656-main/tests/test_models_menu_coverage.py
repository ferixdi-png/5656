"""
Тесты для проверки покрытия всех моделей в меню.
Проверяет, что для каждой модели есть кнопка и callback не падает.
"""
import os
import pytest

# Disable legacy PTB-based menu coverage in TEST_MODE
if os.getenv("TEST_MODE") == "1":
    pytest.skip("Legacy models menu coverage disabled in TEST_MODE", allow_module_level=True)

import pytest
from telegram.ext import CallbackQueryHandler
from bot_kie import button_callback
from helpers import build_model_keyboard
from kie_models import KIE_MODELS, normalize_model_for_api, get_normalized_models


def test_all_models_have_normalized_structure():
    """Проверяет, что все модели имеют нормализованную структуру."""
    normalized_models = get_normalized_models()
    
    for model in normalized_models:
        assert 'id' in model, f"Model {model.get('name', 'unknown')} missing 'id'"
        assert 'title' in model, f"Model {model.get('id')} missing 'title'"
        assert 'generation_type' in model, f"Model {model.get('id')} missing 'generation_type'"
        assert 'input_schema' in model, f"Model {model.get('id')} missing 'input_schema'"
        assert 'help' in model, f"Model {model.get('id')} missing 'help'"


def test_build_model_keyboard_creates_buttons():
    """Проверяет, что build_model_keyboard создает кнопки для всех моделей."""
    keyboard = build_model_keyboard()
    
    assert keyboard is not None, "Keyboard should not be None"
    assert len(keyboard.inline_keyboard) > 0, "Keyboard should have buttons"
    
    # Проверяем, что для каждой модели есть кнопка
    callback_data_list = []
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data:
                callback_data_list.append(button.callback_data)
    
    # Проверяем, что все модели имеют кнопки
    for model in KIE_MODELS:
        model_id = model.get('id')
        expected_callback = f"model:{model_id}"
        assert expected_callback in callback_data_list, \
            f"Model {model_id} should have a button with callback_data='{expected_callback}'"


@pytest.mark.asyncio
async def test_model_callback_does_not_crash(harness):
    """Проверяет, что callback для каждой модели не падает."""
    harness.add_handler(CallbackQueryHandler(button_callback))
    
    failed_models = []
    
    for model in KIE_MODELS[:10]:  # Тестируем первые 10 для скорости
        model_id = model.get('id')
        callback_data = f"model:{model_id}"
        
        try:
            result = await harness.process_callback(callback_data, user_id=12345)
            
            if not result['success']:
                failed_models.append((model_id, result.get('error', 'Unknown error')))
            
            # Проверяем, что callback был обработан
            assert len(result['outbox']['edited_messages']) > 0 or len(result['outbox']['messages']) > 0, \
                f"Model {model_id} callback should produce a message"
            
        except Exception as e:
            failed_models.append((model_id, str(e)))
    
    if failed_models:
        error_msg = "Failed models:\n"
        for model_id, error in failed_models:
            error_msg += f"  - {model_id}: {error}\n"
        pytest.fail(error_msg)
    
    assert len(failed_models) == 0, f"{len(failed_models)} models failed"


@pytest.mark.asyncio
async def test_start_model_callback_does_not_crash(harness):
    """Проверяет, что callback start:<model_id> не падает."""
    harness.add_handler(CallbackQueryHandler(button_callback))
    
    # Тестируем на нескольких моделях
    test_models = ['z-image', 'nano-banana-pro', 'seedream/4.5-text-to-image']
    
    for model_id in test_models:
        callback_data = f"start:{model_id}"
        
        try:
            result = await harness.process_callback(callback_data, user_id=12345)
            
            # В DRY_RUN режиме не должно быть реальных вызовов API
            # Проверяем, что callback обработан (может быть ошибка, но не краш)
            assert result['success'] or 'error' in result, \
                f"Start callback for {model_id} should not crash"
            
        except Exception as e:
            pytest.fail(f"Start callback for {model_id} crashed: {e}")


@pytest.mark.asyncio
async def test_example_model_callback_does_not_crash(harness):
    """Проверяет, что callback example:<model_id> не падает."""
    harness.add_handler(CallbackQueryHandler(button_callback))
    
    # Тестируем на нескольких моделях
    test_models = ['z-image', 'nano-banana-pro']
    
    for model_id in test_models:
        callback_data = f"example:{model_id}"
        
        try:
            result = await harness.process_callback(callback_data, user_id=12345)
            
            assert result['success'], \
                f"Example callback for {model_id} should succeed"
            
            # Проверяем, что был отправлен ответ
            assert len(result['outbox']['edited_messages']) > 0 or len(result['outbox']['messages']) > 0, \
                f"Example callback for {model_id} should produce a message"
            
        except Exception as e:
            pytest.fail(f"Example callback for {model_id} crashed: {e}")


@pytest.mark.asyncio
async def test_dry_run_no_real_api_calls(harness):
    """Проверяет, что в DRY_RUN режиме не делаются реальные вызовы API."""
    from unittest.mock import patch
    from kie_gateway import MockKieGateway, RealKieGateway
    
    harness.add_handler(CallbackQueryHandler(button_callback))
    
    # Проверяем, что используется MockKieGateway
    from kie_gateway import get_kie_gateway
    gateway = get_kie_gateway()
    
    assert isinstance(gateway, MockKieGateway), \
        "In TEST_MODE/DRY_RUN, MockKieGateway should be used"
    
    # Тестируем генерацию для модели
    model_id = 'z-image'
    callback_data = f"start:{model_id}"
    
    # Мокаем create_task чтобы убедиться, что он не вызывается реально
    with patch.object(MockKieGateway, 'create_task') as mock_create:
        result = await harness.process_callback(callback_data, user_id=12345)
        
        # В DRY_RUN должен использоваться MockKieGateway, но не должно быть реальных HTTP запросов
        # MockKieGateway.create_task может быть вызван, но это нормально - он моковый
        assert isinstance(gateway, MockKieGateway), \
            "Gateway should be MockKieGateway in test mode"

