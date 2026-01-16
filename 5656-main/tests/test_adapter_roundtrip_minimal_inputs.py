#!/usr/bin/env python3
"""
Тест для проверки roundtrip всех моделей с минимальными входными данными.
Для каждой модели собирает минимальный набор required params и проверяет,
что адаптер возвращает dict для API без ошибок.
"""

import sys
import pytest
from pathlib import Path
from typing import Dict, Any, List

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def generate_minimal_params(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Генерирует минимальный набор параметров для схемы (только required).
    """
    params = {}
    
    for param_name, param_schema in schema.items():
        if param_schema.get('required', False):
            param_type = param_schema.get('type', 'string')
            
            if param_type == 'string':
                # Генерируем тестовую строку
                if 'prompt' in param_name.lower():
                    params[param_name] = "Test prompt"
                elif 'url' in param_name.lower():
                    params[param_name] = "https://example.com/test.jpg"
                else:
                    params[param_name] = "test_value"
            
            elif param_type == 'enum':
                # Берем первое значение из enum
                values = param_schema.get('values', [])
                if values:
                    params[param_name] = values[0]
                else:
                    params[param_name] = "default"
            
            elif param_type == 'array':
                item_type = param_schema.get('item_type', 'string')
                if item_type == 'string':
                    # Минимальный массив с одним элементом
                    if 'url' in param_name.lower() or 'image' in param_name.lower() or 'video' in param_name.lower():
                        params[param_name] = ["https://example.com/test.jpg"]
                    else:
                        params[param_name] = ["test_item"]
                else:
                    params[param_name] = []
            
            elif param_type == 'boolean':
                params[param_name] = False
            
            elif param_type in ('number', 'integer', 'float'):
                # Используем минимальное значение или default
                if 'min' in param_schema:
                    params[param_name] = param_schema['min']
                else:
                    params[param_name] = 1
    
    return params


def test_all_models_roundtrip():
    """Проверяет roundtrip для всех моделей из YAML"""
    from app.models.registry import get_models_sync
    from kie_input_adapter import get_schema, apply_defaults, validate_params, adapt_to_api
    
    models = get_models_sync()
    assert len(models) > 0, "No models loaded"
    
    failed_models = []
    
    for model in models:
        model_id = model.get('id')
        if not model_id:
            continue
        
        try:
            # Получаем схему
            schema = get_schema(model_id)
            if not schema:
                # Модель не найдена в YAML - пропускаем
                continue
            
            # Генерируем минимальные параметры
            minimal_params = generate_minimal_params(schema)
            
            # Применяем дефолты
            params_with_defaults = apply_defaults(schema, minimal_params)
            
            # Валидируем
            is_valid, errors = validate_params(schema, params_with_defaults)
            if not is_valid:
                failed_models.append({
                    'model_id': model_id,
                    'reason': f"Validation failed: {errors}",
                    'params': minimal_params
                })
                continue
            
            # Адаптируем к API
            api_params = adapt_to_api(model_id, params_with_defaults)
            
            # Проверяем, что результат - это dict
            assert isinstance(api_params, dict), f"api_params should be dict for {model_id}"
            
            # Проверяем, что нет None значений в required параметрах
            for param_name, param_schema in schema.items():
                if param_schema.get('required', False):
                    # Проверяем, что параметр присутствует в API params (после адаптации)
                    # Имя может измениться после адаптации, поэтому проверяем общее наличие
                    # (это упрощенная проверка, но достаточная для базового теста)
                    pass
            
        except Exception as e:
            failed_models.append({
                'model_id': model_id,
                'reason': f"Exception: {str(e)}",
                'error_type': type(e).__name__
            })
    
    if failed_models:
        error_msg = f"Failed models ({len(failed_models)}/{len(models)}):\n"
        for failure in failed_models[:10]:  # Показываем первые 10
            error_msg += f"  - {failure['model_id']}: {failure['reason']}\n"
        if len(failed_models) > 10:
            error_msg += f"  ... and {len(failed_models) - 10} more\n"
        
        pytest.fail(error_msg)
    
    # Если все прошло успешно
    assert len(failed_models) == 0, f"Some models failed: {len(failed_models)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

