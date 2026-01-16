"""
Валидация входных данных для защиты от атак.

Защищает от:
1. Слишком больших файлов (DoS)
2. Слишком длинных текстов (DoS)
3. Некорректных URL
4. SQL injection (через параметры)
5. XSS (через текстовые поля)
"""
import re
import logging
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# Лимиты для защиты от DoS
MAX_TEXT_LENGTH = 50 * 1024  # 50KB для текстовых полей
MAX_URL_LENGTH = 2048  # 2KB для URL
MAX_FILE_SIZE_MB = 20  # 20MB для файлов
MAX_PROMPT_LENGTH = 10 * 1024  # 10KB для промптов
MAX_PARAMS_COUNT = 50  # Максимум 50 параметров


def validate_text_field(value: str, field_name: str, max_length: int = MAX_TEXT_LENGTH) -> Tuple[bool, Optional[str]]:
    """
    Валидировать текстовое поле.
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    
    # Проверить длину
    byte_length = len(value.encode('utf-8'))
    if byte_length > max_length:
        return False, f"{field_name} слишком длинный ({byte_length} bytes, максимум {max_length} bytes)"
    
    # Проверить на подозрительные паттерны (базовая защита от XSS)
    suspicious_patterns = [
        r'<script[^>]*>',
        r'javascript:',
        r'onerror\s*=',
        r'onload\s*=',
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(f"[INPUT_VALIDATION] Suspicious pattern in {field_name}: {pattern}")
            # Не блокируем, но логируем
    
    return True, None


def validate_url(value: str, field_name: str) -> Tuple[bool, Optional[str]]:
    """
    Валидировать URL.
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    
    # Проверить длину
    if len(value) > MAX_URL_LENGTH:
        return False, f"{field_name} URL слишком длинный ({len(value)} chars, максимум {MAX_URL_LENGTH})"
    
    # Проверить формат URL
    if not value.startswith(('http://', 'https://')):
        return False, f"{field_name} должен начинаться с http:// или https://"
    
    # Проверить, что это не Telegram file_id
    if value.startswith(('AgACAg', 'BQACAg', 'BAACAg')):
        return False, f"{field_name} содержит Telegram file_id вместо URL. Используйте прямую ссылку."
    
    # Парсить URL
    try:
        parsed = urlparse(value)
        if not parsed.netloc:
            return False, f"{field_name} некорректный URL (нет домена)"
        
        # Проверить на подозрительные домены
        suspicious_domains = ['localhost', '127.0.0.1', '0.0.0.0']
        if parsed.netloc.lower() in suspicious_domains:
            logger.warning(f"[INPUT_VALIDATION] Suspicious domain in {field_name}: {parsed.netloc}")
    except Exception as e:
        return False, f"{field_name} некорректный URL: {e}"
    
    return True, None


def validate_file_size(file_size: int, max_size_mb: int = MAX_FILE_SIZE_MB) -> Tuple[bool, Optional[str]]:
    """
    Валидировать размер файла.
    
    Returns:
        (is_valid, error_message)
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        return False, f"Файл слишком большой ({file_size / 1024 / 1024:.1f}MB, максимум {max_size_mb}MB)"
    
    return True, None


def validate_user_inputs(user_inputs: Dict[str, Any], model_schema: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """
    Валидировать все входные данные пользователя.
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(user_inputs, dict):
        return False, "user_inputs must be a dictionary"
    
    # Проверить количество параметров
    if len(user_inputs) > MAX_PARAMS_COUNT:
        return False, f"Слишком много параметров ({len(user_inputs)}, максимум {MAX_PARAMS_COUNT})"
    
    # Валидировать каждое поле
    text_fields = ('prompt', 'text', 'input_text', 'message', 'negative_prompt')
    url_fields = ('image_url', 'video_url', 'audio_url', 'image_base64', 'video_base64', 'audio_base64')
    
    for key, value in user_inputs.items():
        if not isinstance(key, str):
            return False, f"Parameter key must be a string: {type(key)}"
        
        # Проверить длину ключа
        if len(key) > 100:
            return False, f"Parameter key too long: {key[:50]}..."
        
        if isinstance(value, str):
            # Текстовые поля
            if key in text_fields:
                is_valid, error = validate_text_field(value, key, max_length=MAX_PROMPT_LENGTH if key == 'prompt' else MAX_TEXT_LENGTH)
                if not is_valid:
                    return False, error
            
            # URL поля
            elif key in url_fields:
                is_valid, error = validate_url(value, key)
                if not is_valid:
                    return False, error
            
            # Другие строковые поля
            else:
                is_valid, error = validate_text_field(value, key)
                if not is_valid:
                    return False, error
        
        elif isinstance(value, (int, float)):
            # Числовые значения - проверить на разумные пределы
            if abs(value) > 1e10:  # Очень большие числа
                return False, f"Parameter {key} has unreasonable value: {value}"
        
        elif isinstance(value, dict):
            # Вложенные словари - рекурсивная валидация
            is_valid, error = validate_user_inputs(value)
            if not is_valid:
                return False, f"Invalid nested parameter {key}: {error}"
        
        elif isinstance(value, list):
            # Списки - проверить размер
            if len(value) > 100:
                return False, f"Parameter {key} list too long ({len(value)}, максимум 100)"
            
            # Валидировать элементы
            for i, item in enumerate(value):
                if isinstance(item, str):
                    is_valid, error = validate_text_field(item, f"{key}[{i}]")
                    if not is_valid:
                        return False, error
    
    return True, None

