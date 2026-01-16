"""
Строгий валидатор input-полей на основе SOURCE_OF_TRUTH.json

Основано на паттерне aiogram CallbackDataFilter для type-safe валидации.
Гарантирует, что все обязательные поля присутствуют и имеют правильный тип
ПЕРЕД отправкой в KIE AI API.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class ValidationError:
    """Описание ошибки валидации"""
    
    def __init__(self, field_path: str, message: str, expected: Optional[Any] = None):
        self.field_path = field_path
        self.message = message
        self.expected = expected
    
    def __repr__(self):
        if self.expected:
            return f"{self.field_path}: {self.message} (expected: {self.expected})"
        return f"{self.field_path}: {self.message}"
    
    def to_dict(self):
        return {
            "field": self.field_path,
            "error": self.message,
            "expected": self.expected
        }


class ValidationResult:
    """Результат валидации"""
    
    def __init__(self, is_valid: bool, errors: List[ValidationError]):
        self.is_valid = is_valid
        self.errors = errors
    
    @property
    def error_messages(self) -> List[str]:
        """Простые текстовые сообщения для пользователя"""
        return [str(e) for e in self.errors]
    
    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors]
        }


class InputSchemaValidator:
    """
    Валидатор input-полей на основе SOURCE_OF_TRUTH.json
    
    Usage:
        validator = InputSchemaValidator()
        result = validator.validate("bytedance/seedream", {
            "model": "bytedance/seedream",
            "callBackUrl": "https://example.com/callback",
            "input": {"prompt": "test"}
        })
        
        if not result.is_valid:
            for error in result.error_messages:
                print(error)
    """
    
    def __init__(self, source_of_truth_path: Optional[str] = None):
        """
        Args:
            source_of_truth_path: Путь к KIE_SOURCE_OF_TRUTH.json
                                  Если None, используется default путь
        """
        if source_of_truth_path is None:
            # Default: models/KIE_SOURCE_OF_TRUTH.json
            base_dir = Path(__file__).parent.parent.parent
            source_of_truth_path = base_dir / "models" / "KIE_SOURCE_OF_TRUTH.json"
        
        self.schemas = self._load_schemas(source_of_truth_path)
        logger.info(f"[INPUT_VALIDATOR] Loaded {len(self.schemas)} model schemas from {source_of_truth_path}")
    
    def _load_schemas(self, path: Path) -> Dict[str, Dict]:
        """Загрузить схемы из SOURCE_OF_TRUTH.json"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Вернуть только модели с input_schema
            schemas = {}
            for model_id, model_data in data.get("models", {}).items():
                if "input_schema" in model_data:
                    schemas[model_id] = model_data
            
            return schemas
        except Exception as e:
            logger.error(f"[INPUT_VALIDATOR] Failed to load schemas: {e}")
            return {}
    
    def validate(self, model_id: str, input_data: Dict[str, Any]) -> ValidationResult:
        """
        Валидировать input_data против схемы модели
        
        Args:
            model_id: ID модели (напр. "bytedance/seedream")
            input_data: Данные для валидации (напр. {"model": "...", "callBackUrl": "...", "input": {...}})
        
        Returns:
            ValidationResult с is_valid и списком ошибок
        """
        errors = []
        
        # 1. Проверить, что модель существует
        schema_data = self.schemas.get(model_id)
        if not schema_data:
            errors.append(ValidationError(
                "model",
                f"Unknown model: {model_id}",
                expected="Valid model ID from SOURCE_OF_TRUTH"
            ))
            return ValidationResult(False, errors)
        
        input_schema = schema_data.get("input_schema", {})
        
        # 2. Проверить обязательные поля
        for field_name, field_spec in input_schema.items():
            is_required = field_spec.get("required", False)
            
            if is_required and field_name not in input_data:
                errors.append(ValidationError(
                    field_name,
                    f"Missing required field",
                    expected=field_spec.get("type", "any")
                ))
                continue
            
            # Если поле не обязательное и его нет - OK
            if field_name not in input_data:
                continue
            
            # 3. Проверить тип поля
            actual_value = input_data[field_name]
            expected_type = field_spec.get("type", "any")
            
            type_error = self._validate_type(field_name, actual_value, expected_type)
            if type_error:
                errors.append(type_error)
        
        # 4. Валидировать вложенные поля в "input" (если это dict)
        if "input" in input_data and isinstance(input_data["input"], dict):
            # Получить примеры из схемы для проверки enum values
            examples = input_schema.get("input", {}).get("examples", [])
            if examples:
                # Извлечь возможные значения для enum полей из примеров
                input_errors = self._validate_input_dict(
                    input_data["input"],
                    examples,
                    model_id
                )
                errors.extend(input_errors)
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors)
    
    def _validate_type(self, field_name: str, value: Any, expected_type: str) -> Optional[ValidationError]:
        """
        Проверить, соответствует ли значение ожидаемому типу
        
        Args:
            field_name: Имя поля
            value: Значение для проверки
            expected_type: Ожидаемый тип ("str", "int", "dict", "list", "bool", "float")
        
        Returns:
            ValidationError если тип не совпадает, иначе None
        """
        type_mapping = {
            "str": str,
            "int": int,
            "dict": dict,
            "list": list,
            "bool": bool,
            "float": (float, int),  # int допустим для float
            "any": object
        }
        
        expected_py_type = type_mapping.get(expected_type, object)
        
        if not isinstance(value, expected_py_type):
            actual_type = type(value).__name__
            return ValidationError(
                field_name,
                f"Invalid type: got {actual_type}",
                expected=expected_type
            )
        
        return None
    
    def _validate_input_dict(
        self,
        input_dict: Dict[str, Any],
        examples: List[Dict],
        model_id: str
    ) -> List[ValidationError]:
        """
        Валидировать поля внутри input dict
        
        Проверяет:
        - Обязательные поля (только prompt для большинства моделей)
        - Enum значения (например, image_size должен быть из списка)
        
        Args:
            input_dict: Словарь input параметров
            examples: Примеры из схемы
            model_id: ID модели (для логирования)
        
        Returns:
            Список ValidationError
        """
        errors = []
        
        if not examples:
            # Нет примеров - не можем валидировать enum
            return errors
        
        # Только prompt считаем обязательным (есть в большинстве моделей)
        # Остальные поля - optional
        if "prompt" not in input_dict:
            # Проверяем, есть ли prompt в примерах
            has_prompt_in_examples = any("prompt" in ex for ex in examples)
            if has_prompt_in_examples:
                errors.append(ValidationError(
                    "input.prompt",
                    "Missing required field",
                    expected="Text prompt for generation"
                ))
        
        # Проверить enum значения (image_size, image_resolution, etc.)
        # Но ТОЛЬКО для полей которые пользователь передал
        enum_fields = self._extract_enum_fields(examples)
        
        for field_name, allowed_values in enum_fields.items():
            if field_name in input_dict:
                actual_value = input_dict[field_name]
                # Проверяем только строковые enum values
                if isinstance(actual_value, str) and actual_value not in allowed_values:
                    errors.append(ValidationError(
                        f"input.{field_name}",
                        f"Invalid value: {actual_value}",
                        expected=f"One of {sorted(allowed_values)}"
                    ))
        
        return errors
    
    def _extract_enum_fields(self, examples: List[Dict]) -> Dict[str, set]:
        """
        Извлечь поля с enum значениями из примеров
        
        Если поле имеет ограниченный набор значений (2-10 уникальных),
        считаем его enum.
        
        Args:
            examples: Список примеров
        
        Returns:
            Dict[field_name, set_of_allowed_values]
        """
        field_values = {}
        
        for example in examples:
            for key, value in example.items():
                # Собираем только строковые значения для enum
                if isinstance(value, str):
                    if key not in field_values:
                        field_values[key] = set()
                    field_values[key].add(value)
        
        # Фильтруем: только поля с 2-10 уникальными значениями = enum
        enum_fields = {}
        for key, values in field_values.items():
            if 2 <= len(values) <= 10:
                enum_fields[key] = values
        
        return enum_fields
    
    def get_model_schema(self, model_id: str) -> Optional[Dict]:
        """Получить полную схему модели"""
        return self.schemas.get(model_id)
    
    def get_available_models(self) -> List[str]:
        """Получить список всех доступных model_id"""
        return list(self.schemas.keys())
    
    def is_model_available(self, model_id: str) -> bool:
        """Проверить, доступна ли модель"""
        return model_id in self.schemas


# Global singleton instance
_validator_instance = None


def get_validator() -> InputSchemaValidator:
    """
    Получить singleton instance валидатора
    
    Использовать это вместо создания новых экземпляров для экономии памяти.
    """
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = InputSchemaValidator()
    return _validator_instance
