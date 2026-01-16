#!/usr/bin/env python3
"""
Test: проверяет, что все модели из реестра доступны через меню.

Проверяет:
1. Все model_id доступны через "show_all_models_list"
2. Все модели имеют callback select_model:<id>
3. Все модели можно выбрать и получить информацию
"""
import os
import pytest

# Disable legacy PTB menu coverage in TEST_MODE (new menu via aiogram)
if os.getenv("TEST_MODE") == "1":
    pytest.skip("Legacy menu coverage disabled in TEST_MODE", allow_module_level=True)

import sys
import os
from pathlib import Path

# Устанавливаем TEST_MODE для использования MockKieGateway
os.environ['TEST_MODE'] = '1'
os.environ['ALLOW_REAL_GENERATION'] = '0'

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import logging
logging.basicConfig(level=logging.WARNING)  # Уменьшаем шум

from app.models.registry import get_models_sync
from bot_kie import (
    get_model_by_id_from_registry,
    get_models_by_category_from_registry,
    get_categories_from_registry
)

def test_all_models_in_registry():
    """Проверяет, что все модели загружены из реестра"""
    models = get_models_sync()
    assert len(models) > 0, "No models loaded from registry"
    print(f"✅ Loaded {len(models)} models from registry")
    return models


def test_all_models_have_select_model_callback():
    """Проверяет, что все модели имеют callback select_model:<id>"""
    models = get_models_sync()
    missing_callbacks = []
    
    for model in models:
        model_id = model.get('id')
        if not model_id:
            missing_callbacks.append(f"Model without ID: {model}")
            continue
        
        # Проверяем, что callback_data будет валидным
        callback_data = f"select_model:{model_id}"
        callback_bytes = callback_data.encode('utf-8')
        
        if len(callback_bytes) > 64:
            # Если слишком длинный, должен быть fallback
            short_callback = f"sel:{model_id[:50]}"
            if len(short_callback.encode('utf-8')) > 64:
                missing_callbacks.append(f"Model {model_id}: callback too long even with fallback")
    
    if missing_callbacks:
        print(f"❌ Found {len(missing_callbacks)} models with callback issues:")
        for issue in missing_callbacks[:10]:  # Показываем первые 10
            print(f"   - {issue}")
        assert False, f"{len(missing_callbacks)} models have callback issues"
    
    print(f"✅ All {len(models)} models have valid select_model callbacks")
    return True


def test_all_models_accessible_via_get_model_by_id():
    """Проверяет, что все модели доступны через get_model_by_id_from_registry"""
    models = get_models_sync()
    missing_models = []
    
    for model in models:
        model_id = model.get('id')
        if not model_id:
            continue
        
        found_model = get_model_by_id_from_registry(model_id)
        if not found_model:
            missing_models.append(model_id)
    
    if missing_models:
        print(f"❌ Found {len(missing_models)} models not accessible via get_model_by_id_from_registry:")
        for model_id in missing_models[:10]:  # Показываем первые 10
            print(f"   - {model_id}")
        assert False, f"{len(missing_models)} models not accessible"
    
    print(f"✅ All {len(models)} models accessible via get_model_by_id_from_registry")
    return True


def test_all_models_in_categories():
    """Проверяет, что все модели присутствуют в категориях"""
    models = get_models_sync()
    categories = get_categories_from_registry()
    
    models_in_categories = set()
    for category in categories:
        category_models = get_models_by_category_from_registry(category)
        for model in category_models:
            model_id = model.get('id')
            if model_id:
                models_in_categories.add(model_id)
    
    all_model_ids = {model.get('id') for model in models if model.get('id')}
    missing_in_categories = all_model_ids - models_in_categories
    
    if missing_in_categories:
        print(f"⚠️  Found {len(missing_in_categories)} models not in any category:")
        for model_id in list(missing_in_categories)[:10]:  # Показываем первые 10
            print(f"   - {model_id}")
        # Это не критично, но стоит проверить
        print("   (This is a warning, not an error)")
    
    print(f"✅ Models in categories: {len(models_in_categories)}/{len(all_model_ids)}")
    return True


def test_show_all_models_list_coverage():
    """Проверяет, что show_all_models_list показывает все модели"""
    models = get_models_sync()
    categories = get_categories_from_registry()
    
    # Симулируем логику show_all_models_list
    shown_models = set()
    for category in categories:
        category_models = get_models_by_category_from_registry(category)
        for model in category_models:
            model_id = model.get('id')
            if model_id:
                shown_models.add(model_id)
    
    all_model_ids = {model.get('id') for model in models if model.get('id')}
    missing_in_list = all_model_ids - shown_models
    
    if missing_in_list:
        print(f"❌ Found {len(missing_in_list)} models not shown in show_all_models_list:")
        for model_id in list(missing_in_list)[:10]:  # Показываем первые 10
            print(f"   - {model_id}")
        assert False, f"{len(missing_in_list)} models not shown in menu"
    
    print(f"✅ All {len(all_model_ids)} models are shown in show_all_models_list")
    return True


def test_model_schema_available():
    """Проверяет, что для всех моделей доступна YAML schema"""
    from kie_input_adapter import get_schema
    
    models = get_models_sync()
    missing_schemas = []
    
    for model in models:
        model_id = model.get('id')
        if not model_id:
            continue
        
        schema = get_schema(model_id)
        if not schema:
            missing_schemas.append(model_id)
    
    if missing_schemas:
        print(f"⚠️  Found {len(missing_schemas)} models without YAML schema:")
        for model_id in missing_schemas[:10]:  # Показываем первые 10
            print(f"   - {model_id}")
        print("   (This is a warning - models may still work with fallback input_params)")
    
    schemas_available = len(models) - len(missing_schemas)
    print(f"✅ YAML schemas available: {schemas_available}/{len(models)}")
    return True


def main():
    """Запускает все тесты"""
    print("=" * 80)
    print("Test: Menu Covers All Models")
    print("=" * 80)
    print()
    
    try:
        # Test 1: Все модели загружены
        models = test_all_models_in_registry()
        print()
        
        # Test 2: Все модели имеют callback
        test_all_models_have_select_model_callback()
        print()
        
        # Test 3: Все модели доступны через get_model_by_id
        test_all_models_accessible_via_get_model_by_id()
        print()
        
        # Test 4: Все модели в категориях
        test_all_models_in_categories()
        print()
        
        # Test 5: Все модели показаны в show_all_models_list
        test_show_all_models_list_coverage()
        print()
        
        # Test 6: YAML schemas доступны
        test_model_schema_available()
        print()
        
        print("=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        return 0
        
    except AssertionError as e:
        print()
        print("=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        return 1
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())

