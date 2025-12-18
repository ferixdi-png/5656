"""
Строгая валидация параметров через контракт API.
Валидация типов, нормирование значений, подсказки пользователю.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


def validate_parameter_strict(
    param_name: str,
    param_value: Any,
    param_schema: Dict[str, Any]
) -> Tuple[bool, Optional[str], Any]:
    """
    Строгая валидация параметра согласно схеме.
    
    Args:
        param_name: Название параметра
        param_value: Значение для проверки
        param_schema: Схема параметра
    
    Returns:
        (валидно, сообщение_об_ошибке, нормализованное_значение)
    """
    param_type = param_schema.get("type", "string")
    
    # Валидация типа
    if param_type == "string":
        if not isinstance(param_value, str):
            return False, f"Параметр {param_name} должен быть строкой", None
        
        # Проверка maxLength
        max_length = param_schema.get("maxLength")
        if max_length and len(param_value) > max_length:
            return False, f"Параметр {param_name} слишком длинный (максимум {max_length} символов)", None
        
        # Нормализация: обрезка пробелов
        normalized = param_value.strip()
        
    elif param_type == "integer" or param_type == "number":
        try:
            normalized = int(param_value) if param_type == "integer" else float(param_value)
        except (ValueError, TypeError):
            return False, f"Параметр {param_name} должен быть числом", None
        
        # Проверка minimum/maximum
        minimum = param_schema.get("minimum")
        maximum = param_schema.get("maximum")
        
        if minimum is not None and normalized < minimum:
            return False, f"Параметр {param_name} должен быть не менее {minimum}", None
        
        if maximum is not None and normalized > maximum:
            return False, f"Параметр {param_name} должен быть не более {maximum}", None
        
    elif param_type == "boolean":
        if isinstance(param_value, bool):
            normalized = param_value
        elif isinstance(param_value, str):
            normalized = param_value.lower() in ('true', '1', 'yes', 'да')
        else:
            return False, f"Параметр {param_name} должен быть boolean", None
        
    elif param_type == "array":
        if not isinstance(param_value, list):
            return False, f"Параметр {param_name} должен быть массивом", None
        
        # Проверка minItems/maxItems
        min_items = param_schema.get("minItems")
        max_items = param_schema.get("maxItems")
        
        if min_items is not None and len(param_value) < min_items:
            return False, f"Параметр {param_name} должен содержать не менее {min_items} элементов", None
        
        if max_items is not None and len(param_value) > max_items:
            return False, f"Параметр {param_name} должен содержать не более {max_items} элементов", None
        
        normalized = param_value
        
    else:
        normalized = param_value
    
    # Валидация enum
    enum_values = param_schema.get("enum")
    if enum_values:
        if normalized not in enum_values:
            return False, f"Параметр {param_name} должен быть одним из: {', '.join(map(str, enum_values))}", None
    
    return True, None, normalized


def validate_all_parameters_strict(
    params: Dict[str, Any],
    input_schema: Dict[str, Any]
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Валидирует все параметры строго согласно схеме.
    
    Args:
        params: Параметры для проверки
        input_schema: Схема входных данных
    
    Returns:
        (валидно, список_ошибок, нормализованные_параметры)
    """
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    
    errors = []
    normalized_params = {}
    
    # Проверяем обязательные параметры
    for param_name in required:
        if param_name not in params:
            errors.append(f"Обязательный параметр {param_name} отсутствует")
    
    # Валидируем все переданные параметры
    for param_name, param_value in params.items():
        if param_name not in properties:
            logger.warning(f"⚠️ Неизвестный параметр {param_name}, пропускаем")
            continue
        
        param_schema = properties[param_name]
        is_valid, error_msg, normalized_value = validate_parameter_strict(
            param_name,
            param_value,
            param_schema
        )
        
        if not is_valid:
            errors.append(error_msg)
        else:
            normalized_params[param_name] = normalized_value
    
    # Применяем значения по умолчанию для отсутствующих параметров
    for param_name, param_schema in properties.items():
        if param_name not in normalized_params and "default" in param_schema:
            normalized_params[param_name] = param_schema["default"]
    
    return len(errors) == 0, errors, normalized_params


def get_parameter_hint(param_name: str, param_schema: Dict[str, Any], user_lang: str = 'ru') -> str:
    """
    Получает подсказку для параметра.
    
    Args:
        param_name: Название параметра
        param_schema: Схема параметра
        user_lang: Язык пользователя
    
    Returns:
        Подсказка для пользователя
    """
    description = param_schema.get("description", "")
    param_type = param_schema.get("type", "string")
    enum_values = param_schema.get("enum")
    default = param_schema.get("default")
    
    hint_parts = []
    
    if description:
        hint_parts.append(description)
    
    if enum_values:
        if user_lang == 'ru':
            hint_parts.append(f"Доступные значения: {', '.join(map(str, enum_values))}")
        else:
            hint_parts.append(f"Available values: {', '.join(map(str, enum_values))}")
    
    if default is not None:
        if user_lang == 'ru':
            hint_parts.append(f"По умолчанию: {default}")
        else:
            hint_parts.append(f"Default: {default}")
    
    if param_type == "integer" or param_type == "number":
        minimum = param_schema.get("minimum")
        maximum = param_schema.get("maximum")
        if minimum is not None or maximum is not None:
            range_text = f"{minimum or '?'}-{maximum or '?'}"
            if user_lang == 'ru':
                hint_parts.append(f"Диапазон: {range_text}")
            else:
                hint_parts.append(f"Range: {range_text}")
    
    if param_type == "string":
        max_length = param_schema.get("maxLength")
        if max_length:
            if user_lang == 'ru':
                hint_parts.append(f"Максимум символов: {max_length}")
            else:
                hint_parts.append(f"Max length: {max_length}")
    
    return "\n".join(hint_parts) if hint_parts else ""

