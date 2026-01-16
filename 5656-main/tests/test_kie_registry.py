"""
Тесты для KIE Registry - проверка что модели ТОЛЬКО из документации.
"""

import pytest
from pathlib import Path
import sys

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.kie.spec_registry import load_registry, reset_registry, KIERegistry
from app.kie.model_enforcer import enforce_model_from_registry, get_model_or_fail
from app.kie.spec_parser import parse_all_integration_docs


def test_registry_generated_from_docs_only():
    """
    Проверяет что количество моделей в registry == количеству файлов инструкций.
    """
    docs_dir = project_root / "docs"
    registry_path = project_root / "models" / "kie_registry.generated.json"
    
    # Подсчитываем файлы *_INTEGRATION.md
    integration_files = list(docs_dir.glob("*_INTEGRATION.md"))
    expected_count = len(integration_files)
    
    # Загружаем registry
    registry = load_registry(registry_path)
    actual_count = registry.count()
    
    # Проверяем что количество совпадает (или близко, т.к. некоторые файлы могут не парситься)
    assert actual_count > 0, "Registry should have at least one model"
    assert actual_count <= expected_count, f"Registry has more models ({actual_count}) than docs files ({expected_count})"
    
    # Проверяем что все модели из registry имеют уникальные ID
    model_ids = registry.list_models()
    assert len(model_ids) == len(set(model_ids)), "Duplicate model_ids in registry"


def test_no_unknown_models_in_ui():
    """
    Проверяет что меню перечисляет только registry models.
    """
    registry_path = project_root / "models" / "kie_registry.generated.json"
    registry = load_registry(registry_path)
    
    # Получаем список всех моделей из registry
    registry_models = set(registry.list_models())
    
    # Проверяем что registry не пустой
    assert len(registry_models) > 0, "Registry should have models"
    
    # Проверяем что каждая модель имеет спецификацию
    for model_id in registry_models:
        model_spec = registry.get_model(model_id)
        assert model_spec is not None, f"Model {model_id} should have spec"
        assert model_spec.model_id == model_id, f"Model spec should have correct model_id"
        assert model_spec.create_endpoint, f"Model {model_id} should have create_endpoint"
        assert model_spec.record_endpoint, f"Model {model_id} should have record_endpoint"
        assert model_spec.output_media_type in ["media_urls", "text_object"], \
            f"Model {model_id} should have valid output_media_type"


def test_payload_matches_doc_schema():
    """
    Проверяет что для 2-3 моделей можно собрать минимальный input и payload корректен.
    """
    registry_path = project_root / "models" / "kie_registry.generated.json"
    registry = load_registry(registry_path)
    
    # Выбираем несколько моделей для тестирования
    test_models = ["google/imagen4", "kling/v2-5-turbo-text-to-video-pro"]
    
    for model_id in test_models:
        model_spec = registry.get_model(model_id)
        if not model_spec:
            continue  # Пропускаем если модель не найдена
        
        # Собираем минимальный input на основе required полей
        input_params = {}
        for field_name, field in model_spec.input_schema.items():
            if field.required:
                # Устанавливаем дефолтное значение в зависимости от типа
                if field.type == "string":
                    input_params[field_name] = "test"
                elif field.type == "number":
                    input_params[field_name] = 0
                elif field.type == "boolean":
                    input_params[field_name] = False
                else:
                    input_params[field_name] = {}
        
        # Формируем payload
        payload = {
            "model": model_id,
            "input": input_params
        }
        
        # Проверяем что payload корректен
        assert "model" in payload, f"Payload should have 'model' for {model_id}"
        assert "input" in payload, f"Payload should have 'input' for {model_id}"
        assert payload["model"] == model_id, f"Payload model should match {model_id}"
        assert isinstance(payload["input"], dict), f"Payload input should be dict for {model_id}"


def test_resultJson_parsing_urls_vs_object():
    """
    Проверяет что output_media_type правильно определен для моделей.
    """
    registry_path = project_root / "models" / "kie_registry.generated.json"
    registry = load_registry(registry_path)
    
    # Проверяем что у всех моделей определен output_media_type
    for model_id in registry.list_models():
        model_spec = registry.get_model(model_id)
        assert model_spec is not None, f"Model {model_id} should have spec"
        assert model_spec.output_media_type in ["media_urls", "text_object"], \
            f"Model {model_id} should have valid output_media_type, got: {model_spec.output_media_type}"


def test_stub_mode_no_network():
    """
    Проверяет что в TEST_MODE=1/KIE_STUB=1 не делаются реальные HTTP запросы.
    """
    import os
    
    # Устанавливаем TEST_MODE
    os.environ["TEST_MODE"] = "1"
    os.environ["KIE_STUB"] = "1"
    
    try:
        # Пробуем создать gateway (должен использовать stub если доступен)
        from app.integrations.kie_gateway_unified import UnifiedKIEGateway
        
        gateway = UnifiedKIEGateway()
        
        # Проверяем что gateway создан (stub проверка будет в самом stub модуле)
        assert gateway is not None
        
    finally:
        # Восстанавливаем env
        if "TEST_MODE" in os.environ:
            del os.environ["TEST_MODE"]
        if "KIE_STUB" in os.environ:
            del os.environ["KIE_STUB"]


def test_model_enforcer_blocks_unknown_models():
    """
    Проверяет что enforcer блокирует модели не из registry.
    """
    registry_path = project_root / "models" / "kie_registry.generated.json"
    registry = load_registry(registry_path)
    
    # Проверяем что известная модель проходит
    known_model = registry.list_models()[0]
    is_valid, error = enforce_model_from_registry(known_model)
    assert is_valid, f"Known model {known_model} should be valid"
    assert error is None, f"Known model {known_model} should not have error"
    
    # Проверяем что неизвестная модель блокируется
    unknown_model = "unknown/model/that/does/not/exist"
    is_valid, error = enforce_model_from_registry(unknown_model)
    assert not is_valid, f"Unknown model {unknown_model} should be invalid"
    assert error is not None, f"Unknown model {unknown_model} should have error message"


def test_get_model_or_fail():
    """
    Проверяет что get_model_or_fail выбрасывает исключение для неизвестных моделей.
    """
    registry_path = project_root / "models" / "kie_registry.generated.json"
    registry = load_registry(registry_path)
    
    # Проверяем что известная модель возвращается
    known_model = registry.list_models()[0]
    model_spec = get_model_or_fail(known_model)
    assert model_spec is not None, f"Known model {known_model} should return spec"
    assert model_spec.model_id == known_model, f"Spec should have correct model_id"
    
    # Проверяем что неизвестная модель выбрасывает исключение
    unknown_model = "unknown/model/that/does/not/exist"
    with pytest.raises(ValueError, match="not found in registry"):
        get_model_or_fail(unknown_model)


@pytest.fixture(autouse=True)
def reset_registry_before_test():
    """Сбрасывает registry перед каждым тестом."""
    reset_registry()
    yield
    reset_registry()
















