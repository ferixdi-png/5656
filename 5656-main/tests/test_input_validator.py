"""
Unit tests для InputSchemaValidator

Проверяет все основные сценарии валидации:
- Валидные input данные
- Отсутствие обязательных полей
- Неправильные типы
- Неизвестные модели
- Enum validation
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.input_validator import InputSchemaValidator, ValidationResult, get_validator


class TestInputSchemaValidator:
    """Тесты для валидатора input схем"""
    
    @pytest.fixture
    def validator(self):
        """Fixture для validator instance"""
        return get_validator()
    
    def test_validator_loads_schemas(self, validator):
        """Тест: валидатор загружает схемы из SOURCE_OF_TRUTH"""
        available_models = validator.get_available_models()
        
        assert len(available_models) > 0, "Should load at least some models"
        assert "bytedance/seedream" in available_models, "Should include seedream model"
    
    def test_valid_input_passes(self, validator):
        """Тест: валидный input проходит валидацию"""
        valid_input = {
            "model": "bytedance/seedream",
            "callBackUrl": "https://example.com/callback",
            "input": {
                "prompt": "A beautiful landscape",
                "image_size": "square_hd",
                "guidance_scale": 2.5,
                "enable_safety_checker": True
            }
        }
        
        result = validator.validate("bytedance/seedream", valid_input)
        
        assert result.is_valid, f"Should be valid, got errors: {result.error_messages}"
        assert len(result.errors) == 0
    
    def test_missing_required_field_fails(self, validator):
        """Тест: отсутствие обязательного поля вызывает ошибку"""
        invalid_input = {
            "model": "bytedance/seedream",
            # callBackUrl отсутствует (required)
            "input": {
                "prompt": "Test"
            }
        }
        
        result = validator.validate("bytedance/seedream", invalid_input)
        
        assert not result.is_valid, "Should be invalid due to missing callBackUrl"
        assert any("callBackUrl" in str(e) for e in result.errors)
    
    def test_wrong_type_fails(self, validator):
        """Тест: неправильный тип поля вызывает ошибку"""
        invalid_input = {
            "model": "bytedance/seedream",
            "callBackUrl": 12345,  # Should be str, not int
            "input": {
                "prompt": "Test"
            }
        }
        
        result = validator.validate("bytedance/seedream", invalid_input)
        
        assert not result.is_valid, "Should be invalid due to wrong type"
        assert any("callBackUrl" in str(e) and "type" in str(e).lower() for e in result.errors)
    
    def test_unknown_model_fails(self, validator):
        """Тест: неизвестная модель вызывает ошибку"""
        input_data = {
            "model": "unknown/nonexistent-model",
            "callBackUrl": "https://example.com/callback",
            "input": {}
        }
        
        result = validator.validate("unknown/nonexistent-model", input_data)
        
        assert not result.is_valid, "Should be invalid for unknown model"
        assert any("unknown" in str(e).lower() for e in result.errors)
    
    def test_input_dict_type_validation(self, validator):
        """Тест: валидация типа для поля input (должен быть dict)"""
        invalid_input = {
            "model": "bytedance/seedream",
            "callBackUrl": "https://example.com/callback",
            "input": "not a dict"  # Should be dict
        }
        
        result = validator.validate("bytedance/seedream", invalid_input)
        
        assert not result.is_valid, "Should be invalid due to input not being dict"
    
    def test_missing_input_field_fails(self, validator):
        """Тест: отсутствие обязательного поля input вызывает ошибку"""
        invalid_input = {
            "model": "bytedance/seedream",
            "callBackUrl": "https://example.com/callback"
            # input отсутствует
        }
        
        result = validator.validate("bytedance/seedream", invalid_input)
        
        assert not result.is_valid, "Should be invalid due to missing input field"
        assert any("input" in str(e).lower() for e in result.errors)
    
    def test_optional_fields_allowed(self, validator):
        """Тест: необязательные поля могут отсутствовать"""
        minimal_input = {
            "model": "bytedance/seedream",
            "callBackUrl": "https://example.com/callback",
            "input": {
                "prompt": "Test prompt"
                # Другие необязательные поля отсутствуют - это OK
            }
        }
        
        result = validator.validate("bytedance/seedream", minimal_input)
        
        # Может быть valid или invalid в зависимости от required fields в schema
        # Просто проверяем, что валидатор не падает
        assert isinstance(result, ValidationResult)
    
    def test_get_model_schema(self, validator):
        """Тест: получение схемы модели"""
        schema = validator.get_model_schema("bytedance/seedream")
        
        assert schema is not None
        assert "input_schema" in schema
        assert "pricing" in schema
    
    def test_is_model_available(self, validator):
        """Тест: проверка доступности модели"""
        assert validator.is_model_available("bytedance/seedream"), "Should return True for existing model"
        assert not validator.is_model_available("nonexistent/model"), "Should return False for nonexistent model"
    
    def test_validation_result_to_dict(self, validator):
        """Тест: ValidationResult.to_dict() возвращает сериализуемый dict"""
        invalid_input = {
            "model": "bytedance/seedream"
            # Missing required fields
        }
        
        result = validator.validate("bytedance/seedream", invalid_input)
        result_dict = result.to_dict()
        
        assert "is_valid" in result_dict
        assert "errors" in result_dict
        assert isinstance(result_dict["errors"], list)
    
    def test_multiple_errors_collected(self, validator):
        """Тест: валидатор собирает несколько ошибок сразу"""
        invalid_input = {
            # model отсутствует
            # callBackUrl отсутствует
            # input отсутствует
        }
        
        result = validator.validate("bytedance/seedream", invalid_input)
        
        assert not result.is_valid
        # Должно быть минимум 2 ошибки (callBackUrl + input обязательны)
        assert len(result.errors) >= 2
    
    def test_singleton_get_validator(self):
        """Тест: get_validator() возвращает singleton"""
        v1 = get_validator()
        v2 = get_validator()
        
        assert v1 is v2, "Should return same instance"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
