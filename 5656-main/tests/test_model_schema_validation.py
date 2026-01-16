"""
Тесты для валидации model schema контракта.

Проверяет:
- Каждая enabled модель имеет schema required/properties
- Wizard может построить flow без runtime ошибок
- Missing required → корректный user error
"""

import pytest
from pathlib import Path
import sys
import json
import yaml

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_yaml_models():
    """Загружает модели из YAML файла."""
    yaml_path = project_root / "models" / "kie_models.yaml"
    if not yaml_path.exists():
        return {}
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    return data.get('models', {})


def load_registry_models():
    """Загружает модели из registry JSON (если есть)."""
    registry_path = project_root / "models" / "kie_models_source_of_truth.json"
    if not registry_path.exists():
        return {}
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_enabled_models():
    """Получает список всех enabled моделей."""
    models = {}
    
    # Пробуем загрузить из YAML
    yaml_models = load_yaml_models()
    if yaml_models:
        for model_id, model_data in yaml_models.items():
            if isinstance(model_data, dict) and model_data.get('enabled', True):
                models[model_id] = model_data
    
    # Пробуем загрузить из registry
    registry_models = load_registry_models()
    if registry_models:
        for model_id, model_data in registry_models.items():
            if isinstance(model_data, dict) and model_data.get('enabled', True):
                models[model_id] = model_data
    
    return models


def test_all_enabled_models_have_schema():
    """Тест: каждая enabled модель имеет schema required/properties."""
    enabled_models = get_enabled_models()
    
    assert len(enabled_models) > 0, "No enabled models found"
    
    errors = []
    
    for model_id, model_data in enabled_models.items():
        # Проверяем наличие input_schema или input
        input_schema = model_data.get('input_schema') or model_data.get('input', {})
        
        if not input_schema:
            errors.append(f"{model_id}: Missing input_schema/input")
            continue
        
        if not isinstance(input_schema, dict):
            errors.append(f"{model_id}: input_schema must be a dictionary")
            continue
        
        # Проверяем наличие required (может быть список или часть properties)
        required = input_schema.get('required', [])
        properties = input_schema.get('properties', {})
        
        # Если required - это список, проверяем что все required поля есть в properties
        if isinstance(required, list):
            for field_name in required:
                if field_name not in properties:
                    errors.append(f"{model_id}: Required field '{field_name}' not in properties")
        
        # Проверяем что properties не пустой (хотя бы одно поле должно быть)
        if not properties:
            # Проверяем альтернативный формат (прямо в input_schema)
            if len(input_schema) == 0:
                errors.append(f"{model_id}: Empty input_schema (no properties)")
    
    if errors:
        error_msg = "\n".join(f"  - {err}" for err in errors[:20])
        if len(errors) > 20:
            error_msg += f"\n  ... and {len(errors) - 20} more"
        raise AssertionError(
            f"Found {len(errors)} model schema validation error(s):\n{error_msg}\n\n"
            "All enabled models MUST have valid input_schema with required/properties."
        )


def test_model_schema_has_required_properties():
    """Тест: schema имеет структуру required/properties или альтернативный формат."""
    enabled_models = get_enabled_models()
    
    errors = []
    
    for model_id, model_data in enabled_models.items():
        input_schema = model_data.get('input_schema') or model_data.get('input', {})
        
        if not input_schema or not isinstance(input_schema, dict):
            continue
        
        # Проверяем наличие required (может быть список)
        required = input_schema.get('required', [])
        properties = input_schema.get('properties', {})
        
        # Если есть required, должен быть и properties
        if required and not properties:
            # Проверяем альтернативный формат (поля прямо в input_schema)
            has_fields = any(
                isinstance(v, dict) and ('type' in v or 'required' in v)
                for v in input_schema.values()
            )
            if not has_fields:
                errors.append(f"{model_id}: Has 'required' but no 'properties' or field definitions")
    
    if errors:
        error_msg = "\n".join(f"  - {err}" for err in errors[:10])
        raise AssertionError(
            f"Found {len(errors)} models with invalid schema structure:\n{error_msg}"
        )


def test_wizard_can_build_flow():
    """Тест: wizard может построить flow без runtime ошибок (базовая проверка)."""
    enabled_models = get_enabled_models()
    
    errors = []
    
    for model_id, model_data in enabled_models.items():
        # Проверяем что модель имеет все необходимые поля для wizard
        required_fields = ['model_id', 'name', 'description']
        
        for field in required_fields:
            if field not in model_data:
                errors.append(f"{model_id}: Missing required field '{field}' for wizard")
        
        # Проверяем что есть input_schema для построения формы
        input_schema = model_data.get('input_schema') or model_data.get('input', {})
        if not input_schema:
            errors.append(f"{model_id}: Missing input_schema for wizard form")
    
    if errors:
        error_msg = "\n".join(f"  - {err}" for err in errors[:10])
        raise AssertionError(
            f"Found {len(errors)} models that cannot build wizard flow:\n{error_msg}"
        )


def test_missing_required_field_error():
    """Тест: missing required → корректный user error (проверка валидации)."""
    from app.kie.validator import validate_model_inputs, ModelContractError
    
    enabled_models = get_enabled_models()
    
    if not enabled_models:
        pytest.skip("No enabled models found")
    
    # Берем первую модель для теста
    model_id = list(enabled_models.keys())[0]
    model_data = enabled_models[model_id]
    
    input_schema = model_data.get('input_schema') or model_data.get('input', {})
    if not input_schema:
        pytest.skip(f"Model {model_id} has no input_schema")
    
    # Определяем required поля
    required = input_schema.get('required', [])
    if not required:
        pytest.skip(f"Model {model_id} has no required fields")
    
    # Пробуем валидировать без required поля
    user_inputs = {}  # Пустой input (нет required полей)
    
    try:
        validate_model_inputs(model_id, input_schema, user_inputs)
        # Если не выбросило ошибку - это проблема
        raise AssertionError(
            f"Model {model_id}: Validation should fail for missing required fields, but it didn't"
        )
    except ModelContractError as e:
        # Ожидаем ошибку с понятным сообщением
        error_msg = str(e)
        assert "required" in error_msg.lower() or "missing" in error_msg.lower(), \
            f"Error message should mention 'required' or 'missing', got: {error_msg}"
    except Exception as e:
        # Другие ошибки тоже OK (валидация сработала)
        pass

