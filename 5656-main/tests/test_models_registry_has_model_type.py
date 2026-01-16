#!/usr/bin/env python3
"""
Тест для проверки что все модели имеют model_type и input_params.
Проверяет что count == 72 (или актуальный из YAML).
"""

import sys
import pytest
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def test_all_models_have_model_type():
    """Проверяет что у каждой модели есть model_type."""
    from app.models.registry import get_models_sync
    
    models = get_models_sync()
    
    assert len(models) > 0, "No models loaded"
    
    missing_model_type = []
    for model in models:
        model_id = model.get('id')
        if not model_id:
            missing_model_type.append(f"Model without id: {model}")
            continue
        
        if 'model_type' not in model or not model['model_type']:
            missing_model_type.append(f"Model {model_id} missing model_type")
    
    assert not missing_model_type, f"Models missing model_type: {missing_model_type}"


def test_all_models_have_input_params():
    """Проверяет что у каждой модели есть input_params и он не пустой."""
    from app.models.registry import get_models_sync
    
    models = get_models_sync()
    
    assert len(models) > 0, "No models loaded"
    
    missing_input_params = []
    for model in models:
        model_id = model.get('id')
        if not model_id:
            missing_input_params.append(f"Model without id: {model}")
            continue
        
        input_params = model.get('input_params')
        if not input_params:
            missing_input_params.append(f"Model {model_id} missing input_params")
        elif not isinstance(input_params, dict):
            missing_input_params.append(f"Model {model_id} input_params is not a dict: {type(input_params)}")
        elif len(input_params) == 0:
            missing_input_params.append(f"Model {model_id} has empty input_params")
    
    assert not missing_input_params, f"Models with input_params issues: {missing_input_params}"


def test_all_models_have_id():
    """Проверяет что у каждой модели есть id."""
    from app.models.registry import get_models_sync
    
    models = get_models_sync()
    
    assert len(models) > 0, "No models loaded"
    
    missing_id = []
    for model in models:
        if 'id' not in model or not model['id']:
            missing_id.append(f"Model missing id: {model}")
    
    assert not missing_id, f"Models missing id: {missing_id}"


def test_model_count_matches_yaml():
    """Проверяет что количество моделей соответствует YAML."""
    from app.models.registry import get_models_sync, get_model_registry
    from app.models.yaml_registry import get_yaml_meta
    
    models = get_models_sync()
    registry = get_model_registry()
    yaml_meta = get_yaml_meta()
    
    yaml_total = yaml_meta.get('total_models')
    
    if yaml_total:
        assert len(models) == yaml_total, (
            f"Model count mismatch: registry has {len(models)}, YAML says {yaml_total}"
        )
    else:
        # Если нет YAML метаданных, просто проверяем что есть модели
        assert len(models) > 0, "No models loaded"
    
    # Проверяем что registry знает о count
    assert registry['count'] == len(models), (
        f"Registry count mismatch: registry says {registry['count']}, actual is {len(models)}"
    )


def test_no_duplicate_model_ids():
    """Проверяет что нет дубликатов model_id."""
    from app.models.registry import get_models_sync
    
    models = get_models_sync()
    
    seen_ids = set()
    duplicates = []
    
    for model in models:
        model_id = model.get('id')
        if not model_id:
            continue
        
        if model_id in seen_ids:
            duplicates.append(model_id)
        else:
            seen_ids.add(model_id)
    
    assert not duplicates, f"Duplicate model IDs found: {duplicates}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

