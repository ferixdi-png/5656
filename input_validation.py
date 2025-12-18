"""
Модуль для проверки входных данных.
Включает валидацию через регулярные выражения и другие методы.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def validate_prompt(prompt: str, max_length: int = 1000) -> tuple[bool, Optional[str]]:
    """
    Проверяет корректность промпта.
    
    Args:
        prompt: Текстовый промпт
        max_length: Максимальная длина промпта
    
    Returns:
        (валидно, сообщение_об_ошибке)
    """
    if not prompt or not isinstance(prompt, str):
        return False, "Промпт не может быть пустым"
    
    if len(prompt) > max_length:
        return False, f"Промпт слишком длинный (максимум {max_length} символов)"
    
    if len(prompt.strip()) < 3:
        return False, "Промпт слишком короткий (минимум 3 символа)"
    
    # Проверяем на потенциально опасные паттерны
    dangerous_patterns = [
        r'<script',
        r'javascript:',
        r'onerror=',
        r'onload=',
        r'eval\(',
        r'exec\('
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            return False, "Промпт содержит недопустимые символы"
    
    return True, None


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Проверяет корректность URL.
    
    Args:
        url: URL для проверки
    
    Returns:
        (валидно, сообщение_об_ошибке)
    """
    if not url or not isinstance(url, str):
        return False, "URL не может быть пустым"
    
    try:
        parsed = urlparse(url)
        
        # Проверяем схему
        if parsed.scheme not in ['http', 'https']:
            return False, "URL должен использовать HTTP или HTTPS"
        
        # Проверяем наличие домена
        if not parsed.netloc:
            return False, "URL должен содержать домен"
        
        # Проверяем на опасные паттерны
        dangerous_patterns = [
            r'javascript:',
            r'data:',
            r'file:',
            r'<script'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False, "URL содержит недопустимые символы"
        
        return True, None
        
    except Exception as e:
        return False, f"Ошибка при проверке URL: {str(e)}"


def validate_parameter_value(param_name: str, param_value: Any, param_schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Проверяет корректность значения параметра на основе схемы.
    
    Args:
        param_name: Название параметра
        param_value: Значение параметра
        param_schema: Схема параметра
    
    Returns:
        (валидно, сообщение_об_ошибке)
    """
    param_type = param_schema.get('type', 'string')
    
    # Проверка типа
    if param_type == 'string':
        if not isinstance(param_value, str):
            return False, f"Параметр {param_name} должен быть строкой"
        
        # Проверка max_length
        max_length = param_schema.get('max_length')
        if max_length and len(param_value) > max_length:
            return False, f"Параметр {param_name} слишком длинный (максимум {max_length} символов)"
        
        # Проверка min_length
        min_length = param_schema.get('min_length')
        if min_length and len(param_value) < min_length:
            return False, f"Параметр {param_name} слишком короткий (минимум {min_length} символов)"
        
        # Проверка enum
        enum_values = param_schema.get('enum')
        if enum_values and param_value not in enum_values:
            return False, f"Параметр {param_name} должен быть одним из: {', '.join(enum_values)}"
    
    elif param_type == 'number':
        if not isinstance(param_value, (int, float)):
            return False, f"Параметр {param_name} должен быть числом"
        
        # Проверка min/max
        min_value = param_schema.get('minimum')
        if min_value is not None and param_value < min_value:
            return False, f"Параметр {param_name} должен быть не менее {min_value}"
        
        max_value = param_schema.get('maximum')
        if max_value is not None and param_value > max_value:
            return False, f"Параметр {param_name} должен быть не более {max_value}"
    
    elif param_type == 'boolean':
        if not isinstance(param_value, bool):
            return False, f"Параметр {param_name} должен быть булевым значением"
    
    elif param_type == 'array':
        if not isinstance(param_value, list):
            return False, f"Параметр {param_name} должен быть массивом"
        
        # Проверка min_items/max_items
        min_items = param_schema.get('min_items')
        if min_items and len(param_value) < min_items:
            return False, f"Параметр {param_name} должен содержать минимум {min_items} элементов"
        
        max_items = param_schema.get('max_items')
        if max_items and len(param_value) > max_items:
            return False, f"Параметр {param_name} должен содержать максимум {max_items} элементов"
    
    return True, None


def validate_generation_params(model_id: str, params: Dict[str, Any], model_schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Проверяет все параметры генерации.
    
    Args:
        model_id: ID модели
        params: Параметры для проверки
        model_schema: Схема модели
    
    Returns:
        (валидно, список_ошибок)
    """
    errors = []
    
    # Получаем схему параметров
    input_schema = model_schema.get('input_schema', {})
    properties = input_schema.get('properties', {})
    required = input_schema.get('required', [])
    
    # Проверяем обязательные параметры
    for param_name in required:
        if param_name not in params:
            errors.append(f"Обязательный параметр {param_name} отсутствует")
    
    # Проверяем каждый параметр
    for param_name, param_value in params.items():
        if param_name in properties:
            param_schema = properties[param_name]
            is_valid, error_msg = validate_parameter_value(param_name, param_value, param_schema)
            
            if not is_valid:
                errors.append(error_msg)
        else:
            # Неизвестный параметр (может быть допустимо, в зависимости от модели)
            logger.warning(f"⚠️ Неизвестный параметр {param_name} для модели {model_id}")
    
    return len(errors) == 0, errors

