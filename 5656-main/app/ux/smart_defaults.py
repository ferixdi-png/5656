"""
Smart Defaults System - BATCH 43

Автоматически применяет дефолтные значения для всех необязательных параметров.
Спрашивает пользователя ТОЛЬКО обязательные параметры.

Принципы:
1. required: True → спрашиваем пользователя
2. required: False + default: "value" → автоматически применяем
3. Кнопка "⚙️ Настройки" → пользователь может изменить defaults
"""
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


def apply_smart_defaults(model_id: str, user_inputs: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply smart defaults for all optional parameters.
    
    Args:
        model_id: Model ID
        user_inputs: User-provided inputs (only required fields)
        schema: Model input schema
        
    Returns:
        Complete inputs with defaults applied
    """
    result = dict(user_inputs)  # Copy user inputs
    
    for param_name, param_spec in schema.items():
        # Skip if user already provided
        if param_name in result:
            continue
        
        # Apply default for optional params
        if not param_spec.get("required", False):
            default_value = param_spec.get("default")
            if default_value is not None:
                result[param_name] = default_value
                logger.debug(
                    f"[SMART_DEFAULTS] model={model_id} param={param_name} "
                    f"default={default_value}"
                )
    
    return result


def get_required_fields(schema: Dict[str, Any]) -> List[str]:
    """
    Get list of required field names.
    
    Args:
        schema: Model input schema
        
    Returns:
        List of required field names
    """
    return [
        field_name
        for field_name, field_spec in schema.items()
        if field_spec.get("required", False)
    ]


def get_optional_fields(schema: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """
    Get list of optional fields with their defaults.
    
    Args:
        schema: Model input schema
        
    Returns:
        List of (field_name, default_value) tuples
    """
    optional = []
    for field_name, field_spec in schema.items():
        if not field_spec.get("required", False):
            default_value = field_spec.get("default")
            if default_value is not None:
                optional.append((field_name, default_value))
    
    return optional


def get_user_friendly_field_name(field_name: str, field_spec: Dict[str, Any]) -> str:
    """
    Get user-friendly name for field.
    
    Args:
        field_name: Technical field name
        field_spec: Field specification
        
    Returns:
        User-friendly field name in Russian
    """
    # Try to extract from description
    description = field_spec.get("description", "")
    if description:
        # Take first sentence before period or colon
        first_part = description.split(".")[0].split(":")[0].strip()
        if first_part and len(first_part) < 100:
            return first_part
    
    # Fallback: capitalize field name
    return field_name.replace("_", " ").capitalize()


def format_default_value(value: Any, field_spec: Dict[str, Any]) -> str:
    """
    Format default value for user display.
    
    Args:
        value: Default value
        field_spec: Field specification
        
    Returns:
        Formatted value string
    """
    field_type = field_spec.get("type", "string")
    
    if field_type == "boolean":
        return "Да" if value else "Нет"
    elif field_type in ("integer", "float", "number"):
        return str(value)
    elif field_type == "string":
        if field_spec.get("enum"):
            # For enum, show value as-is
            return str(value)
        # For free text, truncate if too long
        str_value = str(value)
        return str_value if len(str_value) < 50 else str_value[:47] + "..."
    else:
        return str(value)


def get_settings_summary(schema: Dict[str, Any], current_values: Dict[str, Any]) -> str:
    """
    Get summary of current settings for display.
    
    Args:
        schema: Model input schema
        current_values: Current values (with defaults applied)
        
    Returns:
        Formatted summary string
    """
    lines = ["⚙️ <b>Текущие настройки:</b>\n"]
    
    optional = get_optional_fields(schema)
    if not optional:
        return "⚙️ Нет дополнительных настроек для этой модели"
    
    for field_name, default_value in optional:
        field_spec = schema[field_name]
        friendly_name = get_user_friendly_field_name(field_name, field_spec)
        current_value = current_values.get(field_name, default_value)
        formatted_value = format_default_value(current_value, field_spec)
        
        lines.append(f"• <b>{friendly_name}:</b> {formatted_value}")
    
    lines.append("\n💡 <i>Эти значения установлены автоматически, но вы можете их изменить</i>")
    
    return "\n".join(lines)


def validate_custom_value(value: Any, field_spec: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate user-provided custom value.
    
    Args:
        value: User value
        field_spec: Field specification
        
    Returns:
        (is_valid, error_message)
    """
    field_type = field_spec.get("type", "string")
    
    # Type validation
    if field_type in ("integer", "int"):
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            return False, "❌ Значение должно быть целым числом"
        
        # Range validation
        min_val = field_spec.get("min")
        max_val = field_spec.get("max")
        if min_val is not None and int_value < min_val:
            return False, f"❌ Значение должно быть >= {min_val}"
        if max_val is not None and int_value > max_val:
            return False, f"❌ Значение должно быть <= {max_val}"
    
    elif field_type in ("float", "number"):
        try:
            float_value = float(value)
        except (TypeError, ValueError):
            return False, "❌ Значение должно быть числом"
        
        # Range validation
        min_val = field_spec.get("min")
        max_val = field_spec.get("max")
        if min_val is not None and float_value < min_val:
            return False, f"❌ Значение должно быть >= {min_val}"
        if max_val is not None and float_value > max_val:
            return False, f"❌ Значение должно быть <= {max_val}"
    
    elif field_type == "boolean":
        if str(value).lower() not in ("true", "false", "да", "нет", "yes", "no", "1", "0"):
            return False, "❌ Значение должно быть: да/нет или true/false"
    
    elif field_type == "string":
        # Enum validation
        enum_values = field_spec.get("enum")
        if enum_values and value not in enum_values:
            enum_str = ", ".join(enum_values)
            return False, f"❌ Допустимые значения: {enum_str}"
        
        # Length validation
        max_length = field_spec.get("max_length")
        if max_length and len(str(value)) > max_length:
            return False, f"❌ Максимальная длина: {max_length} символов"
    
    return True, None

