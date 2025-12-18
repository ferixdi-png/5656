"""
Модуль для упрощения валидации входных данных.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)

# Кеш для схем валидации
_validation_schemas: Dict[str, Dict[str, Any]] = {}


def validate_input_unified(
    input_type: str,
    value: Any,
    schema: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Унифицированная валидация входных данных.
    
    Args:
        input_type: Тип входных данных ('prompt', 'url', 'parameter', 'number')
        value: Значение для проверки
        schema: Схема валидации (опционально)
    
    Returns:
        (валидно, сообщение_об_ошибке)
    """
    if input_type == 'prompt':
        from input_validation import validate_prompt
        return validate_prompt(value if isinstance(value, str) else str(value))
    
    elif input_type == 'url':
        from input_validation import validate_url
        return validate_url(value if isinstance(value, str) else str(value))
    
    elif input_type == 'parameter':
        if not schema:
            return True, None
        
        from input_validation import validate_parameter_value
        param_name = schema.get('name', 'parameter')
        return validate_parameter_value(param_name, value, schema)
    
    elif input_type == 'number':
        if not isinstance(value, (int, float)):
            return False, "Значение должно быть числом"
        
        if schema:
            min_val = schema.get('minimum')
            max_val = schema.get('maximum')
            
            if min_val is not None and value < min_val:
                return False, f"Значение должно быть не менее {min_val}"
            
            if max_val is not None and value > max_val:
                return False, f"Значение должно быть не более {max_val}"
        
        return True, None
    
    return True, None


def validate_all_params_at_once(
    params: Dict[str, Any],
    param_schemas: Dict[str, Dict[str, Any]]
) -> Tuple[bool, List[str]]:
    """
    Валидирует все параметры за один проход.
    
    Args:
        params: Параметры для проверки
        param_schemas: Схемы параметров
    
    Returns:
        (валидно, список_ошибок)
    """
    errors = []
    
    for param_name, param_value in params.items():
        if param_name in param_schemas:
            schema = param_schemas[param_name]
            param_type = schema.get('type', 'string')
            
            is_valid, error_msg = validate_input_unified(
                'parameter',
                param_value,
                schema
            )
            
            if not is_valid:
                errors.append(f"{param_name}: {error_msg}")
    
    return len(errors) == 0, errors


def get_parameter_hint_optimized(
    param_name: str,
    param_value: Any,
    lang: str = 'ru',
    show_price_impact: bool = True
) -> str:
    """
    Оптимизированная подсказка для параметра.
    Объединяет информацию о параметре и его влиянии на цену.
    
    Args:
        param_name: Название параметра
        param_value: Значение параметра
        lang: Язык
        show_price_impact: Показывать ли влияние на цену
    
    Returns:
        Подсказка
    """
    hints = []
    
    # Базовая подсказка о параметре
    try:
        from optimization_ux import get_parameter_hint
        base_hint = get_parameter_hint(param_name, lang)
        if base_hint:
            hints.append(base_hint)
    except ImportError:
        pass
    
    # Подсказка о влиянии на цену
    if show_price_impact:
        try:
            from pricing_transparency import get_price_hint_for_parameter
            price_hint = get_price_hint_for_parameter(param_name, param_value, lang)
            if price_hint:
                hints.append(price_hint)
        except ImportError:
            pass
    
    # Объединяем подсказки
    if hints:
        return "\n".join(hints)
    
    return ""

