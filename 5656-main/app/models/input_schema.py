"""
Input Schema Parser - строгие контракты для всех моделей из SOURCE_OF_TRUTH

Этот модуль парсит SOURCE_OF_TRUTH.json и генерирует:
- required_inputs: обязательные поля (must-have)
- optional_inputs: опциональные поля (can-have)
- enum_inputs: поля с ограниченным набором значений (choice)

NO MAGIC DEFAULTS - пользователь выбирает все enum inputs через UI
"""
import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


PROJECT_ROOT = Path(__file__).parent.parent.parent
SOURCE_OF_TRUTH = PROJECT_ROOT / "models" / "KIE_SOURCE_OF_TRUTH.json"


class InputType(Enum):
    """Тип input поля"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    FILE = "file"  # base64, url
    OBJECT = "object"
    ARRAY = "array"


@dataclass
class InputField:
    """Описание одного input поля"""
    name: str
    type: InputType
    required: bool
    enum_values: Optional[List[Any]] = None
    default: Optional[Any] = None
    description: str = ""
    
    @property
    def is_enum(self) -> bool:
        """Является ли поле enum (ограниченный набор значений)"""
        return self.type == InputType.ENUM and self.enum_values is not None
    
    @property
    def is_file(self) -> bool:
        """Является ли поле файлом"""
        return self.type == InputType.FILE or self.name in ["image", "image_url", "video", "audio"]


@dataclass
class ModelInputSchema:
    """Полная схема inputs для модели"""
    model_id: str
    category: str
    required_fields: List[InputField] = field(default_factory=list)
    optional_fields: List[InputField] = field(default_factory=list)
    
    @property
    def all_fields(self) -> List[InputField]:
        """Все поля (required + optional)"""
        return self.required_fields + self.optional_fields
    
    @property
    def enum_fields(self) -> List[InputField]:
        """Поля с enum значениями"""
        return [f for f in self.all_fields if f.is_enum]
    
    @property
    def file_fields(self) -> List[InputField]:
        """Поля-файлы"""
        return [f for f in self.all_fields if f.is_file]
    
    def validate(self, inputs: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Валидация inputs против схемы
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # CRITICAL FIX: Для image-edit моделей prompt может быть пустой строкой, но должен присутствовать
        if 'image-edit' in self.model_id.lower() or 'image_edit' in self.model_id.lower():
            if 'prompt' not in inputs:
                # Для image-edit моделей добавляем пустой prompt если отсутствует
                inputs['prompt'] = ""
        
        # Проверка required полей
        for field in self.required_fields:
            if field.name not in inputs:
                errors.append(f"Missing required field: {field.name}")
            elif inputs[field.name] is None:
                errors.append(f"Required field cannot be None: {field.name}")
        
        # Проверка enum значений
        for field in self.enum_fields:
            value = inputs.get(field.name)
            
            # Skip validation for None/null/"none" on OPTIONAL fields
            if value is None or (isinstance(value, str) and value.lower() in ["none", "null"]):
                # Only skip if field is optional
                if field not in self.required_fields:
                    continue
            
            if value is not None and field.enum_values:
                # Allow "none" for optional enum fields as fallback
                if not field.required and isinstance(value, str) and value.lower() == "none":
                    continue
                
                # CRITICAL FIX: For text fields (prompt, text, input, message), enum values are suggestions/examples,
                # NOT strict constraints. Users should be able to enter arbitrary text.
                is_text_field = field.name in ['prompt', 'text', 'input', 'message', 'negative_prompt'] or field.type == InputType.STRING
                
                if not is_text_field and value not in field.enum_values:
                    # For non-text fields, enum is strict
                    errors.append(
                        f"Invalid value for {field.name}: {value}. "
                        f"Must be one of: {', '.join(map(str, field.enum_values))}"
                    )
                elif is_text_field and value not in field.enum_values:
                    # For text fields, enum is just a suggestion - allow arbitrary text
                    # Don't add error - allow arbitrary text
                    pass
        
        return len(errors) == 0, errors


class InputSchemaParser:
    """Парсер SOURCE_OF_TRUTH для извлечения input схем"""
    
    def __init__(self, source_file: Path = SOURCE_OF_TRUTH):
        self.source_file = source_file
        self._data: Optional[Dict] = None
        self._schemas: Dict[str, ModelInputSchema] = {}
        
        # Известные enum поля с их возможными значениями
        self.KNOWN_ENUMS = {
            "aspect_ratio": ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9", "9:21"],
            "image_size": ["square", "portrait", "landscape", "square_hd", "portrait_hd", "landscape_hd", "1024x1024", "512x512"],
            "style": ["realistic", "anime", "cartoon", "3d", "oil_painting", "watercolor"],
            "quality": ["standard", "hd", "ultra"],
            "output_format": ["png", "jpg", "jpeg", "webp"],
            "resolution": ["1080p", "720p", "480p", "4k"],
            "duration": ["5", "10", "15", "30"],
            "acceleration": ["standard", "fast", "ultra_fast"],
        }
    
    def load(self) -> None:
        """Загрузить SOURCE_OF_TRUTH"""
        with open(self.source_file) as f:
            self._data = json.load(f)
    
    def _infer_type(self, value: Any, field_name: str) -> InputType:
        """Определить тип поля по значению"""
        # Файловые поля (но НЕ prompt!)
        if field_name in ["image", "image_url", "image_urls", "video", "video_url", "audio"]:
            return InputType.FILE
        
        # Enum поля
        if field_name in self.KNOWN_ENUMS:
            return InputType.ENUM
        
        # По типу значения
        if isinstance(value, bool):
            return InputType.BOOLEAN
        elif isinstance(value, (int, float)):
            return InputType.NUMBER
        elif isinstance(value, str):
            # Prompt всегда string, даже если длинный
            if field_name in ["prompt", "negative_prompt", "text"]:
                return InputType.STRING
            # Проверка на base64 (длинная строка без http)
            if len(value) > 100 and not value.startswith("http"):
                return InputType.FILE
            return InputType.STRING
        elif isinstance(value, list):
            return InputType.ARRAY
        elif isinstance(value, dict):
            return InputType.OBJECT
        
        return InputType.STRING
    
    def _parse_examples(self, examples: List[Any]) -> Dict[str, InputField]:
        """Парсинг примеров для извлечения полей"""
        if not examples or not isinstance(examples, list):
            return {}
        
        # Анализируем все примеры
        field_info: Dict[str, Dict] = {}
        
        for example in examples:
            if not isinstance(example, dict):
                continue
            
            for key, value in example.items():
                if key not in field_info:
                    field_info[key] = {
                        "occurrences": 0,
                        "values": set(),
                        "types": set(),
                        "sample_value": value,
                    }
                
                field_info[key]["occurrences"] += 1
                field_info[key]["types"].add(type(value).__name__)
                
                # Собираем уникальные значения для enum detection
                if isinstance(value, (str, int, float, bool)) and len(str(value)) < 50:
                    field_info[key]["values"].add(value)
        
        # Создаём InputField для каждого поля
        fields = {}
        total_examples = len(examples)
        
        for name, info in field_info.items():
            # Поле required если присутствует во всех примерах
            required = info["occurrences"] == total_examples
            
            # Определяем тип
            sample = info["sample_value"]
            input_type = self._infer_type(sample, name)
            
            # Enum detection
            enum_values = None
            if name in self.KNOWN_ENUMS:
                # For known enums, UNION of predefined + actual values from examples
                enum_values = list(set(self.KNOWN_ENUMS[name]) | info["values"])
                input_type = InputType.ENUM
            elif len(info["values"]) <= 10 and len(info["values"]) > 1:
                # Если уникальных значений мало - вероятно enum
                enum_values = sorted(list(info["values"]))
                input_type = InputType.ENUM
            
            fields[name] = InputField(
                name=name,
                type=input_type,
                required=required,
                enum_values=enum_values,
                default=sample if not required else None,
            )
        
        return fields
    
    def parse_model(self, model_id: str) -> Optional[ModelInputSchema]:
        """Парсинг схемы для одной модели"""
        if not self._data:
            self.load()
        
        models = self._data.get("models", {})
        model_data = models.get(model_id)
        
        if not model_data:
            return None
        
        # Извлекаем примеры из input_schema
        input_schema = model_data.get("input_schema", {}).get("input", {})
        examples = input_schema.get("examples", [])
        
        # Парсим поля
        fields = self._parse_examples(examples)
        
        # Разделяем на required и optional
        required_fields = [f for f in fields.values() if f.required]
        optional_fields = [f for f in fields.values() if not f.required]
        
        schema = ModelInputSchema(
            model_id=model_id,
            category=model_data.get("category", "unknown"),
            required_fields=required_fields,
            optional_fields=optional_fields,
        )
        
        return schema
    
    def parse_all(self) -> Dict[str, ModelInputSchema]:
        """Парсинг схем для всех моделей"""
        if not self._data:
            self.load()
        
        models = self._data.get("models", {})
        
        for model_id in models.keys():
            schema = self.parse_model(model_id)
            if schema:
                self._schemas[model_id] = schema
        
        return self._schemas
    
    def get_schema(self, model_id: str) -> Optional[ModelInputSchema]:
        """Получить схему для модели"""
        if model_id not in self._schemas:
            schema = self.parse_model(model_id)
            if schema:
                self._schemas[model_id] = schema
        
        return self._schemas.get(model_id)


# Singleton instance
_parser: Optional[InputSchemaParser] = None


def get_input_schema_parser() -> InputSchemaParser:
    """Получить singleton парсера"""
    global _parser
    if _parser is None:
        _parser = InputSchemaParser()
        _parser.load()
    return _parser


def get_model_schema(model_id: str) -> Optional[ModelInputSchema]:
    """Быстрый доступ к схеме модели"""
    parser = get_input_schema_parser()
    return parser.get_schema(model_id)


def validate_inputs(model_id: str, inputs: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Валидация inputs для модели
    
    Returns:
        (is_valid, errors)
    """
    # CRITICAL FIX: Для image-edit моделей prompt может быть пустой строкой, но должен присутствовать
    if ('image-edit' in model_id.lower() or 'image_edit' in model_id.lower()) and 'prompt' not in inputs:
        inputs['prompt'] = ""
    
    schema = get_model_schema(model_id)
    if not schema:
        return False, [f"Unknown model: {model_id}"]
    
    return schema.validate(inputs)
