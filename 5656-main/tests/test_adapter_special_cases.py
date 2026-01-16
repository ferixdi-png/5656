#!/usr/bin/env python3
"""
Тест для проверки специальных случаев маппинга параметров через адаптер.
Проверяет 4 кейса:
- recraft/remove-background: image_input[0] -> image
- recraft/crisp-upscale: image_input[0] -> image
- ideogram/v3-reframe: image_input[0] -> image_url
- topaz/image-upscale: image_input[0] -> image_url
"""

import sys
import pytest
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def test_recraft_remove_background_mapping():
    """Проверяет маппинг для recraft/remove-background: image_input[0] -> image"""
    from kie_input_adapter import adapt_to_api, get_schema, apply_defaults, validate_params
    
    model_id = "recraft/remove-background"
    
    # Внутренние параметры (как в YAML)
    internal_params = {
        "image_input": ["https://example.com/image.jpg"]
    }
    
    # Получаем схему
    schema = get_schema(model_id)
    assert schema is not None, f"Schema not found for {model_id}"
    
    # Применяем дефолты
    params_with_defaults = apply_defaults(schema, internal_params)
    
    # Валидируем
    is_valid, errors = validate_params(schema, params_with_defaults)
    assert is_valid, f"Validation failed: {errors}"
    
    # Адаптируем к API
    api_params = adapt_to_api(model_id, params_with_defaults)
    
    # Проверяем результат
    assert "image_input" not in api_params, "image_input should be removed"
    assert "image" in api_params, "image should be present"
    assert api_params["image"] == "https://example.com/image.jpg", "image should be first element of image_input"
    assert isinstance(api_params["image"], str), "image should be a string, not array"


def test_recraft_crisp_upscale_mapping():
    """Проверяет маппинг для recraft/crisp-upscale: image_input[0] -> image"""
    from kie_input_adapter import adapt_to_api, get_schema, apply_defaults, validate_params
    
    model_id = "recraft/crisp-upscale"
    
    # Внутренние параметры (как в YAML)
    internal_params = {
        "image_input": ["https://example.com/image.jpg"]
    }
    
    # Получаем схему
    schema = get_schema(model_id)
    assert schema is not None, f"Schema not found for {model_id}"
    
    # Применяем дефолты
    params_with_defaults = apply_defaults(schema, internal_params)
    
    # Валидируем
    is_valid, errors = validate_params(schema, params_with_defaults)
    assert is_valid, f"Validation failed: {errors}"
    
    # Адаптируем к API
    api_params = adapt_to_api(model_id, params_with_defaults)
    
    # Проверяем результат
    assert "image_input" not in api_params, "image_input should be removed"
    assert "image" in api_params, "image should be present"
    assert api_params["image"] == "https://example.com/image.jpg", "image should be first element of image_input"
    assert isinstance(api_params["image"], str), "image should be a string, not array"


def test_ideogram_v3_reframe_mapping():
    """Проверяет маппинг для ideogram/v3-reframe: image_input[0] -> image_url"""
    from kie_input_adapter import adapt_to_api, get_schema, apply_defaults, validate_params
    
    model_id = "ideogram/v3-reframe"
    
    # Внутренние параметры (как в YAML)
    internal_params = {
        "image_input": ["https://example.com/image.jpg"],
        "image_size": "square"  # Обязательный параметр, одно из: square, square_hd, portrait_4_3, portrait_16_9, landscape_4_3, landscape_16_9
    }
    
    # Получаем схему
    schema = get_schema(model_id)
    assert schema is not None, f"Schema not found for {model_id}"
    
    # Применяем дефолты
    params_with_defaults = apply_defaults(schema, internal_params)
    
    # Валидируем
    is_valid, errors = validate_params(schema, params_with_defaults)
    assert is_valid, f"Validation failed: {errors}"
    
    # Адаптируем к API
    api_params = adapt_to_api(model_id, params_with_defaults)
    
    # Проверяем результат
    assert "image_input" not in api_params, "image_input should be removed"
    assert "image_url" in api_params, "image_url should be present"
    assert api_params["image_url"] == "https://example.com/image.jpg", "image_url should be first element of image_input"
    assert isinstance(api_params["image_url"], str), "image_url should be a string, not array"
    # Проверяем, что другие параметры сохранились
    assert api_params.get("image_size") == "square"


def test_topaz_image_upscale_mapping():
    """Проверяет маппинг для topaz/image-upscale: image_input[0] -> image_url"""
    from kie_input_adapter import adapt_to_api, get_schema, apply_defaults, validate_params
    
    model_id = "topaz/image-upscale"
    
    # Внутренние параметры (как в YAML)
    internal_params = {
        "image_input": ["https://example.com/image.jpg"],
        "upscale_factor": "2"
    }
    
    # Получаем схему
    schema = get_schema(model_id)
    assert schema is not None, f"Schema not found for {model_id}"
    
    # Применяем дефолты
    params_with_defaults = apply_defaults(schema, internal_params)
    
    # Валидируем
    is_valid, errors = validate_params(schema, params_with_defaults)
    assert is_valid, f"Validation failed: {errors}"
    
    # Адаптируем к API
    api_params = adapt_to_api(model_id, params_with_defaults)
    
    # Проверяем результат
    assert "image_input" not in api_params, "image_input should be removed"
    assert "image_url" in api_params, "image_url should be present"
    assert api_params["image_url"] == "https://example.com/image.jpg", "image_url should be first element of image_input"
    assert isinstance(api_params["image_url"], str), "image_url should be a string, not array"
    # Проверяем, что другие параметры сохранились
    assert api_params.get("upscale_factor") == "2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

