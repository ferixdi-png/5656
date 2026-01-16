"""
Builder для входных параметров KIE AI API.
Собирает input строго по типу модели, валидирует и нормализует.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple, List
from app.kie_catalog.catalog import ModelSpec, ModelMode
from app.kie_catalog.input_schemas import (
    get_schema_for_type,
    get_required_fields_for_type,
    normalize_field_name,
    get_default_value
)
from app.config import get_settings

logger = logging.getLogger(__name__)


def _parse_duration_from_notes(notes: Optional[str]) -> Optional[float]:
    """
    Парсит duration из notes (например "5.0s" -> 5.0).
    
    Args:
        notes: Строка с notes режима
    
    Returns:
        Duration в секундах или None
    """
    if not notes:
        return None
    
    # Ищем паттерны типа "5.0s", "10.0s", "5s", "10s"
    match = re.search(r'(\d+\.?\d*)s', notes, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    
    return None


def _parse_resolution_from_notes(notes: Optional[str]) -> Optional[str]:
    """
    Парсит resolution из notes (например "720p", "1080p").
    
    Args:
        notes: Строка с notes режима
    
    Returns:
        Resolution или None
    """
    if not notes:
        return None
    
    # Ищем паттерны типа "720p", "1080p", "1K", "2K", "4K"
    match = re.search(r'(\d+p|\d+K)', notes, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    
    return None


def _check_required_fields(
    model_type: str,
    input_data: Dict[str, Any],
    required_fields: Set[str]
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет наличие обязательных полей.
    
    Args:
        model_type: Тип модели
        input_data: Входные данные
        required_fields: Множество обязательных полей
    
    Returns:
        (is_valid, error_message)
    """
    if not required_fields:
        return True, None
    
    # Для полей типа image_url/image_base64/image проверяем хотя бы одно
    image_fields = {'image_url', 'image_base64', 'image'}
    video_fields = {'video_url', 'video'}
    audio_fields = {'audio_url', 'audio'}
    
    # Проверяем группы полей
    if image_fields.intersection(required_fields):
        has_image = any(
            input_data.get(field) for field in image_fields
            if field in input_data and input_data[field]
        )
        if not has_image:
            if model_type == 'i2i':
                return False, "Нужно загрузить изображение для генерации"
            elif model_type == 'i2v':
                return False, "Нужно загрузить изображение для создания видео"
            elif model_type in ['upscale', 'bg_remove', 'watermark_remove']:
                return False, "Нужно загрузить изображение"
    
    if video_fields.intersection(required_fields):
        has_video = any(
            input_data.get(field) for field in video_fields
            if field in input_data and input_data[field]
        )
        if not has_video:
            if model_type == 'v2v':
                return False, "Нужно загрузить видео"
            elif model_type == 'lip_sync':
                return False, "Нужно загрузить видео или изображение"
    
    if audio_fields.intersection(required_fields):
        has_audio = any(
            input_data.get(field) for field in audio_fields
            if field in input_data and input_data[field]
        )
        if not has_audio:
            if model_type == 'stt':
                return False, "Нужно загрузить аудио"
            elif model_type == 'audio_isolation':
                return False, "Нужно загрузить аудио"
            elif model_type == 'lip_sync':
                return False, "Нужно загрузить аудио"
    
    # Проверяем остальные обязательные поля
    for field in required_fields:
        if field in image_fields or field in video_fields or field in audio_fields:
            continue  # Уже проверили выше
        
        if field not in input_data or not input_data[field]:
            if field == 'prompt':
                return False, "Введите текст для генерации"
            elif field == 'text':
                return False, "Введите текст для синтеза речи"
            else:
                return False, f"Поле '{field}' обязательно"
    
    return True, None


def _normalize_duration_for_wan_2_6(value: Any) -> Optional[str]:
    """
    Нормализует duration для wan/2-6-text-to-video.
    Принимает числа (5, 10, 15) или строки ("5", "10", "15") и возвращает строку.
    
    Args:
        value: Значение duration (может быть int, float, str)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Убираем "s" или "seconds" в конце, если есть
    if str_value.lower().endswith('seconds'):
        str_value = str_value[:-7].strip()
    elif str_value.lower().endswith('s'):
        str_value = str_value[:-1].strip()
    
    # Проверяем что это валидное значение
    valid_values = ["5", "10", "15"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем конвертировать число в строку
    try:
        num_value = float(str_value)
        if num_value == 5.0 or num_value == 5:
            return "5"
        elif num_value == 10.0 or num_value == 10:
            return "10"
        elif num_value == 15.0 or num_value == 15:
            return "15"
    except (ValueError, TypeError):
        pass
    
    return None


def _normalize_resolution_for_wan_2_6(value: Any) -> Optional[str]:
    """
    Нормализует resolution для wan/2-6-text-to-video.
    Принимает строки ("720p", "1080p") и возвращает нормализованную строку.
    
    Args:
        value: Значение resolution
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    str_value = str(value).strip().lower()
    
    # Убеждаемся что есть суффикс "p"
    if not str_value.endswith('p'):
        str_value = str_value + 'p'
    
    # Проверяем что это валидное значение
    valid_values = ["720p", "1080p"]
    if str_value in valid_values:
        return str_value
    
    return None


def _normalize_video_urls_for_wan_2_6(value: Any) -> Optional[List[str]]:
    """
    Нормализует video_urls для wan/2-6-video-to-video.
    Принимает строку, массив строк или None и возвращает массив строк.
    
    Args:
        value: Значение video_urls (может быть str, list, None)
    
    Returns:
        Нормализованный массив URL или None
    """
    if value is None:
        return None
    
    # Если это строка, конвертируем в массив
    if isinstance(value, str):
        if value.strip():
            return [value.strip()]
        return None
    
    # Если это массив, проверяем и нормализуем элементы
    if isinstance(value, list):
        normalized = []
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip())
        return normalized if normalized else None
    
    return None


def _normalize_duration_for_wan_2_6_v2v(value: Any) -> Optional[str]:
    """
    Нормализует duration для wan/2-6-video-to-video.
    Принимает числа (5, 10) или строки ("5", "10") и возвращает строку.
    ВАЖНО: Для v2v поддерживаются только "5" и "10", не "15"!
    
    Args:
        value: Значение duration (может быть int, float, str)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Убираем "s" или "seconds" в конце, если есть
    if str_value.lower().endswith('seconds'):
        str_value = str_value[:-7].strip()
    elif str_value.lower().endswith('s'):
        str_value = str_value[:-1].strip()
    
    # Проверяем что это валидное значение (только 5 и 10 для v2v!)
    valid_values = ["5", "10"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем конвертировать число в строку
    try:
        num_value = float(str_value)
        if num_value == 5.0 or num_value == 5:
            return "5"
        elif num_value == 10.0 or num_value == 10:
            return "10"
    except (ValueError, TypeError):
        pass
    
    return None


def _normalize_image_urls_for_wan_2_6(value: Any) -> Optional[List[str]]:
    """
    Нормализует image_urls для wan/2-6-image-to-video.
    Принимает строку, массив строк или None и возвращает массив строк.
    
    Args:
        value: Значение image_urls (может быть str, list, None)
    
    Returns:
        Нормализованный массив URL или None
    """
    if value is None:
        return None
    
    # Если это строка, конвертируем в массив
    if isinstance(value, str):
        if value.strip():
            return [value.strip()]
        return None
    
    # Если это массив, проверяем и нормализуем элементы
    if isinstance(value, list):
        normalized = []
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip())
        return normalized if normalized else None
    
    return None


def _normalize_resolution_for_wan_2_5(value: Any) -> Optional[str]:
    """
    Нормализует resolution для wan/2-5-image-to-video.
    Принимает значение и возвращает нормализованную строку в нижнем регистре.
    ВАЖНО: Для wan/2-5-image-to-video поддерживаются только "720p" и "1080p"!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["720p", "1080p"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    if str_value in ["720", "720p", "hd"]:
        return "720p"
    elif str_value in ["1080", "1080p", "fullhd", "fhd"]:
        return "1080p"
    
    return None


def _normalize_boolean(value: Any) -> Optional[bool]:
    """
    Нормализует boolean значение для enable_prompt_expansion.
    Принимает значение и возвращает bool или None.
    
    Args:
        value: Значение (может быть str, int, bool)
    
    Returns:
        bool или None
    """
    if value is None:
        return None
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    if isinstance(value, str):
        str_lower = value.strip().lower()
        if str_lower in ["true", "1", "yes", "y", "on"]:
            return True
        elif str_lower in ["false", "0", "no", "n", "off"]:
            return False
    
    return None


def _validate_wan_2_5_text_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-5-text-to-video согласно документации API.
    
    ВАЖНО: Отличается от wan/2-6-text-to-video:
    - prompt максимум 800 символов (в 2-6 было 5000)
    - negative_prompt максимум 500 символов (в 2-6 было больше)
    - Есть параметр enable_prompt_expansion (boolean)
    - resolution только "720p" | "1080p" (в 2-6 были другие значения)
    - aspect_ratio "16:9" | "9:16" | "1:1" (в 2-6 были другие значения)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["wan/2-5-text-to-video", "wan/2.5-text-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 800 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 800:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 800)"
    
    # Валидация duration: опциональный, "5" | "10", default "5"
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_wan_2_6(duration)  # Переиспользуем функцию (те же значения "5" и "10")
        if normalized_duration is None or normalized_duration not in ["5", "10"]:
            valid_values = ["5", "10"]
            return False, f"Поле 'duration' должно быть одним из: {', '.join(valid_values)} (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация aspect_ratio: опциональный, "16:9" | "9:16" | "1:1", default "16:9"
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        normalized_aspect_ratio = _normalize_aspect_ratio_for_kling_v2_5_turbo(aspect_ratio)  # Переиспользуем функцию (те же значения)
        if normalized_aspect_ratio is None:
            valid_values = ["16:9", "9:16", "1:1"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация resolution: опциональный, "720p" | "1080p", default "1080p"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_wan_2_5(resolution)
        if normalized_resolution is None:
            valid_values = ["720p", "1080p"]
            return False, f"Поле 'resolution' должно быть одним из: {', '.join(valid_values)} (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    # Валидация negative_prompt: опциональный, максимум 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        
        negative_prompt = negative_prompt.strip()
        negative_prompt_len = len(negative_prompt)
        if negative_prompt_len > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {negative_prompt_len} символов (максимум 500)"
        # Если пустая строка, удаляем параметр
        if not negative_prompt:
            del normalized_input['negative_prompt']
        else:
            normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация enable_prompt_expansion: опциональный boolean
    enable_prompt_expansion = normalized_input.get('enable_prompt_expansion')
    if enable_prompt_expansion is not None:
        normalized_bool = _normalize_boolean(enable_prompt_expansion)
        if normalized_bool is None:
            return False, f"Поле 'enable_prompt_expansion' должно быть boolean (true/false) (получено: {enable_prompt_expansion})"
        normalized_input['enable_prompt_expansion'] = normalized_bool
    
    # Валидация seed: опциональный number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(seed) if isinstance(seed, (int, float, str)) else None
            if seed_num is None:
                return False, f"Поле 'seed' должно быть числом (получено: {seed})"
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    return True, None


def _validate_wan_2_5_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-5-image-to-video согласно документации API.
    
    ВАЖНО: Отличается от wan/2-6-image-to-video:
    - prompt максимум 800 символов (в 2-6 было 5000)
    - image_url обязательный string (не массив image_urls!)
    - negative_prompt максимум 500 символов (в 2-6 было больше)
    - Есть параметр enable_prompt_expansion (boolean)
    - resolution только "720p" | "1080p" (в 2-6 были другие значения)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["wan/2-5-image-to-video", "wan/2.5-image-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 800 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 800:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 800)"
    
    # Валидация image_url: обязательный string (не массив!)
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения"
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if not image_url:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not image_url.startswith(('http://', 'https://')):
        return False, "Поле 'image_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['image_url'] = image_url
    
    # ВАЖНО: Удаляем image_urls если он был передан (для этой модели нужен только image_url как string!)
    if 'image_urls' in normalized_input:
        logger.warning(f"Parameter 'image_urls' is not supported for wan/2-5-image-to-video (use 'image_url' as string), removing it")
        del normalized_input['image_urls']
    
    # Валидация duration: опциональный, "5" | "10", default "5"
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_wan_2_6(duration)  # Переиспользуем функцию (те же значения "5" и "10")
        if normalized_duration is None or normalized_duration not in ["5", "10"]:
            valid_values = ["5", "10"]
            return False, f"Поле 'duration' должно быть одним из: {', '.join(valid_values)} (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация resolution: опциональный, "720p" | "1080p", default "1080p"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_wan_2_5(resolution)
        if normalized_resolution is None:
            valid_values = ["720p", "1080p"]
            return False, f"Поле 'resolution' должно быть одним из: {', '.join(valid_values)} (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    # Валидация negative_prompt: опциональный, максимум 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        
        negative_prompt = negative_prompt.strip()
        negative_prompt_len = len(negative_prompt)
        if negative_prompt_len > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {negative_prompt_len} символов (максимум 500)"
        # Если пустая строка, удаляем параметр
        if not negative_prompt:
            del normalized_input['negative_prompt']
        else:
            normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация enable_prompt_expansion: опциональный boolean
    enable_prompt_expansion = normalized_input.get('enable_prompt_expansion')
    if enable_prompt_expansion is not None:
        normalized_bool = _normalize_boolean(enable_prompt_expansion)
        if normalized_bool is None:
            return False, f"Поле 'enable_prompt_expansion' должно быть boolean (true/false) (получено: {enable_prompt_expansion})"
        normalized_input['enable_prompt_expansion'] = normalized_bool
    
    # Валидация seed: опциональный number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(seed) if isinstance(seed, (int, float, str)) else None
            if seed_num is None:
                return False, f"Поле 'seed' должно быть числом (получено: {seed})"
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    return True, None


def _validate_wan_2_6_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-6-image-to-video согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "wan/2-6-image-to-video":
        return True, None
    
    # Валидация prompt: обязательный, 2-5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len < 2:
        return False, "Поле 'prompt' должно содержать минимум 2 символа"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_urls: обязательный массив
    # Проверяем различные варианты имени поля
    image_urls = None
    if 'image_urls' in normalized_input:
        image_urls = normalized_input['image_urls']
    elif 'image_url' in normalized_input:
        # Конвертируем image_url в image_urls
        image_urls = normalized_input['image_url']
    elif 'image' in normalized_input:
        image_urls = normalized_input['image']
    
    if not image_urls:
        return False, "Поле 'image_urls' обязательно для генерации видео из изображения"
    
    # Нормализуем image_urls
    normalized_image_urls = _normalize_image_urls_for_wan_2_6(image_urls)
    if not normalized_image_urls:
        return False, "Поле 'image_urls' должно содержать хотя бы один валидный URL изображения"
    
    # Проверяем что все URL начинаются с http:// или https://
    for idx, url in enumerate(normalized_image_urls):
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, f"URL изображения #{idx + 1} должен начинаться с http:// или https://"
    
    # Сохраняем нормализованное значение
    normalized_input['image_urls'] = normalized_image_urls
    
    # Валидация duration: опциональный, "5" | "10" | "15", default "5"
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_wan_2_6(duration)
        if normalized_duration is None:
            return False, f"Поле 'duration' должно быть '5', '10' или '15' (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация resolution: опциональный, "720p" | "1080p", default "1080p"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_wan_2_6(resolution)
        if normalized_resolution is None:
            return False, f"Поле 'resolution' должно быть '720p' или '1080p' (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _normalize_resolution_for_wan_2_2_animate_move(value: Any) -> Optional[str]:
    """
    Нормализует resolution для wan/2-2-animate-move.
    Принимает значение и возвращает нормализованную строку в нижнем регистре.
    ВАЖНО: Для wan/2-2-animate-move поддерживаются только "480p", "580p" и "720p"!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["480p", "580p", "720p"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    if str_value in ["480", "480p"]:
        return "480p"
    elif str_value in ["580", "580p"]:
        return "580p"
    elif str_value in ["720", "720p", "hd"]:
        return "720p"
    
    return None


def _validate_wan_2_2_animate_replace(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-2-animate-replace согласно документации API.
    
    ВАЖНО: Эта модель требует и video_url, и image_url (оба обязательны)!
    Это уникальная модель, которая заменяет объекты в видео на основе изображения.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["wan/2-2-animate-replace", "wan/2.2-animate-replace"]:
        return True, None
    
    # Валидация video_url: обязательный string
    video_url = normalized_input.get('video_url')
    if not video_url:
        return False, "Поле 'video_url' обязательно для генерации видео. Укажите URL входного видео"
    
    if not isinstance(video_url, str):
        video_url = str(video_url)
    
    video_url = video_url.strip()
    if not video_url:
        return False, "Поле 'video_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not video_url.startswith(('http://', 'https://')):
        return False, "Поле 'video_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['video_url'] = video_url
    
    # Валидация image_url: обязательный string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL входного изображения"
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if not image_url:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not image_url.startswith(('http://', 'https://')):
        return False, "Поле 'image_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['image_url'] = image_url
    
    # ВАЖНО: Удаляем video_urls если он был передан (для этой модели нужен только video_url как string!)
    if 'video_urls' in normalized_input:
        logger.warning(f"Parameter 'video_urls' is not supported for wan/2-2-animate-replace (use 'video_url' as string), removing it")
        del normalized_input['video_urls']
    
    # Валидация resolution: опциональный, "480p" | "580p" | "720p", default "480p"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_wan_2_2_animate_move(resolution)  # Переиспользуем функцию (те же значения)
        if normalized_resolution is None:
            valid_values = ["480p", "580p", "720p"]
            return False, f"Поле 'resolution' должно быть одним из: {', '.join(valid_values)} (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _validate_wan_2_2_animate_move(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-2-animate-move согласно документации API.
    
    ВАЖНО: Эта модель требует и video_url, и image_url (оба обязательны)!
    Это уникальная модель, которая анимирует изображение на основе движения из видео.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["wan/2-2-animate-move", "wan/2.2-animate-move"]:
        return True, None
    
    # Валидация video_url: обязательный string
    video_url = normalized_input.get('video_url')
    if not video_url:
        return False, "Поле 'video_url' обязательно для генерации видео. Укажите URL входного видео"
    
    if not isinstance(video_url, str):
        video_url = str(video_url)
    
    video_url = video_url.strip()
    if not video_url:
        return False, "Поле 'video_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not video_url.startswith(('http://', 'https://')):
        return False, "Поле 'video_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['video_url'] = video_url
    
    # Валидация image_url: обязательный string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL входного изображения"
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if not image_url:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not image_url.startswith(('http://', 'https://')):
        return False, "Поле 'image_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['image_url'] = image_url
    
    # ВАЖНО: Удаляем video_urls если он был передан (для этой модели нужен только video_url как string!)
    if 'video_urls' in normalized_input:
        logger.warning(f"Parameter 'video_urls' is not supported for wan/2-2-animate-move (use 'video_url' as string), removing it")
        del normalized_input['video_urls']
    
    # Валидация resolution: опциональный, "480p" | "580p" | "720p", default "480p"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_wan_2_2_animate_move(resolution)
        if normalized_resolution is None:
            valid_values = ["480p", "580p", "720p"]
            return False, f"Поле 'resolution' должно быть одним из: {', '.join(valid_values)} (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _validate_wan_2_6_video_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-6-video-to-video согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "wan/2-6-video-to-video":
        return True, None
    
    # Валидация prompt: обязательный, 2-5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len < 2:
        return False, "Поле 'prompt' должно содержать минимум 2 символа"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация video_urls: обязательный массив
    # Проверяем различные варианты имени поля
    video_urls = None
    if 'video_urls' in normalized_input:
        video_urls = normalized_input['video_urls']
    elif 'video_url' in normalized_input:
        # Конвертируем video_url в video_urls
        video_urls = normalized_input['video_url']
    elif 'video' in normalized_input:
        video_urls = normalized_input['video']
    
    if not video_urls:
        return False, "Поле 'video_urls' обязательно для генерации видео из видео"
    
    # Нормализуем video_urls
    normalized_video_urls = _normalize_video_urls_for_wan_2_6(video_urls)
    if not normalized_video_urls:
        return False, "Поле 'video_urls' должно содержать хотя бы один валидный URL видео"
    
    # Проверяем что все URL начинаются с http:// или https://
    for idx, url in enumerate(normalized_video_urls):
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, f"URL видео #{idx + 1} должен начинаться с http:// или https://"
    
    # Сохраняем нормализованное значение
    normalized_input['video_urls'] = normalized_video_urls
    
    # Валидация duration: опциональный, "5" | "10" (НЕ "15"!), default "5"
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_wan_2_6_v2v(duration)
        if normalized_duration is None:
            return False, f"Поле 'duration' должно быть '5' или '10' (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация resolution: опциональный, "720p" | "1080p", default "1080p"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_wan_2_6(resolution)
        if normalized_resolution is None:
            return False, f"Поле 'resolution' должно быть '720p' или '1080p' (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _normalize_aspect_ratio_for_seedream_4_5(value: Any) -> Optional[str]:
    """
    Нормализует aspect_ratio для seedream/4.5-text-to-image.
    Принимает строки и возвращает нормализованную строку.
    
    Args:
        value: Значение aspect_ratio
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    str_value = str(value).strip()
    
    # Валидные значения
    valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
    if str_value in valid_values:
        return str_value
    
    return None


def _normalize_quality_for_seedream_4_5(value: Any) -> Optional[str]:
    """
    Нормализует quality для seedream/4.5-text-to-image.
    Принимает строки и возвращает нормализованную строку в нижнем регистре.
    
    Args:
        value: Значение quality
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    str_value = str(value).strip().lower()
    
    # Валидные значения
    valid_values = ["basic", "high"]
    if str_value in valid_values:
        return str_value
    
    return None


def _validate_seedream_4_5_text_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для seedream/4.5-text-to-image согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "seedream/4.5-text-to-image":
        return True, None
    
    # Валидация prompt: обязательный, максимум 3000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 3000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 3000)"
    
    # Валидация aspect_ratio: обязательный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if not aspect_ratio:
        return False, "Поле 'aspect_ratio' обязательно для генерации изображения"
    
    normalized_aspect_ratio = _normalize_aspect_ratio_for_seedream_4_5(aspect_ratio)
    if normalized_aspect_ratio is None:
        valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
        return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
    normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация quality: обязательный, enum
    quality = normalized_input.get('quality')
    if not quality:
        return False, "Поле 'quality' обязательно для генерации изображения"
    
    normalized_quality = _normalize_quality_for_seedream_4_5(quality)
    if normalized_quality is None:
        return False, f"Поле 'quality' должно быть 'basic' или 'high' (получено: {quality})"
    normalized_input['quality'] = normalized_quality
    
    return True, None


def _validate_seedream_4_5_edit(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для seedream/4.5-edit согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "seedream/4.5-edit":
        return True, None
    
    # Валидация prompt: обязательный, максимум 3000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для редактирования изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 3000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 3000)"
    
    # Валидация image_urls: обязательный массив
    # Проверяем различные варианты имени поля
    image_urls = None
    if 'image_urls' in normalized_input:
        image_urls = normalized_input['image_urls']
    elif 'image_url' in normalized_input:
        # Конвертируем image_url в image_urls
        image_urls = normalized_input['image_url']
    elif 'image' in normalized_input:
        image_urls = normalized_input['image']
    
    if not image_urls:
        return False, "Поле 'image_urls' обязательно для редактирования изображения"
    
    # Нормализуем image_urls
    normalized_image_urls = _normalize_image_urls_for_wan_2_6(image_urls)  # Используем ту же функцию
    if not normalized_image_urls:
        return False, "Поле 'image_urls' должно содержать хотя бы один валидный URL изображения"
    
    # Проверяем что все URL начинаются с http:// или https://
    for idx, url in enumerate(normalized_image_urls):
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, f"URL изображения #{idx + 1} должен начинаться с http:// или https://"
    
    # Сохраняем нормализованное значение
    normalized_input['image_urls'] = normalized_image_urls
    
    # Валидация aspect_ratio: обязательный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if not aspect_ratio:
        return False, "Поле 'aspect_ratio' обязательно для редактирования изображения"
    
    normalized_aspect_ratio = _normalize_aspect_ratio_for_seedream_4_5(aspect_ratio)
    if normalized_aspect_ratio is None:
        valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
        return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
    normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация quality: обязательный, enum
    quality = normalized_input.get('quality')
    if not quality:
        return False, "Поле 'quality' обязательно для редактирования изображения"
    
    normalized_quality = _normalize_quality_for_seedream_4_5(quality)
    if normalized_quality is None:
        return False, f"Поле 'quality' должно быть 'basic' или 'high' (получено: {quality})"
    normalized_input['quality'] = normalized_quality
    
    return True, None


def _normalize_sound_for_kling_2_6(value: Any) -> Optional[bool]:
    """
    Нормализует sound для kling-2.6/image-to-video.
    Принимает boolean, строку или число и возвращает boolean.
    
    Args:
        value: Значение sound (может быть bool, str, int, None)
    
    Returns:
        Нормализованный boolean или None
    """
    if value is None:
        return None
    
    # Если это уже boolean, возвращаем как есть
    if isinstance(value, bool):
        return value
    
    # Если это строка, конвертируем в boolean
    if isinstance(value, str):
        str_value = str(value).strip().lower()
        if str_value in ['true', '1', 'yes', 'on']:
            return True
        elif str_value in ['false', '0', 'no', 'off']:
            return False
    
    # Если это число, конвертируем в boolean
    if isinstance(value, (int, float)):
        return bool(value)
    
    return None


def _normalize_duration_for_kling_2_6(value: Any) -> Optional[str]:
    """
    Нормализует duration для kling-2.6/image-to-video.
    Принимает числа (5, 10) или строки ("5", "10") и возвращает строку.
    ВАЖНО: Для kling-2.6 поддерживаются только "5" и "10"!
    
    Args:
        value: Значение duration (может быть int, float, str)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Убираем "s" или "seconds" в конце, если есть
    if str_value.lower().endswith('seconds'):
        str_value = str_value[:-7].strip()
    elif str_value.lower().endswith('s'):
        str_value = str_value[:-1].strip()
    
    # Проверяем что это валидное значение (только 5 и 10 для kling-2.6!)
    valid_values = ["5", "10"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем конвертировать число в строку
    try:
        num_value = float(str_value)
        if num_value == 5.0 or num_value == 5:
            return "5"
        elif num_value == 10.0 or num_value == 10:
            return "10"
    except (ValueError, TypeError):
        pass
    
    return None


def _validate_kling_2_6_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling-2.6/image-to-video согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "kling-2.6/image-to-video":
        return True, None
    
    # Валидация prompt: обязательный, максимум 1000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 1000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 1000)"
    
    # Валидация image_urls: обязательный массив
    # Проверяем различные варианты имени поля
    image_urls = None
    if 'image_urls' in normalized_input:
        image_urls = normalized_input['image_urls']
    elif 'image_url' in normalized_input:
        # Конвертируем image_url в image_urls
        image_urls = normalized_input['image_url']
    elif 'image' in normalized_input:
        image_urls = normalized_input['image']
    
    if not image_urls:
        return False, "Поле 'image_urls' обязательно для генерации видео из изображения"
    
    # Нормализуем image_urls
    normalized_image_urls = _normalize_image_urls_for_wan_2_6(image_urls)  # Используем ту же функцию
    if not normalized_image_urls:
        return False, "Поле 'image_urls' должно содержать хотя бы один валидный URL изображения"
    
    # Проверяем что все URL начинаются с http:// или https://
    for idx, url in enumerate(normalized_image_urls):
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, f"URL изображения #{idx + 1} должен начинаться с http:// или https://"
    
    # Сохраняем нормализованное значение
    normalized_input['image_urls'] = normalized_image_urls
    
    # Валидация sound: обязательный boolean
    sound = normalized_input.get('sound')
    if sound is None:
        return False, "Поле 'sound' обязательно для генерации видео"
    
    normalized_sound = _normalize_sound_for_kling_2_6(sound)
    if normalized_sound is None:
        return False, f"Поле 'sound' должно быть boolean (true/false) (получено: {sound})"
    normalized_input['sound'] = normalized_sound
    
    # Валидация duration: обязательный, "5" | "10", default "5"
    duration = normalized_input.get('duration')
    if not duration:
        return False, "Поле 'duration' обязательно для генерации видео"
    
    normalized_duration = _normalize_duration_for_kling_2_6(duration)
    if normalized_duration is None:
        return False, f"Поле 'duration' должно быть '5' или '10' (получено: {duration})"
    normalized_input['duration'] = normalized_duration
    
    return True, None


def _normalize_aspect_ratio_for_kling_2_6(value: Any) -> Optional[str]:
    """
    Нормализует aspect_ratio для kling-2.6/text-to-video.
    Принимает строку и возвращает нормализованное значение.
    ВАЖНО: Для kling-2.6 поддерживаются только "1:1", "16:9", "9:16"!
    
    Args:
        value: Значение aspect_ratio (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение (только 3 значения для kling-2.6!)
    valid_values = ["1:1", "16:9", "9:16"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["1:1", "1/1", "1x1", "square"]:
        return "1:1"
    elif str_lower in ["16:9", "16/9", "16x9", "landscape", "wide"]:
        return "16:9"
    elif str_lower in ["9:16", "9/16", "9x16", "portrait", "vertical"]:
        return "9:16"
    
    return None


def _validate_kling_2_6_text_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling-2.6/text-to-video согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "kling-2.6/text-to-video":
        return True, None
    
    # Валидация prompt: обязательный, максимум 1000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 1000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 1000)"
    
    # Валидация sound: обязательный boolean
    sound = normalized_input.get('sound')
    if sound is None:
        return False, "Поле 'sound' обязательно для генерации видео"
    
    normalized_sound = _normalize_sound_for_kling_2_6(sound)
    if normalized_sound is None:
        return False, f"Поле 'sound' должно быть boolean (true/false) (получено: {sound})"
    normalized_input['sound'] = normalized_sound
    
    # Валидация aspect_ratio: обязательный, "1:1" | "16:9" | "9:16"
    aspect_ratio = normalized_input.get('aspect_ratio')
    if not aspect_ratio:
        return False, "Поле 'aspect_ratio' обязательно для генерации видео"
    
    normalized_aspect_ratio = _normalize_aspect_ratio_for_kling_2_6(aspect_ratio)
    if normalized_aspect_ratio is None:
        valid_values = ["1:1", "16:9", "9:16"]
        return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
    normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация duration: обязательный, "5" | "10", default "5"
    duration = normalized_input.get('duration')
    if not duration:
        return False, "Поле 'duration' обязательно для генерации видео"
    
    normalized_duration = _normalize_duration_for_kling_2_6(duration)
    if normalized_duration is None:
        return False, f"Поле 'duration' должно быть '5' или '10' (получено: {duration})"
    normalized_input['duration'] = normalized_duration
    
    return True, None


def _normalize_aspect_ratio_for_z_image(value: Any) -> Optional[str]:
    """
    Нормализует aspect_ratio для z-image.
    Принимает строку и возвращает нормализованное значение.
    ВАЖНО: Для z-image поддерживаются только "1:1", "4:3", "3:4", "16:9", "9:16" (5 значений)!
    
    Args:
        value: Значение aspect_ratio (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение (только 5 значений для z-image!)
    valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["1:1", "1/1", "1x1", "square"]:
        return "1:1"
    elif str_lower in ["4:3", "4/3", "4x3"]:
        return "4:3"
    elif str_lower in ["3:4", "3/4", "3x4"]:
        return "3:4"
    elif str_lower in ["16:9", "16/9", "16x9", "landscape", "wide"]:
        return "16:9"
    elif str_lower in ["9:16", "9/16", "9x16", "portrait", "vertical"]:
        return "9:16"
    
    return None


def _validate_z_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для z-image согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "z-image":
        return True, None
    
    # Валидация prompt: обязательный, максимум 1000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 1000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 1000)"
    
    # Валидация aspect_ratio: обязательный, "1:1" | "4:3" | "3:4" | "16:9" | "9:16"
    aspect_ratio = normalized_input.get('aspect_ratio')
    if not aspect_ratio:
        return False, "Поле 'aspect_ratio' обязательно для генерации изображения"
    
    normalized_aspect_ratio = _normalize_aspect_ratio_for_z_image(aspect_ratio)
    if normalized_aspect_ratio is None:
        valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16"]
        return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
    normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    return True, None


def _normalize_input_urls_for_flux_2_pro(value: Any) -> Optional[List[str]]:
    """
    Нормализует input_urls для flux-2/pro-image-to-image.
    Принимает строку, массив строк или None и возвращает массив строк.
    ВАЖНО: Для Flux моделей используется input_urls, а не image_urls!
    
    Args:
        value: Значение input_urls (может быть str, list, None)
    
    Returns:
        Нормализованный массив строк или None
    """
    if value is None:
        return None
    
    # Если это строка, конвертируем в массив
    if isinstance(value, str):
        if value.strip():
            return [value.strip()]
        return None
    
    # Если это массив, проверяем и нормализуем элементы
    if isinstance(value, list):
        normalized = []
        for item in value:
            if isinstance(item, str) and item.strip():
                normalized.append(item.strip())
        return normalized if normalized else None
    
    return None


def _normalize_aspect_ratio_for_flux_2_pro(value: Any) -> Optional[str]:
    """
    Нормализует aspect_ratio для flux-2/pro-image-to-image.
    Принимает строку и возвращает нормализованное значение.
    ВАЖНО: Для flux-2/pro поддерживаются "1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"!
    
    Args:
        value: Значение aspect_ratio (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Извлекаем только соотношение сторон, если есть дополнительные символы (например, "1:1 (Square)")
    if ' ' in str_value:
        str_value = str_value.split()[0].strip()
    
    # Проверяем что это валидное значение
    valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["1:1", "1/1", "1x1", "square"]:
        return "1:1"
    elif str_lower in ["4:3", "4/3", "4x3"]:
        return "4:3"
    elif str_lower in ["3:4", "3/4", "3x4"]:
        return "3:4"
    elif str_lower in ["16:9", "16/9", "16x9", "landscape", "widescreen"]:
        return "16:9"
    elif str_lower in ["9:16", "9/16", "9x16", "portrait", "vertical"]:
        return "9:16"
    elif str_lower in ["3:2", "3/2", "3x2", "classic"]:
        return "3:2"
    elif str_lower in ["2:3", "2/3", "2x3", "classic portrait"]:
        return "2:3"
    elif str_lower == "auto":
        return "auto"
    
    return None


def _normalize_resolution_for_flux_2_pro(value: Any) -> Optional[str]:
    """
    Нормализует resolution для flux-2/pro-image-to-image.
    Принимает строку и возвращает нормализованное значение.
    ВАЖНО: Для flux-2/pro поддерживаются только "1K" и "2K"!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы, конвертируем в верхний регистр
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["1K", "2K"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    if str_value in ["1", "1k", "1000", "1k resolution"]:
        return "1K"
    elif str_value in ["2", "2k", "2000", "2k resolution"]:
        return "2K"
    
    return None


def _validate_flux_2_pro_image_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для flux-2/pro-image-to-image согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "flux-2/pro-image-to-image":
        return True, None
    
    # Валидация input_urls: обязательный массив (1-8 изображений)
    # ВАЖНО: Для Flux моделей используется input_urls, а не image_urls!
    input_urls = None
    if 'input_urls' in normalized_input:
        input_urls = normalized_input['input_urls']
    elif 'image_input' in normalized_input:
        # Конвертируем image_input в input_urls
        input_urls = normalized_input['image_input']
    elif 'image_urls' in normalized_input:
        # Конвертируем image_urls в input_urls
        input_urls = normalized_input['image_urls']
    
    if not input_urls:
        return False, "Поле 'input_urls' обязательно для генерации изображения"
    
    # Нормализуем input_urls
    normalized_input_urls = _normalize_input_urls_for_flux_2_pro(input_urls)
    if not normalized_input_urls:
        return False, "Поле 'input_urls' должно содержать хотя бы один валидный URL изображения"
    
    # Проверяем количество изображений (1-8)
    if len(normalized_input_urls) > 8:
        return False, f"Поле 'input_urls' содержит слишком много изображений: {len(normalized_input_urls)} (максимум 8)"
    
    # Проверяем что все URL начинаются с http:// или https://
    for idx, url in enumerate(normalized_input_urls):
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, f"URL изображения #{idx + 1} должен начинаться с http:// или https://"
    
    # Сохраняем нормализованное значение
    normalized_input['input_urls'] = normalized_input_urls
    
    # Валидация prompt: обязательный, от 3 до 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len < 3:
        return False, f"Поле 'prompt' слишком короткое: {prompt_len} символов (минимум 3)"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация aspect_ratio: обязательный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if not aspect_ratio:
        return False, "Поле 'aspect_ratio' обязательно для генерации изображения"
    
    normalized_aspect_ratio = _normalize_aspect_ratio_for_flux_2_pro(aspect_ratio)
    if normalized_aspect_ratio is None:
        valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"]
        return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
    normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация resolution: обязательный, "1K" | "2K"
    resolution = normalized_input.get('resolution')
    if not resolution:
        return False, "Поле 'resolution' обязательно для генерации изображения"
    
    normalized_resolution = _normalize_resolution_for_flux_2_pro(resolution)
    if normalized_resolution is None:
        return False, f"Поле 'resolution' должно быть '1K' или '2K' (получено: {resolution})"
    normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _validate_flux_2_pro_text_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для flux-2/pro-text-to-image согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "flux-2/pro-text-to-image":
        return True, None
    
    # Валидация prompt: обязательный, от 3 до 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len < 3:
        return False, f"Поле 'prompt' слишком короткое: {prompt_len} символов (минимум 3)"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация aspect_ratio: обязательный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if not aspect_ratio:
        return False, "Поле 'aspect_ratio' обязательно для генерации изображения"
    
    normalized_aspect_ratio = _normalize_aspect_ratio_for_flux_2_pro(aspect_ratio)
    if normalized_aspect_ratio is None:
        valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"]
        return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
    normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация resolution: обязательный, "1K" | "2K"
    resolution = normalized_input.get('resolution')
    if not resolution:
        return False, "Поле 'resolution' обязательно для генерации изображения"
    
    normalized_resolution = _normalize_resolution_for_flux_2_pro(resolution)
    if normalized_resolution is None:
        return False, f"Поле 'resolution' должно быть '1K' или '2K' (получено: {resolution})"
    normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _validate_flux_2_flex_image_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для flux-2/flex-image-to-image согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "flux-2/flex-image-to-image":
        return True, None
    
    # Валидация input_urls: обязательный массив (1-8 изображений)
    # ВАЖНО: Для Flux моделей используется input_urls, а не image_urls!
    input_urls = None
    if 'input_urls' in normalized_input:
        input_urls = normalized_input['input_urls']
    elif 'image_input' in normalized_input:
        # Конвертируем image_input в input_urls
        input_urls = normalized_input['image_input']
    elif 'image_urls' in normalized_input:
        # Конвертируем image_urls в input_urls
        input_urls = normalized_input['image_urls']
    
    if not input_urls:
        return False, "Поле 'input_urls' обязательно для генерации изображения"
    
    # Нормализуем input_urls
    normalized_input_urls = _normalize_input_urls_for_flux_2_pro(input_urls)
    if not normalized_input_urls:
        return False, "Поле 'input_urls' должно содержать хотя бы один валидный URL изображения"
    
    # Проверяем количество изображений (1-8)
    if len(normalized_input_urls) > 8:
        return False, f"Поле 'input_urls' содержит слишком много изображений: {len(normalized_input_urls)} (максимум 8)"
    
    # Проверяем что все URL начинаются с http:// или https://
    for idx, url in enumerate(normalized_input_urls):
        if not (url.startswith('http://') or url.startswith('https://')):
            return False, f"URL изображения #{idx + 1} должен начинаться с http:// или https://"
    
    # Сохраняем нормализованное значение
    normalized_input['input_urls'] = normalized_input_urls
    
    # Валидация prompt: обязательный, от 3 до 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len < 3:
        return False, f"Поле 'prompt' слишком короткое: {prompt_len} символов (минимум 3)"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация aspect_ratio: обязательный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if not aspect_ratio:
        return False, "Поле 'aspect_ratio' обязательно для генерации изображения"
    
    normalized_aspect_ratio = _normalize_aspect_ratio_for_flux_2_pro(aspect_ratio)
    if normalized_aspect_ratio is None:
        valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"]
        return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
    normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация resolution: обязательный, "1K" | "2K"
    resolution = normalized_input.get('resolution')
    if not resolution:
        return False, "Поле 'resolution' обязательно для генерации изображения"
    
    normalized_resolution = _normalize_resolution_for_flux_2_pro(resolution)
    if normalized_resolution is None:
        return False, f"Поле 'resolution' должно быть '1K' или '2K' (получено: {resolution})"
    normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _validate_flux_2_flex_text_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для flux-2/flex-text-to-image согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "flux-2/flex-text-to-image":
        return True, None
    
    # Валидация prompt: обязательный, от 3 до 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len < 3:
        return False, f"Поле 'prompt' слишком короткое: {prompt_len} символов (минимум 3)"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация aspect_ratio: обязательный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if not aspect_ratio:
        return False, "Поле 'aspect_ratio' обязательно для генерации изображения"
    
    normalized_aspect_ratio = _normalize_aspect_ratio_for_flux_2_pro(aspect_ratio)
    if normalized_aspect_ratio is None:
        valid_values = ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "auto"]
        return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
    normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация resolution: обязательный, "1K" | "2K"
    resolution = normalized_input.get('resolution')
    if not resolution:
        return False, "Поле 'resolution' обязательно для генерации изображения"
    
    normalized_resolution = _normalize_resolution_for_flux_2_pro(resolution)
    if normalized_resolution is None:
        return False, f"Поле 'resolution' должно быть '1K' или '2K' (получено: {resolution})"
    normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _normalize_aspect_ratio_for_nano_banana_pro(value: Any) -> Optional[str]:
    """
    Нормализует aspect_ratio для nano-banana-pro.
    Принимает строку и возвращает нормализованное значение.
    ВАЖНО: Для nano-banana-pro поддерживаются 11 значений (включая "auto")!
    
    Args:
        value: Значение aspect_ratio (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Извлекаем только соотношение сторон, если есть дополнительные символы
    if ' ' in str_value:
        str_value = str_value.split()[0].strip()
    
    # Проверяем что это валидное значение
    valid_values = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["1:1", "1/1", "1x1", "square"]:
        return "1:1"
    elif str_lower in ["2:3", "2/3", "2x3"]:
        return "2:3"
    elif str_lower in ["3:2", "3/2", "3x2"]:
        return "3:2"
    elif str_lower in ["3:4", "3/4", "3x4"]:
        return "3:4"
    elif str_lower in ["4:3", "4/3", "4x3"]:
        return "4:3"
    elif str_lower in ["4:5", "4/5", "4x5"]:
        return "4:5"
    elif str_lower in ["5:4", "5/4", "5x4"]:
        return "5:4"
    elif str_lower in ["9:16", "9/16", "9x16", "portrait", "vertical"]:
        return "9:16"
    elif str_lower in ["16:9", "16/9", "16x9", "landscape", "widescreen"]:
        return "16:9"
    elif str_lower in ["21:9", "21/9", "21x9", "ultrawide"]:
        return "21:9"
    elif str_lower == "auto":
        return "auto"
    
    return None


def _normalize_resolution_for_nano_banana_pro(value: Any) -> Optional[str]:
    """
    Нормализует resolution для nano-banana-pro.
    Принимает строку и возвращает нормализованное значение.
    ВАЖНО: Для nano-banana-pro поддерживаются "1K", "2K" и "4K" (3 значения, не 2!)!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы, конвертируем в верхний регистр
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["1K", "2K", "4K"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    if str_value in ["1", "1k", "1000", "1k resolution"]:
        return "1K"
    elif str_value in ["2", "2k", "2000", "2k resolution"]:
        return "2K"
    elif str_value in ["4", "4k", "4000", "4k resolution"]:
        return "4K"
    
    return None


def _normalize_output_format_for_nano_banana_pro(value: Any) -> Optional[str]:
    """
    Нормализует output_format для nano-banana-pro.
    Принимает строку и возвращает нормализованное значение в нижнем регистре.
    ВАЖНО: Для nano-banana-pro поддерживаются только "png" и "jpg"!
    
    Args:
        value: Значение output_format (может быть str)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы, конвертируем в нижний регистр
    str_value = str(value).strip().lower()
    
    # Маппинг jpeg -> jpg
    if str_value == "jpeg":
        str_value = "jpg"
    
    # Проверяем что это валидное значение
    valid_values = ["png", "jpg"]
    if str_value in valid_values:
        return str_value
    
    return None


def _validate_nano_banana_pro(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для nano-banana-pro согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["nano-banana-pro", "google/nano-banana-pro"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация image_input: опциональный массив (до 8 изображений)
    image_input = normalized_input.get('image_input')
    if image_input is not None:
        # Нормализуем image_input (используем функцию для Flux, так как логика похожа)
        normalized_image_input = _normalize_input_urls_for_flux_2_pro(image_input)
        if normalized_image_input is not None:
            # Проверяем количество изображений (до 8)
            if len(normalized_image_input) > 8:
                return False, f"Поле 'image_input' содержит слишком много изображений: {len(normalized_image_input)} (максимум 8)"
            
            # Проверяем что все URL начинаются с http:// или https://
            for idx, url in enumerate(normalized_image_input):
                if not (url.startswith('http://') or url.startswith('https://')):
                    return False, f"URL изображения #{idx + 1} должен начинаться с http:// или https://"
            
            # Сохраняем нормализованное значение
            normalized_input['image_input'] = normalized_image_input
        else:
            # Если image_input пустой или невалидный, устанавливаем пустой массив
            normalized_input['image_input'] = []
    
    # Валидация aspect_ratio: опциональный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        normalized_aspect_ratio = _normalize_aspect_ratio_for_nano_banana_pro(aspect_ratio)
        if normalized_aspect_ratio is None:
            valid_values = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация resolution: опциональный, "1K" | "2K" | "4K"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_nano_banana_pro(resolution)
        if normalized_resolution is None:
            return False, f"Поле 'resolution' должно быть '1K', '2K' или '4K' (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    # Валидация output_format: опциональный, "png" | "jpg"
    output_format = normalized_input.get('output_format')
    if output_format is not None:
        normalized_output_format = _normalize_output_format_for_nano_banana_pro(output_format)
        if normalized_output_format is None:
            return False, f"Поле 'output_format' должно быть 'png' или 'jpg' (получено: {output_format})"
        normalized_input['output_format'] = normalized_output_format
    
    return True, None


def _normalize_resolution_for_v1_pro_fast(value: Any) -> Optional[str]:
    """
    Нормализует resolution для bytedance/v1-pro-fast-image-to-video.
    Принимает строку и возвращает нормализованное значение.
    ВАЖНО: Для v1-pro-fast поддерживаются только "720p" и "1080p" (не "480p"!)!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы, конвертируем в нижний регистр
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["720p", "1080p"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    if str_value in ["720", "720p", "hd"]:
        return "720p"
    elif str_value in ["1080", "1080p", "full hd", "fhd"]:
        return "1080p"
    
    return None


def _normalize_duration_for_v1_pro_fast(value: Any) -> Optional[str]:
    """
    Нормализует duration для bytedance/v1-pro-fast-image-to-video.
    Принимает числа (5, 10) или строки ("5", "10", "5s", "10s") и возвращает строку.
    ВАЖНО: Для v1-pro-fast поддерживаются только "5" и "10"!
    
    Args:
        value: Значение duration (может быть int, float, str)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Убираем "s" или "seconds" в конце, если есть
    if str_value.lower().endswith('seconds'):
        str_value = str_value[:-7].strip()
    elif str_value.lower().endswith('s'):
        str_value = str_value[:-1].strip()
    
    # Проверяем что это валидное значение (только 5 и 10 для v1-pro-fast!)
    valid_values = ["5", "10"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем конвертировать число в строку
    try:
        num_value = float(str_value)
        if num_value == 5.0 or num_value == 5:
            return "5"
        elif num_value == 10.0 or num_value == 10:
            return "10"
    except (ValueError, TypeError):
        pass
    
    return None


def _validate_bytedance_v1_pro_fast_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для bytedance/v1-pro-fast-image-to-video согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 10000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - resolution (опциональный, enum, только 720p/1080p, НЕТ 480p!, default "720p")
    - duration (опциональный, enum, default "5")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["bytedance/v1-pro-fast-image-to-video", "bytedance-v1-pro-fast-image-to-video", "v1-pro-fast-image-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация resolution: опциональный, enum (только 720p/1080p, НЕТ 480p!)
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        valid_resolutions = ["720p", "1080p"]  # ВАЖНО: только 2 значения, НЕТ 480p!
        if resolution not in valid_resolutions:
            return False, f"Поле 'resolution' должно быть одним из: 720p, 1080p (получено: {resolution})"
        normalized_input['resolution'] = resolution
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    return True, None


def _validate_kling_v2_1_master_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling/v2-1-master-image-to-video согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - duration (опциональный, enum, default "5")
    - negative_prompt (опциональный, макс 500 символов, default "blur, distort, and low quality")
    - cfg_scale (опциональный, number, диапазон 0-1, шаг 0.1, default 0.5)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["kling/v2-1-master-image-to-video", "kling-v2-1-master-image-to-video", "v2-1-master-image-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация cfg_scale: опциональный, number, диапазон 0-1, шаг 0.1
    cfg_scale = normalized_input.get('cfg_scale')
    if cfg_scale is not None:
        try:
            cfg_scale_num = float(cfg_scale)
            if cfg_scale_num < 0 or cfg_scale_num > 1:
                return False, f"Поле 'cfg_scale' должно быть в диапазоне от 0 до 1 (получено: {cfg_scale})"
            # Округляем до 1 знака после запятой (шаг 0.1)
            cfg_scale_num = round(cfg_scale_num, 1)
            normalized_input['cfg_scale'] = cfg_scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'cfg_scale' должно быть числом от 0 до 1 (получено: {cfg_scale})"
    
    return True, None


def _validate_kling_v2_1_standard(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling/v2-1-standard согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - duration (опциональный, enum, default "5")
    - negative_prompt (опциональный, макс 500 символов, default "blur, distort, and low quality")
    - cfg_scale (опциональный, number, диапазон 0-1, шаг 0.1, default 0.5)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["kling/v2-1-standard", "kling-v2-1-standard", "v2-1-standard"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация cfg_scale: опциональный, number, диапазон 0-1, шаг 0.1
    cfg_scale = normalized_input.get('cfg_scale')
    if cfg_scale is not None:
        try:
            cfg_scale_num = float(cfg_scale)
            if cfg_scale_num < 0 or cfg_scale_num > 1:
                return False, f"Поле 'cfg_scale' должно быть в диапазоне от 0 до 1 (получено: {cfg_scale})"
            # Округляем до 1 знака после запятой (шаг 0.1)
            cfg_scale_num = round(cfg_scale_num, 1)
            normalized_input['cfg_scale'] = cfg_scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'cfg_scale' должно быть числом от 0 до 1 (получено: {cfg_scale})"
    
    return True, None


def _validate_kling_v2_1_pro(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling/v2-1-pro согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - duration (опциональный, enum, default "5")
    - negative_prompt (опциональный, макс 500 символов, default "blur, distort, and low quality")
    - cfg_scale (опциональный, number, диапазон 0-1, шаг 0.1, default 0.5)
    - tail_image_url (опциональный, макс 10MB, jpeg/png/webp, default "")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["kling/v2-1-pro", "kling-v2-1-pro", "v2-1-pro"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация cfg_scale: опциональный, number, диапазон 0-1, шаг 0.1
    cfg_scale = normalized_input.get('cfg_scale')
    if cfg_scale is not None:
        try:
            cfg_scale_num = float(cfg_scale)
            if cfg_scale_num < 0 or cfg_scale_num > 1:
                return False, f"Поле 'cfg_scale' должно быть в диапазоне от 0 до 1 (получено: {cfg_scale})"
            # Округляем до 1 знака после запятой (шаг 0.1)
            cfg_scale_num = round(cfg_scale_num, 1)
            normalized_input['cfg_scale'] = cfg_scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'cfg_scale' должно быть числом от 0 до 1 (получено: {cfg_scale})"
    
    # Валидация tail_image_url: опциональный, string
    tail_image_url = normalized_input.get('tail_image_url')
    if tail_image_url is not None:
        if not isinstance(tail_image_url, str):
            tail_image_url = str(tail_image_url)
        tail_image_url = tail_image_url.strip()
        # Если пустая строка, оставляем как есть (default "")
        if len(tail_image_url) > 0:
            # Проверяем что это валидный URL (если не пустой)
            normalized_input['tail_image_url'] = tail_image_url
        else:
            normalized_input['tail_image_url'] = ""  # Default пустая строка
    
    return True, None


def _validate_kling_v2_1_master_text_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling/v2-1-master-text-to-video согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - duration (опциональный, enum, default "5")
    - aspect_ratio (опциональный, enum, default "16:9")
    - negative_prompt (опциональный, макс 500 символов, default "blur, distort, and low quality")
    - cfg_scale (опциональный, number, диапазон 0-1, шаг 0.1, default 0.5)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["kling/v2-1-master-text-to-video", "kling-v2-1-master-text-to-video", "v2-1-master-text-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    # Валидация aspect_ratio: опциональный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        valid_aspect_ratios = ["16:9", "9:16", "1:1"]
        if aspect_ratio not in valid_aspect_ratios:
            return False, f"Поле 'aspect_ratio' должно быть одним из: 16:9, 9:16, 1:1 (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = aspect_ratio
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация cfg_scale: опциональный, number, диапазон 0-1, шаг 0.1
    cfg_scale = normalized_input.get('cfg_scale')
    if cfg_scale is not None:
        try:
            cfg_scale_num = float(cfg_scale)
            if cfg_scale_num < 0 or cfg_scale_num > 1:
                return False, f"Поле 'cfg_scale' должно быть в диапазоне от 0 до 1 (получено: {cfg_scale})"
            # Округляем до 1 знака после запятой (шаг 0.1)
            cfg_scale_num = round(cfg_scale_num, 1)
            normalized_input['cfg_scale'] = cfg_scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'cfg_scale' должно быть числом от 0 до 1 (получено: {cfg_scale})"
    
    return True, None


def _validate_ideogram_v3_text_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для ideogram/v3-text-to-image согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - rendering_speed (опциональный, enum, default "BALANCED")
    - style (опциональный, enum, default "AUTO")
    - expand_prompt (опциональный, boolean, default true)
    - image_size (опциональный, enum, default "square_hd")
    - seed (опциональный, number)
    - negative_prompt (опциональный, string, макс 5000 символов, default "")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["ideogram/v3-text-to-image", "ideogram-v3-text-to-image", "ideogram/v3-t2i", "v3-text-to-image"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация rendering_speed: опциональный, enum
    rendering_speed = normalized_input.get('rendering_speed')
    if rendering_speed is not None:
        # Переиспользуем функцию из ideogram/character-edit
        normalized_speed = _normalize_rendering_speed_for_ideogram_character_edit(rendering_speed)
        if normalized_speed is None:
            valid_values = ["TURBO", "BALANCED", "QUALITY"]
            return False, f"Поле 'rendering_speed' должно быть одним из: {', '.join(valid_values)} (получено: {rendering_speed})"
        normalized_input['rendering_speed'] = normalized_speed
    
    # Валидация style: опциональный, enum
    style = normalized_input.get('style')
    if style is not None:
        # Переиспользуем функцию из ideogram/character-edit
        normalized_style = _normalize_style_for_ideogram_character_edit(style)
        if normalized_style is None:
            valid_values = ["AUTO", "GENERAL", "REALISTIC", "DESIGN"]
            return False, f"Поле 'style' должно быть одним из: {', '.join(valid_values)} (получено: {style})"
        normalized_input['style'] = normalized_style
    
    # Валидация expand_prompt: опциональный, boolean
    expand_prompt = normalized_input.get('expand_prompt')
    if expand_prompt is not None:
        normalized_bool = _normalize_boolean(expand_prompt)
        if normalized_bool is None:
            return False, f"Поле 'expand_prompt' должно быть boolean (получено: {expand_prompt})"
        normalized_input['expand_prompt'] = normalized_bool
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        # Переиспользуем функцию из qwen/image-edit
        normalized_size = _normalize_image_size_for_qwen_image_edit(image_size)
        if normalized_size is None:
            valid_values = [
                "square", "square_hd",
                "portrait_4_3", "portrait_16_9",
                "landscape_4_3", "landscape_16_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = float(seed)
            # Преобразуем в int если это целое число
            if seed_num == int(seed_num):
                normalized_input['seed'] = int(seed_num)
            else:
                normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация negative_prompt: опциональный, string, макс 5000 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 5000:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 5000)"
        normalized_input['negative_prompt'] = negative_prompt
    
    return True, None


def _validate_ideogram_v3_edit(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для ideogram/v3-edit согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - mask_url (обязательный, макс 10MB, jpeg/png/webp) - уникальный параметр для inpainting!
    - rendering_speed (опциональный, enum, default "BALANCED")
    - expand_prompt (опциональный, boolean, default true)
    - seed (опциональный, number)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["ideogram/v3-edit", "ideogram-v3-edit", "ideogram/v3-edit", "v3-edit"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для редактирования изображения. Введите текстовое описание для заполнения замаскированной части изображения."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для редактирования изображения. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация mask_url: обязательный, string - уникальный параметр для inpainting!
    mask_url = normalized_input.get('mask_url')
    if not mask_url:
        return False, "Поле 'mask_url' обязательно для редактирования изображения. Укажите URL маски для инпейнтинга."
    
    if not isinstance(mask_url, str):
        mask_url = str(mask_url)
    
    mask_url = mask_url.strip()
    if len(mask_url) == 0:
        return False, "Поле 'mask_url' не может быть пустым"
    
    # Валидация rendering_speed: опциональный, enum
    rendering_speed = normalized_input.get('rendering_speed')
    if rendering_speed is not None:
        # Переиспользуем функцию из ideogram/character-edit
        normalized_speed = _normalize_rendering_speed_for_ideogram_character_edit(rendering_speed)
        if normalized_speed is None:
            valid_values = ["TURBO", "BALANCED", "QUALITY"]
            return False, f"Поле 'rendering_speed' должно быть одним из: {', '.join(valid_values)} (получено: {rendering_speed})"
        normalized_input['rendering_speed'] = normalized_speed
    
    # Валидация expand_prompt: опциональный, boolean
    expand_prompt = normalized_input.get('expand_prompt')
    if expand_prompt is not None:
        normalized_bool = _normalize_boolean(expand_prompt)
        if normalized_bool is None:
            return False, f"Поле 'expand_prompt' должно быть boolean (получено: {expand_prompt})"
        normalized_input['expand_prompt'] = normalized_bool
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = float(seed)
            # Преобразуем в int если это целое число
            if seed_num == int(seed_num):
                normalized_input['seed'] = int(seed_num)
            else:
                normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    return True, None


def _validate_ideogram_v3_remix(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для ideogram/v3-remix согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - rendering_speed (опциональный, enum, default "BALANCED")
    - style (опциональный, enum, default "AUTO")
    - expand_prompt (опциональный, boolean, default true)
    - image_size (опциональный, enum, default "square_hd")
    - num_images (опциональный, string enum, default "1")
    - seed (опциональный, number)
    - strength (опциональный, number, диапазон 0.01-1, шаг 0.01, default 0.8)
    - negative_prompt (опциональный, string, макс 5000 символов, default "")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["ideogram/v3-remix", "ideogram-v3-remix", "ideogram/v3-remix", "v3-remix"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для ремикса изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для ремикса изображения. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация rendering_speed: опциональный, enum
    rendering_speed = normalized_input.get('rendering_speed')
    if rendering_speed is not None:
        # Переиспользуем функцию из ideogram/character-edit
        normalized_speed = _normalize_rendering_speed_for_ideogram_character_edit(rendering_speed)
        if normalized_speed is None:
            valid_values = ["TURBO", "BALANCED", "QUALITY"]
            return False, f"Поле 'rendering_speed' должно быть одним из: {', '.join(valid_values)} (получено: {rendering_speed})"
        normalized_input['rendering_speed'] = normalized_speed
    
    # Валидация style: опциональный, enum
    style = normalized_input.get('style')
    if style is not None:
        # Переиспользуем функцию из ideogram/character-edit
        normalized_style = _normalize_style_for_ideogram_character_edit(style)
        if normalized_style is None:
            valid_values = ["AUTO", "GENERAL", "REALISTIC", "DESIGN"]
            return False, f"Поле 'style' должно быть одним из: {', '.join(valid_values)} (получено: {style})"
        normalized_input['style'] = normalized_style
    
    # Валидация expand_prompt: опциональный, boolean
    expand_prompt = normalized_input.get('expand_prompt')
    if expand_prompt is not None:
        normalized_bool = _normalize_boolean(expand_prompt)
        if normalized_bool is None:
            return False, f"Поле 'expand_prompt' должно быть boolean (получено: {expand_prompt})"
        normalized_input['expand_prompt'] = normalized_bool
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        # Переиспользуем функцию из qwen/image-edit
        normalized_size = _normalize_image_size_for_qwen_image_edit(image_size)
        if normalized_size is None:
            valid_values = [
                "square", "square_hd",
                "portrait_4_3", "portrait_16_9",
                "landscape_4_3", "landscape_16_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация num_images: опциональный, string enum
    num_images = normalized_input.get('num_images')
    if num_images is not None:
        # Переиспользуем функцию из qwen/image-edit
        normalized_num = _normalize_num_images_for_qwen_image_edit(num_images)
        if normalized_num is None:
            valid_values = ["1", "2", "3", "4"]
            return False, f"Поле 'num_images' должно быть одним из: {', '.join(valid_values)} (получено: {num_images})"
        normalized_input['num_images'] = normalized_num
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = float(seed)
            # Преобразуем в int если это целое число
            if seed_num == int(seed_num):
                normalized_input['seed'] = int(seed_num)
            else:
                normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация strength: опциональный, number, диапазон 0.01-1, шаг 0.01
    strength = normalized_input.get('strength')
    if strength is not None:
        try:
            strength_num = float(strength)
            if strength_num < 0.01 or strength_num > 1:
                return False, f"Поле 'strength' должно быть в диапазоне от 0.01 до 1 (получено: {strength})"
            # Округляем до 2 знаков после запятой (шаг 0.01)
            strength_num = round(strength_num, 2)
            normalized_input['strength'] = strength_num
        except (ValueError, TypeError):
            return False, f"Поле 'strength' должно быть числом от 0.01 до 1 (получено: {strength})"
    
    # Валидация negative_prompt: опциональный, string, макс 5000 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 5000:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 5000)"
        normalized_input['negative_prompt'] = negative_prompt
    
    return True, None


def _validate_wan_2_2_a14b_text_to_video_turbo(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-2-a14b-text-to-video-turbo согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - resolution (опциональный, enum, default "720p")
    - aspect_ratio (опциональный, enum, default "16:9")
    - enable_prompt_expansion (опциональный, boolean, default false)
    - seed (опциональный, number, диапазон 0-2147483647, default 0)
    - acceleration (опциональный, enum, default "none")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["wan/2-2-a14b-text-to-video-turbo", "wan-2-2-a14b-text-to-video-turbo", "wan/2-2-a14b-t2v-turbo", "2-2-a14b-text-to-video-turbo"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация resolution: опциональный, enum
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        valid_resolutions = ["480p", "580p", "720p"]
        if resolution not in valid_resolutions:
            return False, f"Поле 'resolution' должно быть одним из: 480p, 580p, 720p (получено: {resolution})"
        normalized_input['resolution'] = resolution
    
    # Валидация aspect_ratio: опциональный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        valid_aspect_ratios = ["16:9", "9:16", "1:1"]
        if aspect_ratio not in valid_aspect_ratios:
            return False, f"Поле 'aspect_ratio' должно быть одним из: 16:9, 9:16, 1:1 (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = aspect_ratio
    
    # Валидация enable_prompt_expansion: опциональный, boolean
    enable_prompt_expansion = normalized_input.get('enable_prompt_expansion')
    if enable_prompt_expansion is not None:
        normalized_bool = _normalize_boolean(enable_prompt_expansion)
        if normalized_bool is None:
            return False, f"Поле 'enable_prompt_expansion' должно быть boolean (получено: {enable_prompt_expansion})"
        normalized_input['enable_prompt_expansion'] = normalized_bool
    
    # Валидация seed: опциональный, number, диапазон 0-2147483647
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = float(seed)
            # Преобразуем в int если это целое число
            if seed_num == int(seed_num):
                seed_int = int(seed_num)
                if seed_int < 0 or seed_int > 2147483647:
                    return False, f"Поле 'seed' должно быть в диапазоне от 0 до 2147483647 (получено: {seed})"
                normalized_input['seed'] = seed_int
            else:
                return False, f"Поле 'seed' должно быть целым числом от 0 до 2147483647 (получено: {seed})"
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом от 0 до 2147483647 (получено: {seed})"
    
    # Валидация acceleration: опциональный, enum
    acceleration = normalized_input.get('acceleration')
    if acceleration is not None:
        valid_accelerations = ["none", "regular"]
        if acceleration not in valid_accelerations:
            return False, f"Поле 'acceleration' должно быть одним из: none, regular (получено: {acceleration})"
        normalized_input['acceleration'] = acceleration
    
    return True, None


def _validate_wan_2_2_a14b_image_to_video_turbo(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-2-a14b-image-to-video-turbo согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - prompt (обязательный, макс 5000 символов)
    - resolution (опциональный, enum, default "720p")
    - aspect_ratio (опциональный, enum, default "auto")
    - enable_prompt_expansion (опциональный, boolean, default false)
    - seed (опциональный, number, диапазон 0-2147483647, default 0)
    - acceleration (опциональный, enum, default "none")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["wan/2-2-a14b-image-to-video-turbo", "wan-2-2-a14b-image-to-video-turbo", "wan/2-2-a14b-i2v-turbo", "2-2-a14b-image-to-video-turbo"]:
        return True, None
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео из изображения. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация resolution: опциональный, enum
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        valid_resolutions = ["480p", "580p", "720p"]
        if resolution not in valid_resolutions:
            return False, f"Поле 'resolution' должно быть одним из: 480p, 580p, 720p (получено: {resolution})"
        normalized_input['resolution'] = resolution
    
    # Валидация aspect_ratio: опциональный, enum (ВАЖНО: включает "auto"!)
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        valid_aspect_ratios = ["auto", "16:9", "9:16", "1:1"]
        if aspect_ratio not in valid_aspect_ratios:
            return False, f"Поле 'aspect_ratio' должно быть одним из: auto, 16:9, 9:16, 1:1 (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = aspect_ratio
    
    # Валидация enable_prompt_expansion: опциональный, boolean
    enable_prompt_expansion = normalized_input.get('enable_prompt_expansion')
    if enable_prompt_expansion is not None:
        normalized_bool = _normalize_boolean(enable_prompt_expansion)
        if normalized_bool is None:
            return False, f"Поле 'enable_prompt_expansion' должно быть boolean (получено: {enable_prompt_expansion})"
        normalized_input['enable_prompt_expansion'] = normalized_bool
    
    # Валидация seed: опциональный, number, диапазон 0-2147483647
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = float(seed)
            # Преобразуем в int если это целое число
            if seed_num == int(seed_num):
                seed_int = int(seed_num)
                if seed_int < 0 or seed_int > 2147483647:
                    return False, f"Поле 'seed' должно быть в диапазоне от 0 до 2147483647 (получено: {seed})"
                normalized_input['seed'] = seed_int
            else:
                return False, f"Поле 'seed' должно быть целым числом от 0 до 2147483647 (получено: {seed})"
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом от 0 до 2147483647 (получено: {seed})"
    
    # Валидация acceleration: опциональный, enum
    acceleration = normalized_input.get('acceleration')
    if acceleration is not None:
        valid_accelerations = ["none", "regular"]
        if acceleration not in valid_accelerations:
            return False, f"Поле 'acceleration' должно быть одним из: none, regular (получено: {acceleration})"
        normalized_input['acceleration'] = acceleration
    
    return True, None


def _validate_google_imagen4_fast(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для google/imagen4-fast согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - negative_prompt (опциональный, макс 5000 символов, default "")
    - aspect_ratio (опциональный, enum, default "16:9")
    - num_images (опциональный, string enum, default "1")
    - seed (опциональный, number)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["google/imagen4-fast", "google-imagen4-fast", "imagen4-fast", "imagen4/fast"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация negative_prompt: опциональный, максимум 5000 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 5000:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 5000)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация aspect_ratio: опциональный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        valid_aspect_ratios = ["1:1", "16:9", "9:16", "3:4", "4:3"]
        if aspect_ratio not in valid_aspect_ratios:
            return False, f"Поле 'aspect_ratio' должно быть одним из: 1:1, 16:9, 9:16, 3:4, 4:3 (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = aspect_ratio
    
    # Валидация num_images: опциональный, string enum
    num_images = normalized_input.get('num_images')
    if num_images is not None:
        # Переиспользуем функцию из qwen/image-edit
        normalized_num = _normalize_num_images_for_qwen_image_edit(num_images)
        if normalized_num is None:
            valid_values = ["1", "2", "3", "4"]
            return False, f"Поле 'num_images' должно быть одним из: {', '.join(valid_values)} (получено: {num_images})"
        normalized_input['num_images'] = normalized_num
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = float(seed)
            # Преобразуем в int если это целое число
            if seed_num == int(seed_num):
                normalized_input['seed'] = int(seed_num)
            else:
                normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    return True, None


def _validate_google_imagen4_ultra(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для google/imagen4-ultra согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - negative_prompt (опциональный, макс 5000 символов, default "")
    - aspect_ratio (опциональный, enum, default "1:1")
    - seed (опциональный, string, макс 500 символов, default "")
    
    ВАЖНО: seed здесь - это string, а не number!
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["google/imagen4-ultra", "google-imagen4-ultra", "imagen4-ultra", "imagen4/ultra"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация negative_prompt: опциональный, максимум 5000 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 5000:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 5000)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация aspect_ratio: опциональный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        valid_aspect_ratios = ["1:1", "16:9", "9:16", "3:4", "4:3"]
        if aspect_ratio not in valid_aspect_ratios:
            return False, f"Поле 'aspect_ratio' должно быть одним из: 1:1, 16:9, 9:16, 3:4, 4:3 (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = aspect_ratio
    
    # Валидация seed: опциональный, string, максимум 500 символов
    # ВАЖНО: seed здесь - это string, а не number!
    seed = normalized_input.get('seed')
    if seed is not None:
        if not isinstance(seed, str):
            seed = str(seed)
        seed = seed.strip()
        if len(seed) > 500:
            return False, f"Поле 'seed' слишком длинное: {len(seed)} символов (максимум 500)"
        normalized_input['seed'] = seed
    
    return True, None


def _validate_google_imagen4(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для google/imagen4 согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - negative_prompt (опциональный, макс 5000 символов, default "")
    - aspect_ratio (опциональный, enum, default "1:1")
    - num_images (опциональный, string enum, default "1")
    - seed (опциональный, string, макс 500 символов, default "")
    
    ВАЖНО: seed здесь - это string, а не number!
    ВАЖНО: aspect_ratio default "1:1" (как в ultra, а не "16:9" как в fast)!
    ВАЖНО: есть num_images (как в fast, но не в ultra)!
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["google/imagen4", "google-imagen4", "imagen4"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация negative_prompt: опциональный, максимум 5000 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 5000:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 5000)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация aspect_ratio: опциональный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        valid_aspect_ratios = ["1:1", "16:9", "9:16", "3:4", "4:3"]
        if aspect_ratio not in valid_aspect_ratios:
            return False, f"Поле 'aspect_ratio' должно быть одним из: 1:1, 16:9, 9:16, 3:4, 4:3 (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = aspect_ratio
    
    # Валидация num_images: опциональный, string enum
    num_images = normalized_input.get('num_images')
    if num_images is not None:
        # Переиспользуем функцию из qwen/image-edit
        normalized_num = _normalize_num_images_for_qwen_image_edit(num_images)
        if normalized_num is None:
            valid_values = ["1", "2", "3", "4"]
            return False, f"Поле 'num_images' должно быть одним из: {', '.join(valid_values)} (получено: {num_images})"
        normalized_input['num_images'] = normalized_num
    
    # Валидация seed: опциональный, string, максимум 500 символов
    # ВАЖНО: seed здесь - это string, а не number!
    seed = normalized_input.get('seed')
    if seed is not None:
        if not isinstance(seed, str):
            seed = str(seed)
        seed = seed.strip()
        if len(seed) > 500:
            return False, f"Поле 'seed' слишком длинное: {len(seed)} символов (максимум 500)"
        normalized_input['seed'] = seed
    
    return True, None


def _normalize_mode_for_grok_imagine(value: Any) -> Optional[str]:
    """
    Нормализует mode для grok-imagine/image-to-video.
    Принимает строку и возвращает нормализованное значение в нижнем регистре.
    ВАЖНО: Для grok-imagine поддерживаются только "fun", "normal", "spicy"!
    
    Args:
        value: Значение mode (может быть str)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы, конвертируем в нижний регистр
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["fun", "normal", "spicy"]
    if str_value in valid_values:
        return str_value
    
    return None


def _validate_grok_imagine_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для grok-imagine/image-to-video согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["grok-imagine/image-to-video", "grok/imagine"]:
        return True, None
    
    # ВАЖНО: Все параметры опциональны! Но должны быть валидными если указаны.
    
    # Валидация image_urls: опциональный массив (только одно изображение)
    image_urls = normalized_input.get('image_urls')
    if image_urls is not None:
        # Нормализуем image_urls
        normalized_image_urls = _normalize_image_urls_for_wan_2_6(image_urls)
        if normalized_image_urls is not None:
            # Проверяем количество изображений (только одно!)
            if len(normalized_image_urls) > 1:
                return False, f"Поле 'image_urls' должно содержать только одно изображение (получено: {len(normalized_image_urls)})"
            
            # Проверяем что URL начинается с http:// или https://
            url = normalized_image_urls[0]
            if not (url.startswith('http://') or url.startswith('https://')):
                return False, "URL изображения должен начинаться с http:// или https://"
            
            # Сохраняем нормализованное значение
            normalized_input['image_urls'] = normalized_image_urls
    
    # Валидация task_id: опциональный string (максимум 100 символов)
    task_id = normalized_input.get('task_id')
    if task_id is not None:
        if not isinstance(task_id, str):
            task_id = str(task_id)
        
        task_id = task_id.strip()
        if len(task_id) > 100:
            return False, f"Поле 'task_id' слишком длинное: {len(task_id)} символов (максимум 100)"
        
        normalized_input['task_id'] = task_id
    
    # Валидация index: опциональный number (0-5, 0-based)
    index = normalized_input.get('index')
    if index is not None:
        try:
            index_num = int(index)
            if index_num < 0 or index_num > 5:
                return False, f"Поле 'index' должно быть числом от 0 до 5 (получено: {index})"
            normalized_input['index'] = index_num
        except (ValueError, TypeError):
            return False, f"Поле 'index' должно быть числом от 0 до 5 (получено: {index})"
    
    # Валидация prompt: опциональный string (максимум 5000 символов)
    prompt = normalized_input.get('prompt')
    if prompt is not None:
        if not isinstance(prompt, str):
            prompt = str(prompt)
        
        prompt_len = len(prompt.strip())
        if prompt_len > 5000:
            return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
        
        normalized_input['prompt'] = prompt.strip() if prompt_len > 0 else None
    
    # Валидация mode: опциональный string ("fun", "normal", "spicy")
    mode = normalized_input.get('mode')
    if mode is not None:
        normalized_mode = _normalize_mode_for_grok_imagine(mode)
        if normalized_mode is None:
            return False, f"Поле 'mode' должно быть 'fun', 'normal' или 'spicy' (получено: {mode})"
        normalized_input['mode'] = normalized_mode
    
    # ВАЖНО: Проверяем взаимоисключающие параметры
    # image_urls и task_id не должны использоваться одновременно
    has_image_urls = normalized_input.get('image_urls') is not None and len(normalized_input.get('image_urls', [])) > 0
    has_task_id = normalized_input.get('task_id') is not None and normalized_input.get('task_id')
    
    if has_image_urls and has_task_id:
        return False, "Поля 'image_urls' и 'task_id' не могут использоваться одновременно. Используйте либо 'image_urls', либо 'task_id'"
    
    # index работает только с task_id
    has_index = normalized_input.get('index') is not None
    if has_index and not has_task_id:
        return False, "Поле 'index' может использоваться только вместе с 'task_id'"
    
    # mode "spicy" не поддерживается с внешними изображениями (image_urls)
    if has_image_urls and normalized_input.get('mode') == 'spicy':
        return False, "Режим 'spicy' не поддерживается с внешними изображениями (image_urls). Используйте 'task_id' для режима 'spicy'"
    
    return True, None


def _normalize_aspect_ratio_for_grok_imagine_text_to_video(value: Any) -> Optional[str]:
    """
    Нормализует aspect_ratio для grok-imagine/text-to-video.
    Принимает строку и возвращает нормализованное значение.
    ВАЖНО: Для grok-imagine/text-to-video поддерживаются только "2:3", "3:2", "1:1" (3 значения)!
    
    Args:
        value: Значение aspect_ratio (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение
    valid_values = ["2:3", "3:2", "1:1"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["2:3", "2/3", "2x3"]:
        return "2:3"
    elif str_lower in ["3:2", "3/2", "3x2"]:
        return "3:2"
    elif str_lower in ["1:1", "1/1", "1x1", "square"]:
        return "1:1"
    
    return None


def _validate_grok_imagine_text_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для grok-imagine/text-to-video согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["grok-imagine/text-to-video", "grok/imagine-text-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация aspect_ratio: опциональный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        normalized_aspect_ratio = _normalize_aspect_ratio_for_grok_imagine_text_to_video(aspect_ratio)
        if normalized_aspect_ratio is None:
            valid_values = ["2:3", "3:2", "1:1"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация mode: опциональный, enum
    mode = normalized_input.get('mode')
    if mode is not None:
        normalized_mode = _normalize_mode_for_grok_imagine(mode)
        if normalized_mode is None:
            return False, f"Поле 'mode' должно быть 'fun', 'normal' или 'spicy' (получено: {mode})"
        normalized_input['mode'] = normalized_mode
    
    return True, None


def _validate_grok_imagine_text_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для grok-imagine/text-to-image согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["grok-imagine/text-to-image", "grok/imagine-text-to-image"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация aspect_ratio: опциональный, enum
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        # Переиспользуем функцию нормализации из text-to-video (те же 3 значения)
        normalized_aspect_ratio = _normalize_aspect_ratio_for_grok_imagine_text_to_video(aspect_ratio)
        if normalized_aspect_ratio is None:
            valid_values = ["2:3", "3:2", "1:1"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # ВАЖНО: Нет параметра mode для text-to-image (в отличие от text-to-video и image-to-video)
    
    return True, None


def _validate_grok_imagine_upscale(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для grok-imagine/upscale согласно документации API.
    
    ВАЖНО: Эта модель работает только с task_id от предыдущих генераций KIE AI,
    а не с прямыми URL изображений!
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["grok-imagine/upscale", "grok/imagine-upscale"]:
        return True, None
    
    # Валидация task_id: обязательный, максимум 100 символов
    task_id = normalized_input.get('task_id')
    if not task_id:
        return False, "Поле 'task_id' обязательно для апскейла. Используйте task_id от предыдущей генерации KIE AI (например, от grok-imagine/text-to-image)"
    
    if not isinstance(task_id, str):
        task_id = str(task_id)
    
    task_id = task_id.strip()
    if len(task_id) == 0:
        return False, "Поле 'task_id' не может быть пустым"
    if len(task_id) > 100:
        return False, f"Поле 'task_id' слишком длинное: {len(task_id)} символов (максимум 100)"
    
    normalized_input['task_id'] = task_id
    
    # ВАЖНО: Эта модель НЕ поддерживает image_url, image_base64 и другие параметры!
    # Только task_id от предыдущих генераций KIE AI
    
    return True, None


def _validate_kling_v1_avatar_standard(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling/v1-avatar-standard согласно документации API.
    
    ВАЖНО: Это модель lip sync, которая требует:
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - audio_url (обязательный, макс 10MB, mpeg/wav/aac/mp4/ogg)
    - prompt (обязательный, макс 5000 символов)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["kling/v1-avatar-standard", "kling/v1-avatar", "kling/avatar-standard"]:
        return True, None
    
    # Валидация image_url: обязательный
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации аватара. Загрузите изображение."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация audio_url: обязательный
    audio_url = normalized_input.get('audio_url')
    if not audio_url:
        return False, "Поле 'audio_url' обязательно для генерации аватара. Загрузите аудио файл."
    
    if not isinstance(audio_url, str):
        audio_url = str(audio_url)
    
    audio_url = audio_url.strip()
    if len(audio_url) == 0:
        return False, "Поле 'audio_url' не может быть пустым"
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации аватара. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    return True, None


def _validate_kling_ai_avatar_v1_pro(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling/ai-avatar-v1-pro согласно документации API.
    
    ВАЖНО: Это модель lip sync (Pro версия), которая требует:
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - audio_url (обязательный, макс 10MB, mpeg/wav/aac/mp4/ogg)
    - prompt (обязательный, макс 5000 символов)
    
    Параметры идентичны kling/v1-avatar-standard, но это другая модель (Pro версия).
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["kling/ai-avatar-v1-pro", "kling/avatar-v1-pro", "kling/ai-avatar-pro"]:
        return True, None
    
    # Валидация image_url: обязательный
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации аватара. Загрузите изображение."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация audio_url: обязательный
    audio_url = normalized_input.get('audio_url')
    if not audio_url:
        return False, "Поле 'audio_url' обязательно для генерации аватара. Загрузите аудио файл."
    
    if not isinstance(audio_url, str):
        audio_url = str(audio_url)
    
    audio_url = audio_url.strip()
    if len(audio_url) == 0:
        return False, "Поле 'audio_url' не может быть пустым"
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации аватара. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    return True, None


def _normalize_image_size_for_seedream_v4(value: Any) -> Optional[str]:
    """
    Нормализует image_size для bytedance/seedream-v4-text-to-image.
    Принимает значение и возвращает нормализованную строку.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение image_size (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = [
        "square", "square_hd",
        "portrait_4_3", "portrait_3_2", "portrait_16_9",
        "landscape_4_3", "landscape_3_2", "landscape_16_9", "landscape_21_9"
    ]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    # Пробуем нормализовать варианты написания
    if str_value in ["square", "sq"]:
        return "square"
    elif str_value in ["square_hd", "square-hd", "squarehd", "hd"]:
        return "square_hd"
    elif str_value in ["portrait_4_3", "portrait-4-3", "portrait43", "4:3 portrait", "3:4"]:
        return "portrait_4_3"
    elif str_value in ["portrait_3_2", "portrait-3-2", "portrait32", "2:3 portrait"]:
        return "portrait_3_2"
    elif str_value in ["portrait_16_9", "portrait-16-9", "portrait169", "9:16 portrait"]:
        return "portrait_16_9"
    elif str_value in ["landscape_4_3", "landscape-4-3", "landscape43", "4:3 landscape"]:
        return "landscape_4_3"
    elif str_value in ["landscape_3_2", "landscape-3-2", "landscape32", "3:2 landscape"]:
        return "landscape_3_2"
    elif str_value in ["landscape_16_9", "landscape-16-9", "landscape169", "16:9 landscape"]:
        return "landscape_16_9"
    elif str_value in ["landscape_21_9", "landscape-21-9", "landscape219", "21:9 landscape"]:
        return "landscape_21_9"
    
    return None


def _normalize_image_resolution_for_seedream_v4(value: Any) -> Optional[str]:
    """
    Нормализует image_resolution для bytedance/seedream-v4-text-to-image.
    Принимает значение и возвращает нормализованную строку в верхнем регистре.
    ВАЖНО: Поддерживаются только "1K", "2K", "4K"!
    
    Args:
        value: Значение image_resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["1K", "2K", "4K"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["1k", "1", "1000", "1k"]:
        return "1K"
    elif str_lower in ["2k", "2", "2000", "2k"]:
        return "2K"
    elif str_lower in ["4k", "4", "4000", "4k", "uhd"]:
        return "4K"
    
    return None


def _validate_bytedance_seedream_v4_text_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для bytedance/seedream-v4-text-to-image согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_size (опциональный, enum, default "square_hd")
    - image_resolution (опциональный, enum, default "1K")
    - max_images (опциональный, number, 1-6, default 1)
    - seed (опциональный, number)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["bytedance/seedream-v4-text-to-image", "seedream-v4-text-to-image", "seedream-v4-t2i"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_seedream_v4(image_size)
        if normalized_size is None:
            valid_values = [
                "square", "square_hd",
                "portrait_4_3", "portrait_3_2", "portrait_16_9",
                "landscape_4_3", "landscape_3_2", "landscape_16_9", "landscape_21_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация image_resolution: опциональный, enum
    image_resolution = normalized_input.get('image_resolution')
    if image_resolution is not None:
        normalized_resolution = _normalize_image_resolution_for_seedream_v4(image_resolution)
        if normalized_resolution is None:
            valid_values = ["1K", "2K", "4K"]
            return False, f"Поле 'image_resolution' должно быть одним из: {', '.join(valid_values)} (получено: {image_resolution})"
        normalized_input['image_resolution'] = normalized_resolution
    
    # Валидация max_images: опциональный, number, 1-6
    max_images = normalized_input.get('max_images')
    if max_images is not None:
        try:
            max_images_num = int(float(max_images))  # Поддерживаем и int и float
            if max_images_num < 1 or max_images_num > 6:
                return False, f"Поле 'max_images' должно быть в диапазоне от 1 до 6 (получено: {max_images})"
            normalized_input['max_images'] = max_images_num
        except (ValueError, TypeError):
            return False, f"Поле 'max_images' должно быть числом от 1 до 6 (получено: {max_images})"
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))  # Поддерживаем и int и float
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    return True, None


def _validate_bytedance_seedream_v4_edit(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для bytedance/seedream-v4-edit согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_urls (обязательный, массив, до 10 изображений)
    - image_size (опциональный, enum, default "square_hd")
    - image_resolution (опциональный, enum, default "1K")
    - max_images (опциональный, number, 1-6, default 1)
    - seed (опциональный, number)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["bytedance/seedream-v4-edit", "seedream-v4-edit", "seedream-v4-i2i"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для редактирования изображения"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_urls: обязательный, массив, до 10 изображений
    image_urls = normalized_input.get('image_urls')
    if not image_urls:
        return False, "Поле 'image_urls' обязательно для редактирования изображения. Загрузите хотя бы одно изображение."
    
    # Нормализуем в массив, если передан один URL
    if isinstance(image_urls, str):
        image_urls = [image_urls]
    elif not isinstance(image_urls, list):
        return False, f"Поле 'image_urls' должно быть массивом URL или одним URL (получено: {type(image_urls).__name__})"
    
    if len(image_urls) == 0:
        return False, "Поле 'image_urls' не может быть пустым массивом. Загрузите хотя бы одно изображение."
    
    if len(image_urls) > 10:
        return False, f"Поле 'image_urls' может содержать максимум 10 изображений (получено: {len(image_urls)})"
    
    # Проверяем что все элементы - строки
    normalized_urls = []
    for i, url in enumerate(image_urls):
        if not isinstance(url, str):
            url = str(url)
        url = url.strip()
        if len(url) == 0:
            return False, f"Элемент {i+1} в 'image_urls' не может быть пустым"
        normalized_urls.append(url)
    
    normalized_input['image_urls'] = normalized_urls
    
    # Валидация image_size: опциональный, enum (переиспользуем функцию из text-to-image)
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_seedream_v4(image_size)
        if normalized_size is None:
            valid_values = [
                "square", "square_hd",
                "portrait_4_3", "portrait_3_2", "portrait_16_9",
                "landscape_4_3", "landscape_3_2", "landscape_16_9", "landscape_21_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация image_resolution: опциональный, enum (переиспользуем функцию из text-to-image)
    image_resolution = normalized_input.get('image_resolution')
    if image_resolution is not None:
        normalized_resolution = _normalize_image_resolution_for_seedream_v4(image_resolution)
        if normalized_resolution is None:
            valid_values = ["1K", "2K", "4K"]
            return False, f"Поле 'image_resolution' должно быть одним из: {', '.join(valid_values)} (получено: {image_resolution})"
        normalized_input['image_resolution'] = normalized_resolution
    
    # Валидация max_images: опциональный, number, 1-6
    max_images = normalized_input.get('max_images')
    if max_images is not None:
        try:
            max_images_num = int(float(max_images))  # Поддерживаем и int и float
            if max_images_num < 1 or max_images_num > 6:
                return False, f"Поле 'max_images' должно быть в диапазоне от 1 до 6 (получено: {max_images})"
            normalized_input['max_images'] = max_images_num
        except (ValueError, TypeError):
            return False, f"Поле 'max_images' должно быть числом от 1 до 6 (получено: {max_images})"
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))  # Поддерживаем и int и float
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    return True, None


def _normalize_resolution_for_infinitalk_from_audio(value: Any) -> Optional[str]:
    """
    Нормализует resolution для infinitalk/from-audio.
    Принимает значение и возвращает нормализованную строку в нижнем регистре.
    ВАЖНО: Поддерживаются только "480p" и "720p"!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["480p", "720p"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    if str_value in ["480", "480p", "480 p", "480p"]:
        return "480p"
    elif str_value in ["720", "720p", "720 p", "720p", "hd"]:
        return "720p"
    
    return None


def _validate_infinitalk_from_audio(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для infinitalk/from-audio согласно документации API.
    
    ВАЖНО: Это модель lip sync, которая требует:
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - audio_url (обязательный, макс 10MB, mpeg/wav/aac/mp4/ogg)
    - prompt (обязательный, макс 5000 символов)
    - resolution (опциональный, "480p" | "720p", default "480p")
    - seed (опциональный, number, 10000-1000000)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["infinitalk/from-audio", "infinitalk/from-audio", "infinitalk-from-audio"]:
        return True, None
    
    # Валидация image_url: обязательный
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Загрузите изображение."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация audio_url: обязательный
    audio_url = normalized_input.get('audio_url')
    if not audio_url:
        return False, "Поле 'audio_url' обязательно для генерации видео. Загрузите аудио файл."
    
    if not isinstance(audio_url, str):
        audio_url = str(audio_url)
    
    audio_url = audio_url.strip()
    if len(audio_url) == 0:
        return False, "Поле 'audio_url' не может быть пустым"
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация resolution: опциональный, "480p" | "720p"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_infinitalk_from_audio(resolution)
        if normalized_resolution is None:
            valid_values = ["480p", "720p"]
            return False, f"Поле 'resolution' должно быть одним из: {', '.join(valid_values)} (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    # Валидация seed: опциональный, number, 10000-1000000
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))  # Поддерживаем и int и float
            if seed_num < 10000 or seed_num > 1000000:
                return False, f"Поле 'seed' должно быть в диапазоне от 10000 до 1000000 (получено: {seed})"
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом от 10000 до 1000000 (получено: {seed})"
    
    return True, None


def _validate_recraft_remove_background(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для recraft/remove-background согласно документации API.
    
    ВАЖНО: Эта модель требует:
    - image (обязательный, макс 5MB, PNG/JPG/WEBP, макс 16MP, макс размер 4096px, мин размер 256px)
    
    Параметр называется 'image' (не 'image_url'), но может быть нормализован из 'image_url' или 'image_base64'.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["recraft/remove-background", "recraft/remove-background", "recraft-remove-background"]:
        return True, None
    
    # Валидация image: обязательный
    # Модель использует параметр 'image', но мы можем принимать 'image_url', 'image_base64', или 'image'
    image = normalized_input.get('image') or normalized_input.get('image_url') or normalized_input.get('image_base64')
    if not image:
        return False, "Поле 'image' обязательно для удаления фона. Загрузите изображение."
    
    if not isinstance(image, str):
        image = str(image)
    
    image = image.strip()
    if len(image) == 0:
        return False, "Поле 'image' не может быть пустым"
    
    # Нормализуем: если был передан image_url или image_base64, переименовываем в image
    if 'image_url' in normalized_input and 'image' not in normalized_input:
        normalized_input['image'] = normalized_input.pop('image_url')
    elif 'image_base64' in normalized_input and 'image' not in normalized_input:
        normalized_input['image'] = normalized_input.pop('image_base64')
    elif 'image' not in normalized_input:
        normalized_input['image'] = image
    
    # Удаляем лишние параметры, если они были
    if 'image_url' in normalized_input and normalized_input.get('image') != normalized_input.get('image_url'):
        del normalized_input['image_url']
    if 'image_base64' in normalized_input and normalized_input.get('image') != normalized_input.get('image_base64'):
        del normalized_input['image_base64']
    
    return True, None


def _validate_recraft_crisp_upscale(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для recraft/crisp-upscale согласно документации API.
    
    ВАЖНО: Эта модель требует:
    - image (обязательный, макс 10MB, PNG/JPG/WEBP)
    
    Параметр называется 'image' (не 'image_url'), но может быть нормализован из 'image_url' или 'image_base64'.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["recraft/crisp-upscale", "recraft-crisp-upscale", "recraft/crisp-upscaler"]:
        return True, None
    
    # Валидация image: обязательный
    # Модель использует параметр 'image', но мы можем принимать 'image_url', 'image_base64', или 'image'
    image = normalized_input.get('image') or normalized_input.get('image_url') or normalized_input.get('image_base64')
    if not image:
        return False, "Поле 'image' обязательно для апскейла изображения. Загрузите изображение."
    
    if not isinstance(image, str):
        image = str(image)
    
    image = image.strip()
    if len(image) == 0:
        return False, "Поле 'image' не может быть пустым"
    
    # Нормализуем: если был передан image_url или image_base64, переименовываем в image
    if 'image_url' in normalized_input and 'image' not in normalized_input:
        normalized_input['image'] = normalized_input.pop('image_url')
    elif 'image_base64' in normalized_input and 'image' not in normalized_input:
        normalized_input['image'] = normalized_input.pop('image_base64')
    elif 'image' not in normalized_input:
        normalized_input['image'] = image
    
    # Удаляем лишние параметры, если они были
    if 'image_url' in normalized_input and normalized_input.get('image') != normalized_input.get('image_url'):
        del normalized_input['image_url']
    if 'image_base64' in normalized_input and normalized_input.get('image') != normalized_input.get('image_base64'):
        del normalized_input['image_base64']
    
    return True, None


def _normalize_image_size_for_ideogram_v3_reframe(value: Any) -> Optional[str]:
    """
    Нормализует image_size для ideogram/v3-reframe.
    Принимает значение и возвращает нормализованную строку.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение image_size (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = [
        "square", "square_hd",
        "portrait_4_3", "portrait_16_9",
        "landscape_4_3", "landscape_16_9"
    ]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    # Пробуем нормализовать варианты написания
    if str_value in ["square", "sq"]:
        return "square"
    elif str_value in ["square_hd", "square-hd", "squarehd", "hd"]:
        return "square_hd"
    elif str_value in ["portrait_4_3", "portrait-4-3", "portrait43", "4:3 portrait", "3:4"]:
        return "portrait_4_3"
    elif str_value in ["portrait_16_9", "portrait-16-9", "portrait169", "9:16 portrait"]:
        return "portrait_16_9"
    elif str_value in ["landscape_4_3", "landscape-4-3", "landscape43", "4:3 landscape"]:
        return "landscape_4_3"
    elif str_value in ["landscape_16_9", "landscape-16-9", "landscape169", "16:9 landscape"]:
        return "landscape_16_9"
    
    return None


def _normalize_rendering_speed_for_ideogram_v3_reframe(value: Any) -> Optional[str]:
    """
    Нормализует rendering_speed для ideogram/v3-reframe.
    Принимает значение и возвращает нормализованную строку в верхнем регистре.
    ВАЖНО: Поддерживаются только "TURBO", "BALANCED", "QUALITY"!
    
    Args:
        value: Значение rendering_speed (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["TURBO", "BALANCED", "QUALITY"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["turbo", "fast", "speed"]:
        return "TURBO"
    elif str_lower in ["balanced", "balance", "normal", "medium"]:
        return "BALANCED"
    elif str_lower in ["quality", "high", "best"]:
        return "QUALITY"
    
    return None


def _normalize_style_for_ideogram_v3_reframe(value: Any) -> Optional[str]:
    """
    Нормализует style для ideogram/v3-reframe.
    Принимает значение и возвращает нормализованную строку в верхнем регистре.
    ВАЖНО: Поддерживаются только "AUTO", "GENERAL", "REALISTIC", "DESIGN"!
    
    Args:
        value: Значение style (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["AUTO", "GENERAL", "REALISTIC", "DESIGN"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["auto", "automatic", "default"]:
        return "AUTO"
    elif str_lower in ["general", "generic", "standard"]:
        return "GENERAL"
    elif str_lower in ["realistic", "real", "photo", "photorealistic"]:
        return "REALISTIC"
    elif str_lower in ["design", "graphic", "artistic"]:
        return "DESIGN"
    
    return None


def _normalize_num_images_for_ideogram_v3_reframe(value: Any) -> Optional[str]:
    """
    Нормализует num_images для ideogram/v3-reframe.
    Принимает значение и возвращает нормализованную строку.
    ВАЖНО: Поддерживаются только "1", "2", "3", "4"!
    
    Args:
        value: Значение num_images (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение
    valid_values = ["1", "2", "3", "4"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания (числа)
    try:
        num = int(float(str_value))
        if 1 <= num <= 4:
            return str(num)
    except (ValueError, TypeError):
        pass
    
    return None


def _validate_ideogram_v3_reframe(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для ideogram/v3-reframe согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - image_size (обязательный, enum, default "square_hd")
    - rendering_speed (опциональный, enum, default "BALANCED")
    - style (опциональный, enum, default "AUTO")
    - num_images (опциональный, enum, default "1")
    - seed (опциональный, number, default 0)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["ideogram/v3-reframe", "ideogram-v3-reframe", "ideogram/v3-reframe"]:
        return True, None
    
    # Валидация image_url: обязательный
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для рефрейминга изображения. Загрузите изображение."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация image_size: обязательный, enum
    image_size = normalized_input.get('image_size')
    if not image_size:
        return False, "Поле 'image_size' обязательно для рефрейминга изображения. Укажите размер выходного изображения."
    
    normalized_size = _normalize_image_size_for_ideogram_v3_reframe(image_size)
    if normalized_size is None:
        valid_values = [
            "square", "square_hd",
            "portrait_4_3", "portrait_16_9",
            "landscape_4_3", "landscape_16_9"
        ]
        return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
    normalized_input['image_size'] = normalized_size
    
    # Валидация rendering_speed: опциональный, enum
    rendering_speed = normalized_input.get('rendering_speed')
    if rendering_speed is not None:
        normalized_speed = _normalize_rendering_speed_for_ideogram_v3_reframe(rendering_speed)
        if normalized_speed is None:
            valid_values = ["TURBO", "BALANCED", "QUALITY"]
            return False, f"Поле 'rendering_speed' должно быть одним из: {', '.join(valid_values)} (получено: {rendering_speed})"
        normalized_input['rendering_speed'] = normalized_speed
    
    # Валидация style: опциональный, enum
    style = normalized_input.get('style')
    if style is not None:
        normalized_style = _normalize_style_for_ideogram_v3_reframe(style)
        if normalized_style is None:
            valid_values = ["AUTO", "GENERAL", "REALISTIC", "DESIGN"]
            return False, f"Поле 'style' должно быть одним из: {', '.join(valid_values)} (получено: {style})"
        normalized_input['style'] = normalized_style
    
    # Валидация num_images: опциональный, enum
    num_images = normalized_input.get('num_images')
    if num_images is not None:
        normalized_num = _normalize_num_images_for_ideogram_v3_reframe(num_images)
        if normalized_num is None:
            valid_values = ["1", "2", "3", "4"]
            return False, f"Поле 'num_images' должно быть одним из: {', '.join(valid_values)} (получено: {num_images})"
        normalized_input['num_images'] = normalized_num
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))  # Поддерживаем и int и float
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    return True, None


def _validate_elevenlabs_audio_isolation(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для elevenlabs/audio-isolation согласно документации API.
    
    ВАЖНО: Эта модель требует:
    - audio_url (обязательный, макс 10MB, mpeg/wav/aac/mp4/ogg)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["elevenlabs/audio-isolation", "elevenlabs-audio-isolation", "elevenlabs/audio-isolation"]:
        return True, None
    
    # Валидация audio_url: обязательный
    # Модель использует параметр 'audio_url', но мы можем принимать 'audio' или 'audio_url'
    audio_url = normalized_input.get('audio_url') or normalized_input.get('audio')
    if not audio_url:
        return False, "Поле 'audio_url' обязательно для изоляции голоса. Загрузите аудио файл."
    
    if not isinstance(audio_url, str):
        audio_url = str(audio_url)
    
    audio_url = audio_url.strip()
    if len(audio_url) == 0:
        return False, "Поле 'audio_url' не может быть пустым"
    
    # Нормализуем: если был передан 'audio', переименовываем в 'audio_url'
    if 'audio' in normalized_input and 'audio_url' not in normalized_input:
        normalized_input['audio_url'] = normalized_input.pop('audio')
    elif 'audio_url' not in normalized_input:
        normalized_input['audio_url'] = audio_url
    
    # Удаляем лишний параметр, если он был
    if 'audio' in normalized_input and normalized_input.get('audio_url') != normalized_input.get('audio'):
        del normalized_input['audio']
    
    return True, None


def _normalize_output_format_for_elevenlabs_sound_effect_v2(value: Any) -> Optional[str]:
    """
    Нормализует output_format для elevenlabs/sound-effect-v2.
    Принимает значение и возвращает нормализованную строку в нижнем регистре.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение output_format (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = [
        "mp3_22050_32", "mp3_44100_32", "mp3_44100_64", "mp3_44100_96",
        "mp3_44100_128", "mp3_44100_192",
        "pcm_8000", "pcm_16000", "pcm_22050", "pcm_24000", "pcm_44100", "pcm_48000",
        "ulaw_8000", "alaw_8000",
        "opus_48000_32", "opus_48000_64", "opus_48000_96", "opus_48000_128", "opus_48000_192"
    ]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    return None


def _validate_elevenlabs_sound_effect_v2(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для elevenlabs/sound-effect-v2 согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - text (обязательный, макс 5000 символов)
    - loop (опциональный, boolean, default false)
    - duration_seconds (опциональный, number, 0.5-22)
    - prompt_influence (опциональный, number, 0-1, default 0.3)
    - output_format (опциональный, enum, default "mp3_44100_128")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["elevenlabs/sound-effect-v2", "elevenlabs-sound-effect-v2", "elevenlabs/sound-effect-v2"]:
        return True, None
    
    # Валидация text: обязательный, максимум 5000 символов
    # Модель использует 'text' (не 'prompt'), но мы можем принимать оба
    text = normalized_input.get('text') or normalized_input.get('prompt')
    if not text:
        return False, "Поле 'text' обязательно для генерации звукового эффекта. Введите текстовое описание."
    
    if not isinstance(text, str):
        text = str(text)
    
    text_len = len(text.strip())
    if text_len == 0:
        return False, "Поле 'text' не может быть пустым"
    if text_len > 5000:
        return False, f"Поле 'text' слишком длинное: {text_len} символов (максимум 5000)"
    
    # Нормализуем: если был передан 'prompt', переименовываем в 'text'
    if 'prompt' in normalized_input and 'text' not in normalized_input:
        normalized_input['text'] = normalized_input.pop('prompt')
    elif 'text' not in normalized_input:
        normalized_input['text'] = text
    
    # Удаляем лишний параметр, если он был
    if 'prompt' in normalized_input and normalized_input.get('text') != normalized_input.get('prompt'):
        del normalized_input['prompt']
    
    # Валидация loop: опциональный, boolean
    loop = normalized_input.get('loop')
    if loop is not None:
        normalized_bool = _normalize_boolean(loop)
        if normalized_bool is None:
            return False, f"Поле 'loop' должно быть boolean (true/false) (получено: {loop})"
        normalized_input['loop'] = normalized_bool
    
    # Валидация duration_seconds: опциональный, number, 0.5-22
    duration_seconds = normalized_input.get('duration_seconds')
    if duration_seconds is not None:
        try:
            duration_num = float(duration_seconds)
            if duration_num < 0.5 or duration_num > 22:
                return False, f"Поле 'duration_seconds' должно быть в диапазоне от 0.5 до 22 (получено: {duration_seconds})"
            normalized_input['duration_seconds'] = duration_num
        except (ValueError, TypeError):
            return False, f"Поле 'duration_seconds' должно быть числом от 0.5 до 22 (получено: {duration_seconds})"
    
    # Валидация prompt_influence: опциональный, number, 0-1
    prompt_influence = normalized_input.get('prompt_influence')
    if prompt_influence is not None:
        try:
            influence_num = float(prompt_influence)
            if influence_num < 0 or influence_num > 1:
                return False, f"Поле 'prompt_influence' должно быть в диапазоне от 0 до 1 (получено: {prompt_influence})"
            normalized_input['prompt_influence'] = influence_num
        except (ValueError, TypeError):
            return False, f"Поле 'prompt_influence' должно быть числом от 0 до 1 (получено: {prompt_influence})"
    
    # Валидация output_format: опциональный, enum
    output_format = normalized_input.get('output_format')
    if output_format is not None:
        normalized_format = _normalize_output_format_for_elevenlabs_sound_effect_v2(output_format)
        if normalized_format is None:
            valid_values = [
                "mp3_22050_32", "mp3_44100_32", "mp3_44100_64", "mp3_44100_96",
                "mp3_44100_128", "mp3_44100_192",
                "pcm_8000", "pcm_16000", "pcm_22050", "pcm_24000", "pcm_44100", "pcm_48000",
                "ulaw_8000", "alaw_8000",
                "opus_48000_32", "opus_48000_64", "opus_48000_96", "opus_48000_128", "opus_48000_192"
            ]
            return False, f"Поле 'output_format' должно быть одним из: {', '.join(valid_values)} (получено: {output_format})"
        normalized_input['output_format'] = normalized_format
    
    return True, None


def _validate_elevenlabs_speech_to_text(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для elevenlabs/speech-to-text согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - audio_url (обязательный, макс 200MB, mpeg/wav/aac/mp4/ogg)
    - language_code (опциональный, string, макс 500 символов, default "")
    - tag_audio_events (опциональный, boolean, default true)
    - diarize (опциональный, boolean, default true)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["elevenlabs/speech-to-text", "elevenlabs-speech-to-text", "elevenlabs/speech-to-text"]:
        return True, None
    
    # Валидация audio_url: обязательный
    # Модель использует параметр 'audio_url', но мы можем принимать 'audio' или 'audio_url'
    audio_url = normalized_input.get('audio_url') or normalized_input.get('audio')
    if not audio_url:
        return False, "Поле 'audio_url' обязательно для транскрипции аудио. Загрузите аудио файл."
    
    if not isinstance(audio_url, str):
        audio_url = str(audio_url)
    
    audio_url = audio_url.strip()
    if len(audio_url) == 0:
        return False, "Поле 'audio_url' не может быть пустым"
    
    # Нормализуем: если был передан 'audio', переименовываем в 'audio_url'
    if 'audio' in normalized_input and 'audio_url' not in normalized_input:
        normalized_input['audio_url'] = normalized_input.pop('audio')
    elif 'audio_url' not in normalized_input:
        normalized_input['audio_url'] = audio_url
    
    # Удаляем лишний параметр, если он был
    if 'audio' in normalized_input and normalized_input.get('audio_url') != normalized_input.get('audio'):
        del normalized_input['audio']
    
    # Валидация language_code: опциональный, string, макс 500 символов
    language_code = normalized_input.get('language_code')
    if language_code is not None:
        if not isinstance(language_code, str):
            language_code = str(language_code)
        language_code = language_code.strip()
        if len(language_code) > 500:
            return False, f"Поле 'language_code' слишком длинное: {len(language_code)} символов (максимум 500)"
        normalized_input['language_code'] = language_code
    
    # Валидация tag_audio_events: опциональный, boolean
    tag_audio_events = normalized_input.get('tag_audio_events')
    if tag_audio_events is not None:
        normalized_bool = _normalize_boolean(tag_audio_events)
        if normalized_bool is None:
            return False, f"Поле 'tag_audio_events' должно быть boolean (true/false) (получено: {tag_audio_events})"
        normalized_input['tag_audio_events'] = normalized_bool
    
    # Валидация diarize: опциональный, boolean
    diarize = normalized_input.get('diarize')
    if diarize is not None:
        normalized_bool = _normalize_boolean(diarize)
        if normalized_bool is None:
            return False, f"Поле 'diarize' должно быть boolean (true/false) (получено: {diarize})"
        normalized_input['diarize'] = normalized_bool
    
    return True, None


def _normalize_voice_for_elevenlabs_tts_multilingual_v2(value: Any) -> Optional[str]:
    """
    Нормализует voice для elevenlabs/text-to-speech-multilingual-v2.
    Принимает значение и возвращает нормализованную строку с первой заглавной буквой.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение voice (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение
    valid_values = [
        "Rachel", "Aria", "Roger", "Sarah", "Laura", "Charlie", "George", "Callum",
        "River", "Liam", "Charlotte", "Alice", "Matilda", "Will", "Jessica", "Eric",
        "Chris", "Brian", "Daniel", "Lily", "Bill"
    ]
    
    # Проверяем точное совпадение (case-insensitive, но возвращаем с правильным регистром)
    for valid in valid_values:
        if str_value.lower() == valid.lower():
            return valid
    
    return None


def _validate_elevenlabs_text_to_speech_multilingual_v2(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для elevenlabs/text-to-speech-multilingual-v2 согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - text (обязательный, макс 5000 символов)
    - voice (опциональный, enum, 21 значение, default "Rachel")
    - stability (опциональный, number, 0-1, default 0.5)
    - similarity_boost (опциональный, number, 0-1, default 0.75)
    - style (опциональный, number, 0-1, default 0)
    - speed (опциональный, number, 0.7-1.2, default 1)
    - timestamps (опциональный, boolean, default false)
    - previous_text (опциональный, string, макс 5000 символов, default "")
    - next_text (опциональный, string, макс 5000 символов, default "")
    - language_code (опциональный, string, макс 500 символов, default "")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["elevenlabs/text-to-speech-multilingual-v2", "elevenlabs-text-to-speech-multilingual-v2", "elevenlabs/text-to-speech-multilingual-v2"]:
        return True, None
    
    # Валидация text: обязательный, максимум 5000 символов
    text = normalized_input.get('text')
    if not text:
        return False, "Поле 'text' обязательно для генерации речи. Введите текст для преобразования в речь."
    
    if not isinstance(text, str):
        text = str(text)
    
    text_len = len(text.strip())
    if text_len == 0:
        return False, "Поле 'text' не может быть пустым"
    if text_len > 5000:
        return False, f"Поле 'text' слишком длинное: {text_len} символов (максимум 5000)"
    
    # Валидация voice: опциональный, enum
    voice = normalized_input.get('voice')
    if voice is not None:
        normalized_voice = _normalize_voice_for_elevenlabs_tts_multilingual_v2(voice)
        if normalized_voice is None:
            valid_values = [
                "Rachel", "Aria", "Roger", "Sarah", "Laura", "Charlie", "George", "Callum",
                "River", "Liam", "Charlotte", "Alice", "Matilda", "Will", "Jessica", "Eric",
                "Chris", "Brian", "Daniel", "Lily", "Bill"
            ]
            return False, f"Поле 'voice' должно быть одним из: {', '.join(valid_values)} (получено: {voice})"
        normalized_input['voice'] = normalized_voice
    
    # Валидация stability: опциональный, number, 0-1
    stability = normalized_input.get('stability')
    if stability is not None:
        try:
            stability_num = float(stability)
            if stability_num < 0 or stability_num > 1:
                return False, f"Поле 'stability' должно быть в диапазоне от 0 до 1 (получено: {stability})"
            normalized_input['stability'] = stability_num
        except (ValueError, TypeError):
            return False, f"Поле 'stability' должно быть числом от 0 до 1 (получено: {stability})"
    
    # Валидация similarity_boost: опциональный, number, 0-1
    similarity_boost = normalized_input.get('similarity_boost')
    if similarity_boost is not None:
        try:
            boost_num = float(similarity_boost)
            if boost_num < 0 or boost_num > 1:
                return False, f"Поле 'similarity_boost' должно быть в диапазоне от 0 до 1 (получено: {similarity_boost})"
            normalized_input['similarity_boost'] = boost_num
        except (ValueError, TypeError):
            return False, f"Поле 'similarity_boost' должно быть числом от 0 до 1 (получено: {similarity_boost})"
    
    # Валидация style: опциональный, number, 0-1
    style = normalized_input.get('style')
    if style is not None:
        try:
            style_num = float(style)
            if style_num < 0 or style_num > 1:
                return False, f"Поле 'style' должно быть в диапазоне от 0 до 1 (получено: {style})"
            normalized_input['style'] = style_num
        except (ValueError, TypeError):
            return False, f"Поле 'style' должно быть числом от 0 до 1 (получено: {style})"
    
    # Валидация speed: опциональный, number, 0.7-1.2
    speed = normalized_input.get('speed')
    if speed is not None:
        try:
            speed_num = float(speed)
            if speed_num < 0.7 or speed_num > 1.2:
                return False, f"Поле 'speed' должно быть в диапазоне от 0.7 до 1.2 (получено: {speed})"
            normalized_input['speed'] = speed_num
        except (ValueError, TypeError):
            return False, f"Поле 'speed' должно быть числом от 0.7 до 1.2 (получено: {speed})"
    
    # Валидация timestamps: опциональный, boolean
    timestamps = normalized_input.get('timestamps')
    if timestamps is not None:
        normalized_bool = _normalize_boolean(timestamps)
        if normalized_bool is None:
            return False, f"Поле 'timestamps' должно быть boolean (true/false) (получено: {timestamps})"
        normalized_input['timestamps'] = normalized_bool
    
    # Валидация previous_text: опциональный, string, макс 5000 символов
    previous_text = normalized_input.get('previous_text')
    if previous_text is not None:
        if not isinstance(previous_text, str):
            previous_text = str(previous_text)
        previous_text = previous_text.strip()
        if len(previous_text) > 5000:
            return False, f"Поле 'previous_text' слишком длинное: {len(previous_text)} символов (максимум 5000)"
        normalized_input['previous_text'] = previous_text
    
    # Валидация next_text: опциональный, string, макс 5000 символов
    next_text = normalized_input.get('next_text')
    if next_text is not None:
        if not isinstance(next_text, str):
            next_text = str(next_text)
        next_text = next_text.strip()
        if len(next_text) > 5000:
            return False, f"Поле 'next_text' слишком длинное: {len(next_text)} символов (максимум 5000)"
        normalized_input['next_text'] = next_text
    
    # Валидация language_code: опциональный, string, макс 500 символов
    language_code = normalized_input.get('language_code')
    if language_code is not None:
        if not isinstance(language_code, str):
            language_code = str(language_code)
        language_code = language_code.strip()
        if len(language_code) > 500:
            return False, f"Поле 'language_code' слишком длинное: {len(language_code)} символов (максимум 500)"
        normalized_input['language_code'] = language_code
    
    return True, None


def _normalize_resolution_for_wan_2_2_a14b_speech_to_video_turbo(value: Any) -> Optional[str]:
    """
    Нормализует resolution для wan/2-2-a14b-speech-to-video-turbo.
    Принимает значение и возвращает нормализованную строку в нижнем регистре с 'p'.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["480p", "580p", "720p"]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    return None


def _validate_wan_2_2_a14b_speech_to_video_turbo(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-2-a14b-speech-to-video-turbo согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - audio_url (обязательный, макс 10MB, mp3/wav/ogg/m4a/flac/aac/x-ms-wma/mpeg)
    - num_frames (опциональный, number, 40-120, кратно 4, default 80)
    - frames_per_second (опциональный, number, 4-60, default 16)
    - resolution (опциональный, enum, default "480p")
    - negative_prompt (опциональный, string, макс 500 символов, default "")
    - seed (опциональный, number)
    - num_inference_steps (опциональный, number, 2-40, default 27)
    - guidance_scale (опциональный, number, 1-10, default 3.5)
    - shift (опциональный, number, 1-10, default 5)
    - enable_safety_checker (опциональный, boolean, default true)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["wan/2-2-a14b-speech-to-video-turbo", "wan-2-2-a14b-speech-to-video-turbo", "wan/2-2-a14b-speech-to-video-turbo"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация audio_url: обязательный, string
    audio_url = normalized_input.get('audio_url')
    if not audio_url:
        return False, "Поле 'audio_url' обязательно для генерации видео. Укажите URL аудио файла."
    
    if not isinstance(audio_url, str):
        audio_url = str(audio_url)
    
    audio_url = audio_url.strip()
    if len(audio_url) == 0:
        return False, "Поле 'audio_url' не может быть пустым"
    
    # Валидация num_frames: опциональный, number, 40-120, кратно 4
    num_frames = normalized_input.get('num_frames')
    if num_frames is not None:
        try:
            frames_num = int(float(num_frames))
            if frames_num < 40 or frames_num > 120:
                return False, f"Поле 'num_frames' должно быть в диапазоне от 40 до 120 (получено: {num_frames})"
            if frames_num % 4 != 0:
                return False, f"Поле 'num_frames' должно быть кратно 4 (получено: {num_frames})"
            normalized_input['num_frames'] = frames_num
        except (ValueError, TypeError):
            return False, f"Поле 'num_frames' должно быть числом от 40 до 120 (кратно 4) (получено: {num_frames})"
    
    # Валидация frames_per_second: опциональный, number, 4-60
    frames_per_second = normalized_input.get('frames_per_second')
    if frames_per_second is not None:
        try:
            fps_num = int(float(frames_per_second))
            if fps_num < 4 or fps_num > 60:
                return False, f"Поле 'frames_per_second' должно быть в диапазоне от 4 до 60 (получено: {frames_per_second})"
            normalized_input['frames_per_second'] = fps_num
        except (ValueError, TypeError):
            return False, f"Поле 'frames_per_second' должно быть числом от 4 до 60 (получено: {frames_per_second})"
    
    # Валидация resolution: опциональный, enum
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_wan_2_2_a14b_speech_to_video_turbo(resolution)
        if normalized_resolution is None:
            return False, f"Поле 'resolution' должно быть одним из: 480p, 580p, 720p (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация num_inference_steps: опциональный, number, 2-40
    num_inference_steps = normalized_input.get('num_inference_steps')
    if num_inference_steps is not None:
        try:
            steps_num = int(float(num_inference_steps))
            if steps_num < 2 or steps_num > 40:
                return False, f"Поле 'num_inference_steps' должно быть в диапазоне от 2 до 40 (получено: {num_inference_steps})"
            normalized_input['num_inference_steps'] = steps_num
        except (ValueError, TypeError):
            return False, f"Поле 'num_inference_steps' должно быть числом от 2 до 40 (получено: {num_inference_steps})"
    
    # Валидация guidance_scale: опциональный, number, 1-10
    guidance_scale = normalized_input.get('guidance_scale')
    if guidance_scale is not None:
        try:
            scale_num = float(guidance_scale)
            if scale_num < 1 or scale_num > 10:
                return False, f"Поле 'guidance_scale' должно быть в диапазоне от 1 до 10 (получено: {guidance_scale})"
            normalized_input['guidance_scale'] = scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'guidance_scale' должно быть числом от 1 до 10 (получено: {guidance_scale})"
    
    # Валидация shift: опциональный, number, 1-10
    shift = normalized_input.get('shift')
    if shift is not None:
        try:
            shift_num = float(shift)
            if shift_num < 1 or shift_num > 10:
                return False, f"Поле 'shift' должно быть в диапазоне от 1 до 10 (получено: {shift})"
            normalized_input['shift'] = shift_num
        except (ValueError, TypeError):
            return False, f"Поле 'shift' должно быть числом от 1 до 10 (получено: {shift})"
    
    # Валидация enable_safety_checker: опциональный, boolean
    enable_safety_checker = normalized_input.get('enable_safety_checker')
    if enable_safety_checker is not None:
        normalized_bool = _normalize_boolean(enable_safety_checker)
        if normalized_bool is None:
            return False, f"Поле 'enable_safety_checker' должно быть boolean (true/false) (получено: {enable_safety_checker})"
        normalized_input['enable_safety_checker'] = normalized_bool
    
    return True, None


def _normalize_image_size_for_bytedance_seedream(value: Any) -> Optional[str]:
    """
    Нормализует image_size для bytedance/seedream.
    Принимает значение и возвращает нормализованную строку в нижнем регистре с подчеркиваниями.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение image_size (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = [
        "square", "square_hd", "portrait_4_3", "portrait_16_9",
        "landscape_4_3", "landscape_16_9"
    ]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    return None


def _validate_bytedance_seedream(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для bytedance/seedream согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_size (опциональный, enum, 6 значений, default "square_hd")
    - guidance_scale (опциональный, number, 1-10, default 2.5)
    - seed (опциональный, number)
    - enable_safety_checker (опциональный, boolean, default true)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["bytedance/seedream", "bytedance-seedream", "seedream"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_bytedance_seedream(image_size)
        if normalized_size is None:
            valid_values = [
                "square", "square_hd", "portrait_4_3", "portrait_16_9",
                "landscape_4_3", "landscape_16_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация guidance_scale: опциональный, number, 1-10
    guidance_scale = normalized_input.get('guidance_scale')
    if guidance_scale is not None:
        try:
            scale_num = float(guidance_scale)
            if scale_num < 1 or scale_num > 10:
                return False, f"Поле 'guidance_scale' должно быть в диапазоне от 1 до 10 (получено: {guidance_scale})"
            normalized_input['guidance_scale'] = scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'guidance_scale' должно быть числом от 1 до 10 (получено: {guidance_scale})"
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация enable_safety_checker: опциональный, boolean
    enable_safety_checker = normalized_input.get('enable_safety_checker')
    if enable_safety_checker is not None:
        normalized_bool = _normalize_boolean(enable_safety_checker)
        if normalized_bool is None:
            return False, f"Поле 'enable_safety_checker' должно быть boolean (true/false) (получено: {enable_safety_checker})"
        normalized_input['enable_safety_checker'] = normalized_bool
    
    return True, None


def _normalize_output_format_for_qwen_i2i(value: Any) -> Optional[str]:
    """
    Нормализует output_format для qwen/image-to-image.
    Принимает значение и возвращает нормализованную строку в нижнем регистре.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение output_format (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["png", "jpeg"]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    return None


def _normalize_acceleration_for_qwen_i2i(value: Any) -> Optional[str]:
    """
    Нормализует acceleration для qwen/image-to-image.
    Принимает значение и возвращает нормализованную строку в нижнем регистре.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение acceleration (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["none", "regular", "high"]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    return None


def _validate_qwen_image_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для qwen/image-to-image согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - strength (опциональный, number, 0-1, default 0.8)
    - output_format (опциональный, enum, default "png")
    - acceleration (опциональный, enum, default "none")
    - negative_prompt (опциональный, string, макс 500 символов, default "blurry, ugly")
    - seed (опциональный, number)
    - num_inference_steps (опциональный, number, 2-250, default 30)
    - guidance_scale (опциональный, number, 0-20, default 2.5)
    - enable_safety_checker (опциональный, boolean, default true)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["qwen/image-to-image", "qwen-image-to-image", "qwen/i2i"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации изображения. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация strength: опциональный, number, 0-1
    strength = normalized_input.get('strength')
    if strength is not None:
        try:
            strength_num = float(strength)
            if strength_num < 0 or strength_num > 1:
                return False, f"Поле 'strength' должно быть в диапазоне от 0 до 1 (получено: {strength})"
            normalized_input['strength'] = strength_num
        except (ValueError, TypeError):
            return False, f"Поле 'strength' должно быть числом от 0 до 1 (получено: {strength})"
    
    # Валидация output_format: опциональный, enum
    output_format = normalized_input.get('output_format')
    if output_format is not None:
        normalized_format = _normalize_output_format_for_qwen_i2i(output_format)
        if normalized_format is None:
            return False, f"Поле 'output_format' должно быть одним из: png, jpeg (получено: {output_format})"
        normalized_input['output_format'] = normalized_format
    
    # Валидация acceleration: опциональный, enum
    acceleration = normalized_input.get('acceleration')
    if acceleration is not None:
        normalized_accel = _normalize_acceleration_for_qwen_i2i(acceleration)
        if normalized_accel is None:
            return False, f"Поле 'acceleration' должно быть одним из: none, regular, high (получено: {acceleration})"
        normalized_input['acceleration'] = normalized_accel
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация num_inference_steps: опциональный, number, 2-250
    num_inference_steps = normalized_input.get('num_inference_steps')
    if num_inference_steps is not None:
        try:
            steps_num = int(float(num_inference_steps))
            if steps_num < 2 or steps_num > 250:
                return False, f"Поле 'num_inference_steps' должно быть в диапазоне от 2 до 250 (получено: {num_inference_steps})"
            normalized_input['num_inference_steps'] = steps_num
        except (ValueError, TypeError):
            return False, f"Поле 'num_inference_steps' должно быть числом от 2 до 250 (получено: {num_inference_steps})"
    
    # Валидация guidance_scale: опциональный, number, 0-20
    guidance_scale = normalized_input.get('guidance_scale')
    if guidance_scale is not None:
        try:
            scale_num = float(guidance_scale)
            if scale_num < 0 or scale_num > 20:
                return False, f"Поле 'guidance_scale' должно быть в диапазоне от 0 до 20 (получено: {guidance_scale})"
            normalized_input['guidance_scale'] = scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'guidance_scale' должно быть числом от 0 до 20 (получено: {guidance_scale})"
    
    # Валидация enable_safety_checker: опциональный, boolean
    enable_safety_checker = normalized_input.get('enable_safety_checker')
    if enable_safety_checker is not None:
        normalized_bool = _normalize_boolean(enable_safety_checker)
        if normalized_bool is None:
            return False, f"Поле 'enable_safety_checker' должно быть boolean (true/false) (получено: {enable_safety_checker})"
        normalized_input['enable_safety_checker'] = normalized_bool
    
    return True, None


def _normalize_image_size_for_qwen_t2i(value: Any) -> Optional[str]:
    """
    Нормализует image_size для qwen/text-to-image.
    Принимает значение и возвращает нормализованную строку в нижнем регистре с подчеркиваниями.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение image_size (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = [
        "square", "square_hd", "portrait_4_3", "portrait_16_9",
        "landscape_4_3", "landscape_16_9"
    ]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    return None


def _validate_qwen_text_to_image(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для qwen/text-to-image согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_size (опциональный, enum, 6 значений, default "square_hd")
    - num_inference_steps (опциональный, number, 2-250, default 30)
    - seed (опциональный, number)
    - guidance_scale (опциональный, number, 0-20, default 2.5)
    - enable_safety_checker (опциональный, boolean, default true)
    - output_format (опциональный, enum, default "png")
    - negative_prompt (опциональный, string, макс 500 символов, default " " (пробел!))
    - acceleration (опциональный, enum, default "none")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["qwen/text-to-image", "qwen-text-to-image", "qwen/t2i"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_qwen_t2i(image_size)
        if normalized_size is None:
            valid_values = [
                "square", "square_hd", "portrait_4_3", "portrait_16_9",
                "landscape_4_3", "landscape_16_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация num_inference_steps: опциональный, number, 2-250
    num_inference_steps = normalized_input.get('num_inference_steps')
    if num_inference_steps is not None:
        try:
            steps_num = int(float(num_inference_steps))
            if steps_num < 2 or steps_num > 250:
                return False, f"Поле 'num_inference_steps' должно быть в диапазоне от 2 до 250 (получено: {num_inference_steps})"
            normalized_input['num_inference_steps'] = steps_num
        except (ValueError, TypeError):
            return False, f"Поле 'num_inference_steps' должно быть числом от 2 до 250 (получено: {num_inference_steps})"
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация guidance_scale: опциональный, number, 0-20
    guidance_scale = normalized_input.get('guidance_scale')
    if guidance_scale is not None:
        try:
            scale_num = float(guidance_scale)
            if scale_num < 0 or scale_num > 20:
                return False, f"Поле 'guidance_scale' должно быть в диапазоне от 0 до 20 (получено: {guidance_scale})"
            normalized_input['guidance_scale'] = scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'guidance_scale' должно быть числом от 0 до 20 (получено: {guidance_scale})"
    
    # Валидация enable_safety_checker: опциональный, boolean
    enable_safety_checker = normalized_input.get('enable_safety_checker')
    if enable_safety_checker is not None:
        normalized_bool = _normalize_boolean(enable_safety_checker)
        if normalized_bool is None:
            return False, f"Поле 'enable_safety_checker' должно быть boolean (true/false) (получено: {enable_safety_checker})"
        normalized_input['enable_safety_checker'] = normalized_bool
    
    # Валидация output_format: опциональный, enum
    output_format = normalized_input.get('output_format')
    if output_format is not None:
        normalized_format = _normalize_output_format_for_qwen_i2i(output_format)  # Переиспользуем функцию из i2i
        if normalized_format is None:
            return False, f"Поле 'output_format' должно быть одним из: png, jpeg (получено: {output_format})"
        normalized_input['output_format'] = normalized_format
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация acceleration: опциональный, enum
    acceleration = normalized_input.get('acceleration')
    if acceleration is not None:
        normalized_accel = _normalize_acceleration_for_qwen_i2i(acceleration)  # Переиспользуем функцию из i2i
        if normalized_accel is None:
            return False, f"Поле 'acceleration' должно быть одним из: none, regular, high (получено: {acceleration})"
        normalized_input['acceleration'] = normalized_accel
    
    return True, None


def _normalize_image_size_for_google_nano_banana(value: Any) -> Optional[str]:
    """
    Нормализует image_size для google/nano-banana.
    Принимает значение и возвращает нормализованную строку в формате "X:Y" или "auto".
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение image_size (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = [
        "1:1", "9:16", "16:9", "3:4", "4:3", "3:2", "2:3", "5:4", "4:5", "21:9", "auto"
    ]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    return None


def _validate_google_nano_banana(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для google/nano-banana согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - output_format (опциональный, enum, default "png")
    - image_size (опциональный, enum, 11 значений, default "1:1")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["google/nano-banana", "google-nano-banana", "nano-banana"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация output_format: опциональный, enum
    output_format = normalized_input.get('output_format')
    if output_format is not None:
        normalized_format = _normalize_output_format_for_qwen_i2i(output_format)  # Переиспользуем функцию из i2i
        if normalized_format is None:
            return False, f"Поле 'output_format' должно быть одним из: png, jpeg (получено: {output_format})"
        normalized_input['output_format'] = normalized_format
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_google_nano_banana(image_size)
        if normalized_size is None:
            valid_values = [
                "1:1", "9:16", "16:9", "3:4", "4:3", "3:2", "2:3", "5:4", "4:5", "21:9", "auto"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    return True, None


def _validate_google_nano_banana_edit(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для google/nano-banana-edit согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_urls (обязательный, массив URL изображений, до 10 изображений, макс 10MB каждое, форматы: jpeg/png/webp)
    - output_format (опциональный, enum, default "png")
    - image_size (опциональный, enum, 11 значений, default "1:1")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["google/nano-banana-edit", "google-nano-banana-edit", "nano-banana-edit"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для редактирования изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_urls: обязательный, массив URL изображений, до 10 изображений
    image_urls = normalized_input.get('image_urls')
    if not image_urls:
        # Проверяем альтернативные поля
        image_url = normalized_input.get('image_url')
        if image_url:
            # Нормализуем image_url в image_urls
            if isinstance(image_url, str):
                normalized_input['image_urls'] = [image_url]
                image_urls = [image_url]
            elif isinstance(image_url, list):
                normalized_input['image_urls'] = image_url
                image_urls = image_url
            else:
                return False, "Поле 'image_urls' обязательно для редактирования изображения. Загрузите изображение."
        else:
            return False, "Поле 'image_urls' обязательно для редактирования изображения. Загрузите изображение."
    
    # Проверяем что image_urls это массив
    if not isinstance(image_urls, list):
        return False, "Поле 'image_urls' должно быть массивом URL изображений"
    
    # Проверяем количество изображений (до 10)
    if len(image_urls) == 0:
        return False, "Поле 'image_urls' не может быть пустым. Загрузите хотя бы одно изображение."
    if len(image_urls) > 10:
        return False, f"Поле 'image_urls' содержит слишком много изображений: {len(image_urls)} (максимум 10)"
    
    # Проверяем что все элементы - строки (URL)
    for idx, url in enumerate(image_urls):
        if not isinstance(url, str):
            return False, f"Элемент {idx} в 'image_urls' должен быть строкой (URL)"
        if not url.strip():
            return False, f"Элемент {idx} в 'image_urls' не может быть пустым"
    
    normalized_input['image_urls'] = image_urls
    
    # Валидация output_format: опциональный, enum
    output_format = normalized_input.get('output_format')
    if output_format is not None:
        normalized_format = _normalize_output_format_for_qwen_i2i(output_format)  # Переиспользуем функцию из i2i
        if normalized_format is None:
            return False, f"Поле 'output_format' должно быть одним из: png, jpeg (получено: {output_format})"
        normalized_input['output_format'] = normalized_format
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_google_nano_banana(image_size)  # Переиспользуем функцию из t2i
        if normalized_size is None:
            valid_values = [
                "1:1", "9:16", "16:9", "3:4", "4:3", "3:2", "2:3", "5:4", "4:5", "21:9", "auto"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    return True, None


def _normalize_image_size_for_qwen_image_edit(value: Any) -> Optional[str]:
    """
    Нормализует image_size для qwen/image-edit.
    Принимает значение и возвращает нормализованную строку в нижнем регистре с подчеркиваниями.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение image_size (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = [
        "square", "square_hd", "portrait_4_3", "portrait_16_9",
        "landscape_4_3", "landscape_16_9"
    ]
    
    # Проверяем точное совпадение (case-insensitive)
    for valid in valid_values:
        if str_value == valid.lower():
            return valid
    
    return None


def _normalize_num_images_for_qwen_image_edit(value: Any) -> Optional[str]:
    """
    Нормализует num_images для qwen/image-edit.
    Принимает значение и возвращает нормализованную строку.
    ВАЖНО: Поддерживаются только указанные значения из документации (1, 2, 3, 4)!
    
    Args:
        value: Значение num_images (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение
    valid_values = ["1", "2", "3", "4"]
    
    # Проверяем точное совпадение
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать числа
    try:
        num = int(float(str_value))
        if num >= 1 and num <= 4:
            return str(num)
    except (ValueError, TypeError):
        pass
    
    return None


def _validate_qwen_image_edit(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для qwen/image-edit согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 2000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - acceleration (опциональный, enum, default "none")
    - image_size (опциональный, enum, 6 значений, default "landscape_4_3")
    - num_inference_steps (опциональный, number, 2-49, default 25)
    - seed (опциональный, number)
    - guidance_scale (опциональный, number, 0-20, default 4)
    - sync_mode (опциональный, boolean, default false)
    - num_images (опциональный, string enum, default не указан)
    - enable_safety_checker (опциональный, boolean, default true)
    - output_format (опциональный, enum, default "png")
    - negative_prompt (опциональный, string, макс 500 символов, default "blurry, ugly")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["qwen/image-edit", "qwen-image-edit", "qwen/edit"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 2000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для редактирования изображения. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 2000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 2000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для редактирования изображения. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация acceleration: опциональный, enum
    acceleration = normalized_input.get('acceleration')
    if acceleration is not None:
        normalized_accel = _normalize_acceleration_for_qwen_i2i(acceleration)  # Переиспользуем функцию из i2i
        if normalized_accel is None:
            return False, f"Поле 'acceleration' должно быть одним из: none, regular, high (получено: {acceleration})"
        normalized_input['acceleration'] = normalized_accel
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_qwen_image_edit(image_size)
        if normalized_size is None:
            valid_values = [
                "square", "square_hd", "portrait_4_3", "portrait_16_9",
                "landscape_4_3", "landscape_16_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация num_inference_steps: опциональный, number, 2-49
    num_inference_steps = normalized_input.get('num_inference_steps')
    if num_inference_steps is not None:
        try:
            steps_num = int(float(num_inference_steps))
            if steps_num < 2 or steps_num > 49:
                return False, f"Поле 'num_inference_steps' должно быть в диапазоне от 2 до 49 (получено: {num_inference_steps})"
            normalized_input['num_inference_steps'] = steps_num
        except (ValueError, TypeError):
            return False, f"Поле 'num_inference_steps' должно быть числом от 2 до 49 (получено: {num_inference_steps})"
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация guidance_scale: опциональный, number, 0-20
    guidance_scale = normalized_input.get('guidance_scale')
    if guidance_scale is not None:
        try:
            scale_num = float(guidance_scale)
            if scale_num < 0 or scale_num > 20:
                return False, f"Поле 'guidance_scale' должно быть в диапазоне от 0 до 20 (получено: {guidance_scale})"
            normalized_input['guidance_scale'] = scale_num
        except (ValueError, TypeError):
            return False, f"Поле 'guidance_scale' должно быть числом от 0 до 20 (получено: {guidance_scale})"
    
    # Валидация sync_mode: опциональный, boolean
    sync_mode = normalized_input.get('sync_mode')
    if sync_mode is not None:
        normalized_bool = _normalize_boolean(sync_mode)
        if normalized_bool is None:
            return False, f"Поле 'sync_mode' должно быть boolean (true/false) (получено: {sync_mode})"
        normalized_input['sync_mode'] = normalized_bool
    
    # Валидация num_images: опциональный, string enum
    num_images = normalized_input.get('num_images')
    if num_images is not None:
        normalized_num = _normalize_num_images_for_qwen_image_edit(num_images)
        if normalized_num is None:
            return False, f"Поле 'num_images' должно быть одним из: 1, 2, 3, 4 (получено: {num_images})"
        normalized_input['num_images'] = normalized_num
    
    # Валидация enable_safety_checker: опциональный, boolean
    enable_safety_checker = normalized_input.get('enable_safety_checker')
    if enable_safety_checker is not None:
        normalized_bool = _normalize_boolean(enable_safety_checker)
        if normalized_bool is None:
            return False, f"Поле 'enable_safety_checker' должно быть boolean (true/false) (получено: {enable_safety_checker})"
        normalized_input['enable_safety_checker'] = normalized_bool
    
    # Валидация output_format: опциональный, enum
    output_format = normalized_input.get('output_format')
    if output_format is not None:
        # Для qwen/image-edit используется jpeg, а не jpg
        str_format = str(output_format).strip().lower()
        if str_format == "jpg":
            str_format = "jpeg"
        if str_format not in ["png", "jpeg"]:
            return False, f"Поле 'output_format' должно быть одним из: png, jpeg (получено: {output_format})"
        normalized_input['output_format'] = str_format
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    return True, None


def _normalize_rendering_speed_for_ideogram_character_edit(value: Any) -> Optional[str]:
    """
    Нормализует rendering_speed для ideogram/character-edit.
    Принимает значение и возвращает нормализованную строку в верхнем регистре.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение rendering_speed (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы, конвертируем в верхний регистр
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["TURBO", "BALANCED", "QUALITY"]
    
    # Проверяем точное совпадение
    if str_value in valid_values:
        return str_value
    
    return None


def _normalize_style_for_ideogram_character_edit(value: Any) -> Optional[str]:
    """
    Нормализует style для ideogram/character-edit.
    Принимает значение и возвращает нормализованную строку в верхнем регистре.
    ВАЖНО: Поддерживаются только указанные значения из документации!
    
    Args:
        value: Значение style (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы, конвертируем в верхний регистр
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["AUTO", "REALISTIC", "FICTION"]
    
    # Проверяем точное совпадение
    if str_value in valid_values:
        return str_value
    
    return None


def _validate_ideogram_character_edit(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для ideogram/character-edit согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - mask_url (обязательный, макс 10MB, jpeg/png/webp)
    - reference_image_urls (обязательный, массив, макс 10MB общий размер, jpeg/png/webp, только 1 изображение поддерживается)
    - rendering_speed (опциональный, enum, default "BALANCED")
    - style (опциональный, enum, default "AUTO")
    - expand_prompt (опциональный, boolean, default true)
    - num_images (опциональный, string enum, default "1")
    - seed (опциональный, number)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["ideogram/character-edit", "ideogram-character-edit", "character-edit"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для редактирования персонажа. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для редактирования персонажа. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация mask_url: обязательный, string
    mask_url = normalized_input.get('mask_url')
    if not mask_url:
        return False, "Поле 'mask_url' обязательно для редактирования персонажа. Укажите URL маски."
    
    if not isinstance(mask_url, str):
        mask_url = str(mask_url)
    
    mask_url = mask_url.strip()
    if len(mask_url) == 0:
        return False, "Поле 'mask_url' не может быть пустым"
    
    normalized_input['mask_url'] = mask_url
    
    # Валидация reference_image_urls: обязательный, массив
    reference_image_urls = normalized_input.get('reference_image_urls')
    if not reference_image_urls:
        return False, "Поле 'reference_image_urls' обязательно для редактирования персонажа. Укажите массив URL изображений-референсов."
    
    # Проверяем что reference_image_urls это массив
    if not isinstance(reference_image_urls, list):
        return False, "Поле 'reference_image_urls' должно быть массивом URL изображений"
    
    # Проверяем количество изображений (минимум 1, но только 1 поддерживается)
    if len(reference_image_urls) == 0:
        return False, "Поле 'reference_image_urls' не может быть пустым. Укажите хотя бы одно изображение-референс."
    
    # Проверяем что все элементы - строки (URL)
    for idx, url in enumerate(reference_image_urls):
        if not isinstance(url, str):
            return False, f"Элемент {idx} в 'reference_image_urls' должен быть строкой (URL)"
        if not url.strip():
            return False, f"Элемент {idx} в 'reference_image_urls' не может быть пустым"
    
    # ВАЖНО: Только 1 изображение поддерживается, остальные игнорируются
    if len(reference_image_urls) > 1:
        # Предупреждение: используем только первое изображение
        reference_image_urls = [reference_image_urls[0]]
    
    normalized_input['reference_image_urls'] = reference_image_urls
    
    # Валидация rendering_speed: опциональный, enum
    rendering_speed = normalized_input.get('rendering_speed')
    if rendering_speed is not None:
        normalized_speed = _normalize_rendering_speed_for_ideogram_character_edit(rendering_speed)
        if normalized_speed is None:
            return False, f"Поле 'rendering_speed' должно быть одним из: TURBO, BALANCED, QUALITY (получено: {rendering_speed})"
        normalized_input['rendering_speed'] = normalized_speed
    
    # Валидация style: опциональный, enum
    style = normalized_input.get('style')
    if style is not None:
        normalized_style = _normalize_style_for_ideogram_character_edit(style)
        if normalized_style is None:
            return False, f"Поле 'style' должно быть одним из: AUTO, REALISTIC, FICTION (получено: {style})"
        normalized_input['style'] = normalized_style
    
    # Валидация expand_prompt: опциональный, boolean
    expand_prompt = normalized_input.get('expand_prompt')
    if expand_prompt is not None:
        normalized_bool = _normalize_boolean(expand_prompt)
        if normalized_bool is None:
            return False, f"Поле 'expand_prompt' должно быть boolean (true/false) (получено: {expand_prompt})"
        normalized_input['expand_prompt'] = normalized_bool
    
    # Валидация num_images: опциональный, string enum
    num_images = normalized_input.get('num_images')
    if num_images is not None:
        # Переиспользуем функцию из qwen/image-edit
        normalized_num = _normalize_num_images_for_qwen_image_edit(num_images)
        if normalized_num is None:
            return False, f"Поле 'num_images' должно быть одним из: 1, 2, 3, 4 (получено: {num_images})"
        normalized_input['num_images'] = normalized_num
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    return True, None


def _validate_ideogram_character_remix(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для ideogram/character-remix согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - reference_image_urls (обязательный, массив, макс 10MB общий размер, jpeg/png/webp, только 1 изображение поддерживается)
    - rendering_speed (опциональный, enum, default "BALANCED")
    - style (опциональный, enum, default "AUTO")
    - expand_prompt (опциональный, boolean, default true)
    - image_size (опциональный, enum, 6 значений, default "square_hd")
    - num_images (опциональный, string enum, default "1")
    - seed (опциональный, number)
    - strength (опциональный, number, 0.1-1, default 0.8)
    - negative_prompt (опциональный, string, макс 500 символов, default "")
    - image_urls (опциональный, массив, макс 10MB общий размер, jpeg/png/webp, default [])
    - reference_mask_urls (опциональный, string, макс 10MB, jpeg/png/webp, default "")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["ideogram/character-remix", "ideogram-character-remix", "character-remix"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для ремикса персонажа. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для ремикса персонажа. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация reference_image_urls: обязательный, массив
    reference_image_urls = normalized_input.get('reference_image_urls')
    if not reference_image_urls:
        return False, "Поле 'reference_image_urls' обязательно для ремикса персонажа. Укажите массив URL изображений-референсов."
    
    # Проверяем что reference_image_urls это массив
    if not isinstance(reference_image_urls, list):
        return False, "Поле 'reference_image_urls' должно быть массивом URL изображений"
    
    # Проверяем количество изображений (минимум 1, но только 1 поддерживается)
    if len(reference_image_urls) == 0:
        return False, "Поле 'reference_image_urls' не может быть пустым. Укажите хотя бы одно изображение-референс."
    
    # Проверяем что все элементы - строки (URL)
    for idx, url in enumerate(reference_image_urls):
        if not isinstance(url, str):
            return False, f"Элемент {idx} в 'reference_image_urls' должен быть строкой (URL)"
        if not url.strip():
            return False, f"Элемент {idx} в 'reference_image_urls' не может быть пустым"
    
    # ВАЖНО: Только 1 изображение поддерживается, остальные игнорируются
    if len(reference_image_urls) > 1:
        # Предупреждение: используем только первое изображение
        reference_image_urls = [reference_image_urls[0]]
    
    normalized_input['reference_image_urls'] = reference_image_urls
    
    # Валидация rendering_speed: опциональный, enum
    rendering_speed = normalized_input.get('rendering_speed')
    if rendering_speed is not None:
        normalized_speed = _normalize_rendering_speed_for_ideogram_character_edit(rendering_speed)  # Переиспользуем функцию
        if normalized_speed is None:
            return False, f"Поле 'rendering_speed' должно быть одним из: TURBO, BALANCED, QUALITY (получено: {rendering_speed})"
        normalized_input['rendering_speed'] = normalized_speed
    
    # Валидация style: опциональный, enum
    style = normalized_input.get('style')
    if style is not None:
        normalized_style = _normalize_style_for_ideogram_character_edit(style)  # Переиспользуем функцию
        if normalized_style is None:
            return False, f"Поле 'style' должно быть одним из: AUTO, REALISTIC, FICTION (получено: {style})"
        normalized_input['style'] = normalized_style
    
    # Валидация expand_prompt: опциональный, boolean
    expand_prompt = normalized_input.get('expand_prompt')
    if expand_prompt is not None:
        normalized_bool = _normalize_boolean(expand_prompt)
        if normalized_bool is None:
            return False, f"Поле 'expand_prompt' должно быть boolean (true/false) (получено: {expand_prompt})"
        normalized_input['expand_prompt'] = normalized_bool
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_qwen_image_edit(image_size)  # Переиспользуем функцию
        if normalized_size is None:
            valid_values = [
                "square", "square_hd", "portrait_4_3", "portrait_16_9",
                "landscape_4_3", "landscape_16_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация num_images: опциональный, string enum
    num_images = normalized_input.get('num_images')
    if num_images is not None:
        normalized_num = _normalize_num_images_for_qwen_image_edit(num_images)  # Переиспользуем функцию
        if normalized_num is None:
            return False, f"Поле 'num_images' должно быть одним из: 1, 2, 3, 4 (получено: {num_images})"
        normalized_input['num_images'] = normalized_num
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация strength: опциональный, number, 0.1-1
    strength = normalized_input.get('strength')
    if strength is not None:
        try:
            strength_num = float(strength)
            if strength_num < 0.1 or strength_num > 1:
                return False, f"Поле 'strength' должно быть в диапазоне от 0.1 до 1 (получено: {strength})"
            normalized_input['strength'] = strength_num
        except (ValueError, TypeError):
            return False, f"Поле 'strength' должно быть числом от 0.1 до 1 (получено: {strength})"
    
    # Валидация negative_prompt: опциональный, string, макс 500 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 500:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 500)"
        normalized_input['negative_prompt'] = negative_prompt
    
    # Валидация image_urls: опциональный, массив
    image_urls = normalized_input.get('image_urls')
    if image_urls is not None:
        # Проверяем что image_urls это массив
        if not isinstance(image_urls, list):
            return False, "Поле 'image_urls' должно быть массивом URL изображений"
        
        # Проверяем что все элементы - строки (URL)
        for idx, url in enumerate(image_urls):
            if not isinstance(url, str):
                return False, f"Элемент {idx} в 'image_urls' должен быть строкой (URL)"
            if not url.strip():
                return False, f"Элемент {idx} в 'image_urls' не может быть пустым"
        
        normalized_input['image_urls'] = image_urls
    
    # Валидация reference_mask_urls: опциональный, string
    reference_mask_urls = normalized_input.get('reference_mask_urls')
    if reference_mask_urls is not None:
        if not isinstance(reference_mask_urls, str):
            reference_mask_urls = str(reference_mask_urls)
        
        reference_mask_urls = reference_mask_urls.strip()
        # Может быть пустой строкой (default "")
        normalized_input['reference_mask_urls'] = reference_mask_urls
    
    return True, None


def _validate_ideogram_character(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для ideogram/character согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 5000 символов)
    - reference_image_urls (обязательный, массив, макс 10MB общий размер, jpeg/png/webp, только 1 изображение поддерживается)
    - rendering_speed (опциональный, enum, default "BALANCED")
    - style (опциональный, enum, default "AUTO")
    - expand_prompt (опциональный, boolean, default true)
    - num_images (опциональный, string enum, default "1")
    - image_size (опциональный, enum, 6 значений, default "square_hd")
    - seed (опциональный, number)
    - negative_prompt (опциональный, string, макс 5000 символов, default "")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["ideogram/character", "ideogram-character", "character"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации персонажа. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация reference_image_urls: обязательный, массив
    reference_image_urls = normalized_input.get('reference_image_urls')
    if not reference_image_urls:
        return False, "Поле 'reference_image_urls' обязательно для генерации персонажа. Укажите массив URL изображений-референсов."
    
    # Проверяем что reference_image_urls это массив
    if not isinstance(reference_image_urls, list):
        return False, "Поле 'reference_image_urls' должно быть массивом URL изображений"
    
    # Проверяем количество изображений (минимум 1, но только 1 поддерживается)
    if len(reference_image_urls) == 0:
        return False, "Поле 'reference_image_urls' не может быть пустым. Укажите хотя бы одно изображение-референс."
    
    # Проверяем что все элементы - строки (URL)
    for idx, url in enumerate(reference_image_urls):
        if not isinstance(url, str):
            return False, f"Элемент {idx} в 'reference_image_urls' должен быть строкой (URL)"
        if not url.strip():
            return False, f"Элемент {idx} в 'reference_image_urls' не может быть пустым"
    
    # ВАЖНО: Только 1 изображение поддерживается, остальные игнорируются
    if len(reference_image_urls) > 1:
        # Предупреждение: используем только первое изображение
        reference_image_urls = [reference_image_urls[0]]
    
    normalized_input['reference_image_urls'] = reference_image_urls
    
    # Валидация rendering_speed: опциональный, enum
    rendering_speed = normalized_input.get('rendering_speed')
    if rendering_speed is not None:
        normalized_speed = _normalize_rendering_speed_for_ideogram_character_edit(rendering_speed)  # Переиспользуем функцию
        if normalized_speed is None:
            return False, f"Поле 'rendering_speed' должно быть одним из: TURBO, BALANCED, QUALITY (получено: {rendering_speed})"
        normalized_input['rendering_speed'] = normalized_speed
    
    # Валидация style: опциональный, enum
    style = normalized_input.get('style')
    if style is not None:
        normalized_style = _normalize_style_for_ideogram_character_edit(style)  # Переиспользуем функцию
        if normalized_style is None:
            return False, f"Поле 'style' должно быть одним из: AUTO, REALISTIC, FICTION (получено: {style})"
        normalized_input['style'] = normalized_style
    
    # Валидация expand_prompt: опциональный, boolean
    expand_prompt = normalized_input.get('expand_prompt')
    if expand_prompt is not None:
        normalized_bool = _normalize_boolean(expand_prompt)
        if normalized_bool is None:
            return False, f"Поле 'expand_prompt' должно быть boolean (true/false) (получено: {expand_prompt})"
        normalized_input['expand_prompt'] = normalized_bool
    
    # Валидация num_images: опциональный, string enum
    num_images = normalized_input.get('num_images')
    if num_images is not None:
        normalized_num = _normalize_num_images_for_qwen_image_edit(num_images)  # Переиспользуем функцию
        if normalized_num is None:
            return False, f"Поле 'num_images' должно быть одним из: 1, 2, 3, 4 (получено: {num_images})"
        normalized_input['num_images'] = normalized_num
    
    # Валидация image_size: опциональный, enum
    image_size = normalized_input.get('image_size')
    if image_size is not None:
        normalized_size = _normalize_image_size_for_qwen_image_edit(image_size)  # Переиспользуем функцию
        if normalized_size is None:
            valid_values = [
                "square", "square_hd", "portrait_4_3", "portrait_16_9",
                "landscape_4_3", "landscape_16_9"
            ]
            return False, f"Поле 'image_size' должно быть одним из: {', '.join(valid_values)} (получено: {image_size})"
        normalized_input['image_size'] = normalized_size
    
    # Валидация seed: опциональный, number
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (получено: {seed})"
    
    # Валидация negative_prompt: опциональный, string, макс 5000 символов
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        negative_prompt = negative_prompt.strip()
        if len(negative_prompt) > 5000:
            return False, f"Поле 'negative_prompt' слишком длинное: {len(negative_prompt)} символов (максимум 5000)"
        normalized_input['negative_prompt'] = negative_prompt
    
    return True, None


def _validate_bytedance_v1_pro_text_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для bytedance/v1-pro-text-to-video согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 10000 символов)
    - aspect_ratio (опциональный, enum, включает 21:9, default "16:9")
    - resolution (опциональный, enum, default "720p")
    - duration (опциональный, enum, default "5")
    - camera_fixed (опциональный, boolean, default false)
    - seed (опциональный, number, может быть -1 для случайного, default -1)
    - enable_safety_checker (опциональный, boolean, default true)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["bytedance/v1-pro-text-to-video", "bytedance-v1-pro-text-to-video", "v1-pro-text-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация aspect_ratio: опциональный, enum (включает 21:9)
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        valid_aspect_ratios = ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]
        if aspect_ratio not in valid_aspect_ratios:
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_aspect_ratios)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = aspect_ratio
    
    # Валидация resolution: опциональный, enum
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        valid_resolutions = ["480p", "720p", "1080p"]
        if resolution not in valid_resolutions:
            return False, f"Поле 'resolution' должно быть одним из: 480p, 720p, 1080p (получено: {resolution})"
        normalized_input['resolution'] = resolution
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    # Валидация camera_fixed: опциональный, boolean
    camera_fixed = normalized_input.get('camera_fixed')
    if camera_fixed is not None:
        normalized_bool = _normalize_boolean(camera_fixed)
        if normalized_bool is None:
            return False, f"Поле 'camera_fixed' должно быть boolean (true/false) (получено: {camera_fixed})"
        normalized_input['camera_fixed'] = normalized_bool
    
    # Валидация seed: опциональный, number (может быть -1 для случайного, default -1)
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            # -1 разрешён для случайного seed, диапазон: -1 до 2147483647
            if seed_num < -1 or seed_num > 2147483647:
                return False, f"Поле 'seed' должно быть в диапазоне от -1 до 2147483647 (получено: {seed})"
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (может быть -1 для случайного) (получено: {seed})"
    
    # Валидация enable_safety_checker: опциональный, boolean
    enable_safety_checker = normalized_input.get('enable_safety_checker')
    if enable_safety_checker is not None:
        normalized_bool = _normalize_boolean(enable_safety_checker)
        if normalized_bool is None:
            return False, f"Поле 'enable_safety_checker' должно быть boolean (true/false) (получено: {enable_safety_checker})"
        normalized_input['enable_safety_checker'] = normalized_bool
    
    return True, None


def _validate_bytedance_v1_lite_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для bytedance/v1-lite-image-to-video согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 10000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - resolution (опциональный, enum, default "720p")
    - duration (опциональный, enum, default "5")
    - camera_fixed (опциональный, boolean, default false)
    - seed (опциональный, number, может быть -1 для случайного, default -1)
    - enable_safety_checker (опциональный, boolean, default true)
    - end_image_url (опциональный, string, макс 10MB, jpeg/png/webp, default "")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["bytedance/v1-lite-image-to-video", "bytedance-v1-lite-image-to-video", "v1-lite-image-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация resolution: опциональный, enum
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        valid_resolutions = ["480p", "720p", "1080p"]
        if resolution not in valid_resolutions:
            return False, f"Поле 'resolution' должно быть одним из: 480p, 720p, 1080p (получено: {resolution})"
        normalized_input['resolution'] = resolution
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    # Валидация camera_fixed: опциональный, boolean
    camera_fixed = normalized_input.get('camera_fixed')
    if camera_fixed is not None:
        normalized_bool = _normalize_boolean(camera_fixed)
        if normalized_bool is None:
            return False, f"Поле 'camera_fixed' должно быть boolean (true/false) (получено: {camera_fixed})"
        normalized_input['camera_fixed'] = normalized_bool
    
    # Валидация seed: опциональный, number (может быть -1 для случайного, default -1)
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            # -1 разрешён для случайного seed, диапазон: -1 до 2147483647
            if seed_num < -1 or seed_num > 2147483647:
                return False, f"Поле 'seed' должно быть в диапазоне от -1 до 2147483647 (получено: {seed})"
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (может быть -1 для случайного) (получено: {seed})"
    
    # Валидация enable_safety_checker: опциональный, boolean
    enable_safety_checker = normalized_input.get('enable_safety_checker')
    if enable_safety_checker is not None:
        normalized_bool = _normalize_boolean(enable_safety_checker)
        if normalized_bool is None:
            return False, f"Поле 'enable_safety_checker' должно быть boolean (true/false) (получено: {enable_safety_checker})"
        normalized_input['enable_safety_checker'] = normalized_bool
    
    # Валидация end_image_url: опциональный, string
    end_image_url = normalized_input.get('end_image_url')
    if end_image_url is not None:
        if not isinstance(end_image_url, str):
            end_image_url = str(end_image_url)
        
        end_image_url = end_image_url.strip()
        # Может быть пустой строкой (default "")
        normalized_input['end_image_url'] = end_image_url
    
    return True, None


def _validate_bytedance_v1_pro_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для bytedance/v1-pro-image-to-video согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 10000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - resolution (опциональный, enum, default "720p")
    - duration (опциональный, enum, default "5")
    - camera_fixed (опциональный, boolean, default false)
    - seed (опциональный, number, может быть -1 для случайного, default -1)
    - enable_safety_checker (опциональный, boolean, default true)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["bytedance/v1-pro-image-to-video", "bytedance-v1-pro-image-to-video", "v1-pro-image-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация resolution: опциональный, enum
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        valid_resolutions = ["480p", "720p", "1080p"]
        if resolution not in valid_resolutions:
            return False, f"Поле 'resolution' должно быть одним из: 480p, 720p, 1080p (получено: {resolution})"
        normalized_input['resolution'] = resolution
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    # Валидация camera_fixed: опциональный, boolean
    camera_fixed = normalized_input.get('camera_fixed')
    if camera_fixed is not None:
        normalized_bool = _normalize_boolean(camera_fixed)
        if normalized_bool is None:
            return False, f"Поле 'camera_fixed' должно быть boolean (true/false) (получено: {camera_fixed})"
        normalized_input['camera_fixed'] = normalized_bool
    
    # Валидация seed: опциональный, number (может быть -1 для случайного, default -1)
    seed = normalized_input.get('seed')
    if seed is not None:
        try:
            seed_num = int(float(seed))
            # -1 разрешён для случайного seed, диапазон: -1 до 2147483647
            if seed_num < -1 or seed_num > 2147483647:
                return False, f"Поле 'seed' должно быть в диапазоне от -1 до 2147483647 (получено: {seed})"
            normalized_input['seed'] = seed_num
        except (ValueError, TypeError):
            return False, f"Поле 'seed' должно быть числом (может быть -1 для случайного) (получено: {seed})"
    
    # Валидация enable_safety_checker: опциональный, boolean
    enable_safety_checker = normalized_input.get('enable_safety_checker')
    if enable_safety_checker is not None:
        normalized_bool = _normalize_boolean(enable_safety_checker)
        if normalized_bool is None:
            return False, f"Поле 'enable_safety_checker' должно быть boolean (true/false) (получено: {enable_safety_checker})"
        normalized_input['enable_safety_checker'] = normalized_bool
    
    return True, None


def _validate_bytedance_v1_pro_fast_image_to_video_updated(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для bytedance/v1-pro-fast-image-to-video согласно документации API.
    
    ВАЖНО: Эта модель имеет специфичные параметры:
    - prompt (обязательный, макс 10000 символов)
    - image_url (обязательный, макс 10MB, jpeg/png/webp)
    - resolution (опциональный, enum, только 720p/1080p, НЕТ 480p!, default "720p")
    - duration (опциональный, enum, default "5")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["bytedance/v1-pro-fast-image-to-video", "bytedance-v1-pro-fast-image-to-video", "v1-pro-fast-image-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео. Введите текстовое описание."
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация image_url: обязательный, string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения."
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Валидация resolution: опциональный, enum (только 720p/1080p, НЕТ 480p!)
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        valid_resolutions = ["720p", "1080p"]  # ВАЖНО: только 2 значения, НЕТ 480p!
        if resolution not in valid_resolutions:
            return False, f"Поле 'resolution' должно быть одним из: 720p, 1080p (получено: {resolution})"
        normalized_input['resolution'] = resolution
    
    # Валидация duration: опциональный, enum
    duration = normalized_input.get('duration')
    if duration is not None:
        # Может быть строкой "5" или "10", или числом 5 или 10
        if isinstance(duration, str):
            if duration not in ["5", "10"]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = duration
        elif isinstance(duration, (int, float)):
            if duration not in [5, 10]:
                return False, f"Поле 'duration' должно быть одним из: 5, 10 (получено: {duration})"
            normalized_input['duration'] = str(int(duration))
        else:
            return False, f"Поле 'duration' должно быть строкой или числом (получено: {duration})"
    
    return True, None


def _normalize_resolution_for_hailuo_2_3_pro(value: Any) -> Optional[str]:
    """
    Нормализует resolution для hailuo/2-3-image-to-video-pro.
    Принимает строку и возвращает нормализованное значение в верхнем регистре.
    ВАЖНО: Для hailuo/2-3-image-to-video-pro поддерживаются только "768P" и "1080P"!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["768P", "1080P"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["768p", "768", "768p"]:
        return "768P"
    elif str_lower in ["1080p", "1080", "1080p", "fullhd", "fhd"]:
        return "1080P"
    
    return None


def _normalize_resolution_for_hailuo_02_standard(value: Any) -> Optional[str]:
    """
    Нормализует resolution для hailuo/02-image-to-video-standard.
    Принимает строку и возвращает нормализованное значение в верхнем регистре.
    ВАЖНО: Для hailuo/02-image-to-video-standard поддерживаются только "512P" и "768P"!
    
    Args:
        value: Значение resolution (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().upper()
    
    # Проверяем что это валидное значение
    valid_values = ["512P", "768P"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["512p", "512", "512p"]:
        return "512P"
    elif str_lower in ["768p", "768", "768p"]:
        return "768P"
    
    return None


def _normalize_duration_for_hailuo_2_3_pro(value: Any) -> Optional[str]:
    """
    Нормализует duration для hailuo/2-3-image-to-video-pro.
    Принимает значение и возвращает нормализованную строку.
    ВАЖНО: Для hailuo/2-3-image-to-video-pro поддерживаются только "6" и "10"!
    
    Args:
        value: Значение duration (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение
    valid_values = ["6", "10"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["6", "6s", "6sec", "6 seconds"]:
        return "6"
    elif str_lower in ["10", "10s", "10sec", "10 seconds"]:
        return "10"
    
    return None


def _validate_hailuo_02_image_to_video_standard(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для hailuo/02-image-to-video-standard согласно документации API.
    
    ВАЖНО: Отличается от hailuo/02-image-to-video-pro:
    - Есть параметры duration ("6" | "10", default "10") и resolution ("512P" | "768P", default "768P")
    - end_image_url имеет default значение (в отличие от pro версии, где default "")
    - 10 секундные видео не поддерживаются для 1080p разрешения (но здесь нет 1080p)
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["hailuo/02-image-to-video-standard", "hailuo/02-i2v-standard", "hailuo/0.2-image-to-video-standard"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 1500 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 1500:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 1500)"
    
    # Валидация image_url: обязательный string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения"
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if not image_url:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not image_url.startswith(('http://', 'https://')):
        return False, "Поле 'image_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['image_url'] = image_url
    
    # ВАЖНО: Удаляем image_urls если он был передан (для этой модели нужен только image_url как string!)
    if 'image_urls' in normalized_input:
        logger.warning(f"Parameter 'image_urls' is not supported for hailuo/02-image-to-video-standard (use 'image_url' as string), removing it")
        del normalized_input['image_urls']
    
    # Валидация end_image_url: опциональный string
    end_image_url = normalized_input.get('end_image_url')
    if end_image_url is not None:
        if not isinstance(end_image_url, str):
            end_image_url = str(end_image_url)
        
        end_image_url = end_image_url.strip()
        # Если пустая строка, удаляем параметр
        if not end_image_url:
            del normalized_input['end_image_url']
        else:
            # Проверяем что это валидный URL
            if not end_image_url.startswith(('http://', 'https://')):
                return False, "Поле 'end_image_url' должно быть валидным URL (начинается с http:// или https://)"
            normalized_input['end_image_url'] = end_image_url
    
    # Валидация duration: опциональный, "6" | "10", default "10"
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_hailuo_2_3_pro(duration)  # Переиспользуем функцию (те же значения "6" и "10")
        if normalized_duration is None:
            valid_values = ["6", "10"]
            return False, f"Поле 'duration' должно быть одним из: {', '.join(valid_values)} (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация resolution: опциональный, "512P" | "768P", default "768P"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_hailuo_02_standard(resolution)
        if normalized_resolution is None:
            valid_values = ["512P", "768P"]
            return False, f"Поле 'resolution' должно быть одним из: {', '.join(valid_values)} (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    # Валидация prompt_optimizer: опциональный boolean
    prompt_optimizer = normalized_input.get('prompt_optimizer')
    if prompt_optimizer is not None:
        normalized_bool = _normalize_boolean(prompt_optimizer)
        if normalized_bool is None:
            return False, f"Поле 'prompt_optimizer' должно быть boolean (true/false) (получено: {prompt_optimizer})"
        normalized_input['prompt_optimizer'] = normalized_bool
    
    return True, None


def _validate_hailuo_02_image_to_video_pro(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для hailuo/02-image-to-video-pro согласно документации API.
    
    ВАЖНО: Отличается от других hailuo моделей:
    - prompt максимум 1500 символов (меньше чем у других)
    - Есть параметр end_image_url (опциональный string)
    - Есть параметр prompt_optimizer (boolean)
    - НЕТ параметров duration, resolution и других
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id not in ["hailuo/02-image-to-video-pro", "hailuo/02-i2v-pro", "hailuo/0.2-image-to-video-pro"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 1500 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 1500:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 1500)"
    
    # Валидация image_url: обязательный string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения"
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if not image_url:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not image_url.startswith(('http://', 'https://')):
        return False, "Поле 'image_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['image_url'] = image_url
    
    # ВАЖНО: Удаляем image_urls если он был передан (для этой модели нужен только image_url как string!)
    if 'image_urls' in normalized_input:
        logger.warning(f"Parameter 'image_urls' is not supported for hailuo/02-image-to-video-pro (use 'image_url' as string), removing it")
        del normalized_input['image_urls']
    
    # Валидация end_image_url: опциональный string
    end_image_url = normalized_input.get('end_image_url')
    if end_image_url is not None:
        if not isinstance(end_image_url, str):
            end_image_url = str(end_image_url)
        
        end_image_url = end_image_url.strip()
        # Если пустая строка, удаляем параметр
        if not end_image_url:
            del normalized_input['end_image_url']
        else:
            # Проверяем что это валидный URL
            if not end_image_url.startswith(('http://', 'https://')):
                return False, "Поле 'end_image_url' должно быть валидным URL (начинается с http:// или https://)"
            normalized_input['end_image_url'] = end_image_url
    
    # Валидация prompt_optimizer: опциональный boolean
    prompt_optimizer = normalized_input.get('prompt_optimizer')
    if prompt_optimizer is not None:
        normalized_bool = _normalize_boolean(prompt_optimizer)
        if normalized_bool is None:
            return False, f"Поле 'prompt_optimizer' должно быть boolean (true/false) (получено: {prompt_optimizer})"
        normalized_input['prompt_optimizer'] = normalized_bool
    
    return True, None


def _validate_hailuo_2_3_image_to_video_pro(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для hailuo/2-3-image-to-video-pro согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["hailuo/2-3-image-to-video-pro", "hailuo/2-3-i2v-pro"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, строка (не массив!)
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Загрузите изображение"
    
    if not isinstance(image_url, str):
        # Если передан массив, берем первый элемент
        if isinstance(image_url, list) and len(image_url) > 0:
            image_url = str(image_url[0])
        else:
            image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Базовая валидация URL
    if not (image_url.startswith('http://') or image_url.startswith('https://')):
        return False, f"Поле 'image_url' должно быть валидным URL (начинаться с http:// или https://). Получено: {image_url[:50]}..."
    
    normalized_input['image_url'] = image_url
    
    # Валидация duration: опциональный, enum ("6" или "10")
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_hailuo_2_3_pro(duration)
        if normalized_duration is None:
            return False, f"Поле 'duration' должно быть '6' или '10' (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация resolution: опциональный, enum ("768P" или "1080P")
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_hailuo_2_3_pro(resolution)
        if normalized_resolution is None:
            valid_values = ["768P", "1080P"]
            return False, f"Поле 'resolution' должно быть одним из: {', '.join(valid_values)} (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    # ВАЖНО: Проверяем взаимоисключающие значения
    # Если resolution="1080P", то duration не может быть "10"!
    final_resolution = normalized_input.get('resolution', "768P")  # Default "768P"
    final_duration = normalized_input.get('duration', "6")  # Default "6"
    
    if final_resolution == "1080P" and final_duration == "10":
        return False, "Для разрешения '1080P' не поддерживается длительность '10' секунд. Используйте duration='6' или resolution='768P'"
    
    return True, None


def _validate_hailuo_2_3_image_to_video_standard(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для hailuo/2-3-image-to-video-standard согласно документации API.
    
    ВАЖНО: Параметры идентичны hailuo/2-3-image-to-video-pro, но это другая модель!
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["hailuo/2-3-image-to-video-standard", "hailuo/2-3-i2v-standard"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация image_url: обязательный, строка (не массив!)
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Загрузите изображение"
    
    if not isinstance(image_url, str):
        # Если передан массив, берем первый элемент
        if isinstance(image_url, list) and len(image_url) > 0:
            image_url = str(image_url[0])
        else:
            image_url = str(image_url)
    
    image_url = image_url.strip()
    if len(image_url) == 0:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Базовая валидация URL
    if not (image_url.startswith('http://') or image_url.startswith('https://')):
        return False, f"Поле 'image_url' должно быть валидным URL (начинаться с http:// или https://). Получено: {image_url[:50]}..."
    
    normalized_input['image_url'] = image_url
    
    # Валидация duration: опциональный, enum ("6" или "10")
    # Переиспользуем функцию нормализации из hailuo/2-3-image-to-video-pro
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_hailuo_2_3_pro(duration)
        if normalized_duration is None:
            return False, f"Поле 'duration' должно быть '6' или '10' (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация resolution: опциональный, enum ("768P" или "1080P")
    # Переиспользуем функцию нормализации из hailuo/2-3-image-to-video-pro
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_hailuo_2_3_pro(resolution)
        if normalized_resolution is None:
            valid_values = ["768P", "1080P"]
            return False, f"Поле 'resolution' должно быть одним из: {', '.join(valid_values)} (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    # ВАЖНО: Проверяем взаимоисключающие значения
    # Если resolution="1080P", то duration не может быть "10"!
    final_resolution = normalized_input.get('resolution', "768P")  # Default "768P"
    final_duration = normalized_input.get('duration', "6")  # Default "6"
    
    if final_resolution == "1080P" and final_duration == "10":
        return False, "Для разрешения '1080P' не поддерживается длительность '10' секунд. Используйте duration='6' или resolution='768P'"
    
    return True, None


def _normalize_n_frames_for_sora_2_pro_storyboard(value: Any) -> Optional[str]:
    """
    Нормализует n_frames для sora-2-pro-storyboard.
    Принимает значение и возвращает нормализованную строку.
    ВАЖНО: Для sora-2-pro-storyboard поддерживаются только "10", "15", "25"!
    
    Args:
        value: Значение n_frames (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение
    valid_values = ["10", "15", "25"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["10", "10s", "10sec", "10 seconds"]:
        return "10"
    elif str_lower in ["15", "15s", "15sec", "15 seconds"]:
        return "15"
    elif str_lower in ["25", "25s", "25sec", "25 seconds"]:
        return "25"
    
    # Пробуем конвертировать число в строку
    try:
        num_value = float(str_value)
        if num_value == 10.0 or num_value == 10:
            return "10"
        elif num_value == 15.0 or num_value == 15:
            return "15"
        elif num_value == 25.0 or num_value == 25:
            return "25"
    except (ValueError, TypeError):
        pass
    
    return None


def _normalize_aspect_ratio_for_sora_2_pro_storyboard(value: Any) -> Optional[str]:
    """
    Нормализует aspect_ratio для sora-2-pro-storyboard.
    Принимает строку и возвращает нормализованное значение в нижнем регистре.
    ВАЖНО: Для sora-2-pro-storyboard поддерживаются только "portrait" и "landscape"!
    
    Args:
        value: Значение aspect_ratio (может быть str)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["portrait", "landscape"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    if str_value in ["portrait", "port", "vertical", "vert"]:
        return "portrait"
    elif str_value in ["landscape", "land", "horizontal", "horiz"]:
        return "landscape"
    
    return None


def _validate_sora_2_pro_storyboard(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для sora-2-pro-storyboard согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["sora-2-pro-storyboard", "sora-2-pro/storyboard", "openai/sora-2-pro-storyboard"]:
        return True, None
    
    # Валидация n_frames: обязательный, enum ("10", "15", "25")
    n_frames = normalized_input.get('n_frames')
    if not n_frames:
        return False, "Поле 'n_frames' обязательно для генерации storyboard. Укажите длительность видео: '10', '15' или '25' секунд"
    
    normalized_n_frames = _normalize_n_frames_for_sora_2_pro_storyboard(n_frames)
    if normalized_n_frames is None:
        valid_values = ["10", "15", "25"]
        return False, f"Поле 'n_frames' должно быть одним из: {', '.join(valid_values)} (получено: {n_frames})"
    normalized_input['n_frames'] = normalized_n_frames
    
    # Валидация image_urls: опциональный массив
    image_urls = normalized_input.get('image_urls')
    if image_urls is not None:
        # Нормализуем image_urls
        normalized_image_urls = _normalize_image_urls_for_wan_2_6(image_urls)
        if normalized_image_urls is None:
            return False, "Поле 'image_urls' должно быть массивом валидных URL изображений"
        normalized_input['image_urls'] = normalized_image_urls
    
    # Валидация aspect_ratio: опциональный, enum ("portrait" или "landscape")
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        normalized_aspect_ratio = _normalize_aspect_ratio_for_sora_2_pro_storyboard(aspect_ratio)
        if normalized_aspect_ratio is None:
            valid_values = ["portrait", "landscape"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    return True, None


def _normalize_n_frames_for_sora_2_pro_text_to_video(value: Any) -> Optional[str]:
    """
    Нормализует n_frames для sora-2-pro-text-to-video.
    Принимает значение и возвращает нормализованную строку.
    ВАЖНО: Для sora-2-pro-text-to-video поддерживаются только "10" и "15"!
    (В отличие от storyboard, где также есть "25")
    
    Args:
        value: Значение n_frames (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение
    valid_values = ["10", "15"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["10", "10s", "10sec", "10 seconds"]:
        return "10"
    elif str_lower in ["15", "15s", "15sec", "15 seconds"]:
        return "15"
    
    # Пробуем конвертировать число в строку
    try:
        num_value = float(str_value)
        if num_value == 10.0 or num_value == 10:
            return "10"
        elif num_value == 15.0 or num_value == 15:
            return "15"
    except (ValueError, TypeError):
        pass
    
    return None


def _normalize_size_for_sora_2_pro_text_to_video(value: Any) -> Optional[str]:
    """
    Нормализует size для sora-2-pro-text-to-video.
    Принимает строку и возвращает нормализованное значение в нижнем регистре.
    ВАЖНО: Для sora-2-pro-text-to-video поддерживаются только "standard" и "high"!
    
    Args:
        value: Значение size (может быть str)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip().lower()
    
    # Проверяем что это валидное значение
    valid_values = ["standard", "high"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    if str_value in ["standard", "std", "normal", "medium"]:
        return "standard"
    elif str_value in ["high", "hq", "quality", "best"]:
        return "high"
    
    return None


def _normalize_boolean(value: Any) -> Optional[bool]:
    """
    Нормализует boolean значение.
    Принимает различные форматы и возвращает bool или None.
    
    Args:
        value: Значение (может быть str, bool, int)
    
    Returns:
        bool или None
    """
    if value is None:
        return None
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    if isinstance(value, str):
        str_lower = value.strip().lower()
        if str_lower in ['true', '1', 'yes', 'y', 'on', 'enabled']:
            return True
        elif str_lower in ['false', '0', 'no', 'n', 'off', 'disabled']:
            return False
    
    return None


def _validate_sora_2_pro_text_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для sora-2-pro-text-to-video согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["sora-2-pro-text-to-video", "sora-2-pro/t2v", "openai/sora-2-pro-text-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация aspect_ratio: опциональный, enum ("portrait" или "landscape")
    # Переиспользуем функцию нормализации из sora-2-pro-storyboard
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        normalized_aspect_ratio = _normalize_aspect_ratio_for_sora_2_pro_storyboard(aspect_ratio)
        if normalized_aspect_ratio is None:
            valid_values = ["portrait", "landscape"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация n_frames: опциональный, enum ("10" или "15")
    n_frames = normalized_input.get('n_frames')
    if n_frames is not None:
        normalized_n_frames = _normalize_n_frames_for_sora_2_pro_text_to_video(n_frames)
        if normalized_n_frames is None:
            valid_values = ["10", "15"]
            return False, f"Поле 'n_frames' должно быть одним из: {', '.join(valid_values)} (получено: {n_frames})"
        normalized_input['n_frames'] = normalized_n_frames
    
    # Валидация size: опциональный, enum ("standard" или "high")
    size = normalized_input.get('size')
    if size is not None:
        normalized_size = _normalize_size_for_sora_2_pro_text_to_video(size)
        if normalized_size is None:
            valid_values = ["standard", "high"]
            return False, f"Поле 'size' должно быть одним из: {', '.join(valid_values)} (получено: {size})"
        normalized_input['size'] = normalized_size
    
    # Валидация remove_watermark: опциональный boolean
    remove_watermark = normalized_input.get('remove_watermark')
    if remove_watermark is not None:
        normalized_remove_watermark = _normalize_boolean(remove_watermark)
        if normalized_remove_watermark is None:
            return False, f"Поле 'remove_watermark' должно быть boolean (true/false) (получено: {remove_watermark})"
        normalized_input['remove_watermark'] = normalized_remove_watermark
    
    return True, None


def _validate_sora_2_pro_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для sora-2-pro-image-to-video согласно документации API.
    
    ВАЖНО: Параметры похожи на sora-2-pro-text-to-video, но:
    - image_urls обязательный (в text-to-video его нет)
    - size default "standard" (в text-to-video default "high")
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["sora-2-pro-image-to-video", "sora-2-pro/i2v", "openai/sora-2-pro-image-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация image_urls: обязательный массив
    image_urls = normalized_input.get('image_urls')
    if not image_urls:
        return False, "Поле 'image_urls' обязательно для генерации видео. Загрузите изображение"
    
    # Переиспользуем функцию нормализации из wan/2-6-image-to-video
    normalized_image_urls = _normalize_image_urls_for_wan_2_6(image_urls)
    if normalized_image_urls is None:
        return False, "Поле 'image_urls' должно быть массивом валидных URL изображений"
    normalized_input['image_urls'] = normalized_image_urls
    
    # Валидация aspect_ratio: опциональный, enum ("portrait" или "landscape")
    # Переиспользуем функцию нормализации из sora-2-pro-storyboard
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        normalized_aspect_ratio = _normalize_aspect_ratio_for_sora_2_pro_storyboard(aspect_ratio)
        if normalized_aspect_ratio is None:
            valid_values = ["portrait", "landscape"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация n_frames: опциональный, enum ("10" или "15")
    # Переиспользуем функцию нормализации из sora-2-pro-text-to-video
    n_frames = normalized_input.get('n_frames')
    if n_frames is not None:
        normalized_n_frames = _normalize_n_frames_for_sora_2_pro_text_to_video(n_frames)
        if normalized_n_frames is None:
            valid_values = ["10", "15"]
            return False, f"Поле 'n_frames' должно быть одним из: {', '.join(valid_values)} (получено: {n_frames})"
        normalized_input['n_frames'] = normalized_n_frames
    
    # Валидация size: опциональный, enum ("standard" или "high")
    # Переиспользуем функцию нормализации из sora-2-pro-text-to-video
    size = normalized_input.get('size')
    if size is not None:
        normalized_size = _normalize_size_for_sora_2_pro_text_to_video(size)
        if normalized_size is None:
            valid_values = ["standard", "high"]
            return False, f"Поле 'size' должно быть одним из: {', '.join(valid_values)} (получено: {size})"
        normalized_input['size'] = normalized_size
    
    # Валидация remove_watermark: опциональный boolean
    # Переиспользуем функцию нормализации из sora-2-pro-text-to-video
    remove_watermark = normalized_input.get('remove_watermark')
    if remove_watermark is not None:
        normalized_remove_watermark = _normalize_boolean(remove_watermark)
        if normalized_remove_watermark is None:
            return False, f"Поле 'remove_watermark' должно быть boolean (true/false) (получено: {remove_watermark})"
        normalized_input['remove_watermark'] = normalized_remove_watermark
    
    return True, None


def _validate_sora_2_text_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для sora-2-text-to-video согласно документации API.
    
    ВАЖНО: Отличается от sora-2-pro-text-to-video:
    - НЕТ параметра size (в pro версии есть)
    - Только: prompt, aspect_ratio, n_frames, remove_watermark
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["sora-2-text-to-video", "sora-2/t2v", "openai/sora-2-text-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация aspect_ratio: опциональный, enum ("portrait" или "landscape")
    # Переиспользуем функцию нормализации из sora-2-pro-storyboard
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        normalized_aspect_ratio = _normalize_aspect_ratio_for_sora_2_pro_storyboard(aspect_ratio)
        if normalized_aspect_ratio is None:
            valid_values = ["portrait", "landscape"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация n_frames: опциональный, enum ("10" или "15")
    # Переиспользуем функцию нормализации из sora-2-pro-text-to-video
    n_frames = normalized_input.get('n_frames')
    if n_frames is not None:
        normalized_n_frames = _normalize_n_frames_for_sora_2_pro_text_to_video(n_frames)
        if normalized_n_frames is None:
            valid_values = ["10", "15"]
            return False, f"Поле 'n_frames' должно быть одним из: {', '.join(valid_values)} (получено: {n_frames})"
        normalized_input['n_frames'] = normalized_n_frames
    
    # Валидация remove_watermark: опциональный boolean
    remove_watermark = normalized_input.get('remove_watermark')
    if remove_watermark is not None:
        normalized_remove_watermark = _normalize_boolean(remove_watermark)
        if normalized_remove_watermark is None:
            return False, f"Поле 'remove_watermark' должно быть boolean (true/false) (получено: {remove_watermark})"
        normalized_input['remove_watermark'] = normalized_remove_watermark
    
    # ВАЖНО: Удаляем параметр size если он был передан (в sora-2-text-to-video его нет!)
    if 'size' in normalized_input:
        logger.warning(f"Parameter 'size' is not supported for sora-2-text-to-video (only for pro version), removing it")
        del normalized_input['size']
    
    return True, None


def _validate_sora_2_image_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для sora-2-image-to-video согласно документации API.
    
    ВАЖНО: Отличается от sora-2-pro-image-to-video:
    - НЕТ параметра size (в pro версии есть)
    - Только: prompt, image_urls, aspect_ratio, n_frames, remove_watermark
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["sora-2-image-to-video", "sora-2/i2v", "openai/sora-2-image-to-video"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 10000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 10000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 10000)"
    
    # Валидация image_urls: обязательный массив
    image_urls = normalized_input.get('image_urls')
    if not image_urls:
        return False, "Поле 'image_urls' обязательно для генерации видео. Загрузите изображение"
    
    # Переиспользуем функцию нормализации из wan/2-6-image-to-video
    normalized_image_urls = _normalize_image_urls_for_wan_2_6(image_urls)
    if normalized_image_urls is None:
        return False, "Поле 'image_urls' должно быть массивом валидных URL изображений"
    normalized_input['image_urls'] = normalized_image_urls
    
    # Валидация aspect_ratio: опциональный, enum ("portrait" или "landscape")
    # Переиспользуем функцию нормализации из sora-2-pro-storyboard
    aspect_ratio = normalized_input.get('aspect_ratio')
    if aspect_ratio is not None:
        normalized_aspect_ratio = _normalize_aspect_ratio_for_sora_2_pro_storyboard(aspect_ratio)
        if normalized_aspect_ratio is None:
            valid_values = ["portrait", "landscape"]
            return False, f"Поле 'aspect_ratio' должно быть одним из: {', '.join(valid_values)} (получено: {aspect_ratio})"
        normalized_input['aspect_ratio'] = normalized_aspect_ratio
    
    # Валидация n_frames: опциональный, enum ("10" или "15")
    # Переиспользуем функцию нормализации из sora-2-pro-text-to-video
    n_frames = normalized_input.get('n_frames')
    if n_frames is not None:
        normalized_n_frames = _normalize_n_frames_for_sora_2_pro_text_to_video(n_frames)
        if normalized_n_frames is None:
            valid_values = ["10", "15"]
            return False, f"Поле 'n_frames' должно быть одним из: {', '.join(valid_values)} (получено: {n_frames})"
        normalized_input['n_frames'] = normalized_n_frames
    
    # Валидация remove_watermark: опциональный boolean
    remove_watermark = normalized_input.get('remove_watermark')
    if remove_watermark is not None:
        normalized_remove_watermark = _normalize_boolean(remove_watermark)
        if normalized_remove_watermark is None:
            return False, f"Поле 'remove_watermark' должно быть boolean (true/false) (получено: {remove_watermark})"
        normalized_input['remove_watermark'] = normalized_remove_watermark
    
    # ВАЖНО: Удаляем параметр size если он был передан (в sora-2-image-to-video его нет!)
    if 'size' in normalized_input:
        logger.warning(f"Parameter 'size' is not supported for sora-2-image-to-video (only for pro version), removing it")
        del normalized_input['size']
    
    return True, None


def _validate_wan_2_6_text_to_video(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для wan/2-6-text-to-video согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    if model_id != "wan/2-6-text-to-video":
        return True, None
    
    # Валидация prompt: обязательный, 1-5000 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len < 1:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 5000:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 5000)"
    
    # Валидация duration: опциональный, "5" | "10" | "15", default "5"
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_wan_2_6(duration)
        if normalized_duration is None:
            return False, f"Поле 'duration' должно быть '5', '10' или '15' (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация resolution: опциональный, "720p" | "1080p", default "1080p"
    resolution = normalized_input.get('resolution')
    if resolution is not None:
        normalized_resolution = _normalize_resolution_for_wan_2_6(resolution)
        if normalized_resolution is None:
            return False, f"Поле 'resolution' должно быть '720p' или '1080p' (получено: {resolution})"
        normalized_input['resolution'] = normalized_resolution
    
    return True, None


def _normalize_video_url_for_sora_watermark_remover(video_url: Any) -> Optional[str]:
    """
    Нормализует video_url для sora-watermark-remover.
    
    Args:
        video_url: URL видео (строка или другой тип)
    
    Returns:
        Нормализованный URL или None если невалидный
    """
    if not video_url:
        return None
    
    # Конвертируем в строку
    if not isinstance(video_url, str):
        video_url = str(video_url)
    
    video_url = video_url.strip()
    
    # Проверяем что URL не пустой
    if not video_url:
        return None
    
    # Проверяем максимальную длину (500 символов)
    if len(video_url) > 500:
        return None
    
    # Проверяем что URL начинается с sora.chatgpt.com
    if not video_url.startswith(('https://sora.chatgpt.com/', 'http://sora.chatgpt.com/')):
        return None
    
    return video_url


def _normalize_upscale_factor_for_topaz(value: Any) -> Optional[str]:
    """
    Нормализует upscale_factor для topaz/image-upscale.
    Принимает значение и возвращает нормализованную строку.
    ВАЖНО: Для topaz/image-upscale поддерживаются только "1", "2", "4", "8"!
    
    Args:
        value: Значение upscale_factor (может быть str, int, float)
    
    Returns:
        Нормализованная строка или None
    """
    if value is None:
        return None
    
    # Конвертируем в строку и убираем пробелы
    str_value = str(value).strip()
    
    # Проверяем что это валидное значение
    valid_values = ["1", "2", "4", "8"]
    if str_value in valid_values:
        return str_value
    
    # Пробуем нормализовать варианты написания
    str_lower = str_value.lower()
    if str_lower in ["1", "1x", "1.0", "1.0x"]:
        return "1"
    elif str_lower in ["2", "2x", "2.0", "2.0x"]:
        return "2"
    elif str_lower in ["4", "4x", "4.0", "4.0x"]:
        return "4"
    elif str_lower in ["8", "8x", "8.0", "8.0x"]:
        return "8"
    
    # Пробуем конвертировать число в строку
    try:
        num_value = float(str_value)
        if num_value == 1.0 or num_value == 1:
            return "1"
        elif num_value == 2.0 or num_value == 2:
            return "2"
        elif num_value == 4.0 or num_value == 4:
            return "4"
        elif num_value == 8.0 or num_value == 8:
            return "8"
    except (ValueError, TypeError):
        pass
    
    return None


def _validate_topaz_image_upscale(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для topaz/image-upscale согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["topaz/image-upscale", "topaz/image-upscaler", "topaz/upscale"]:
        return True, None
    
    # Валидация image_url: обязательный string
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для увеличения изображения. Укажите URL изображения"
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if not image_url:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not image_url.startswith(('http://', 'https://')):
        return False, "Поле 'image_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['image_url'] = image_url
    
    # Валидация upscale_factor: обязательный, enum ("1", "2", "4", "8")
    upscale_factor = normalized_input.get('upscale_factor')
    if not upscale_factor:
        return False, "Поле 'upscale_factor' обязательно для увеличения изображения. Укажите коэффициент увеличения: '1', '2', '4' или '8'"
    
    normalized_upscale_factor = _normalize_upscale_factor_for_topaz(upscale_factor)
    if normalized_upscale_factor is None:
        valid_values = ["1", "2", "4", "8"]
        return False, f"Поле 'upscale_factor' должно быть одним из: {', '.join(valid_values)} (получено: {upscale_factor})"
    normalized_input['upscale_factor'] = normalized_upscale_factor
    
    return True, None


def _validate_kling_v2_5_turbo_image_to_video_pro(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для kling/v2-5-turbo-image-to-video-pro согласно документации API.
    
    ВАЖНО: Отличается от других i2v моделей:
    - image_url обязательный string (не массив!)
    - tail_image_url опциональный string (новый параметр)
    - negative_prompt максимум 2496 символов (не 2500!)
    - НЕТ параметра aspect_ratio
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["kling/v2-5-turbo-image-to-video-pro", "kling/v2-5-turbo-i2v-pro", "kling/v2.5-turbo-image-to-video-pro"]:
        return True, None
    
    # Валидация prompt: обязательный, максимум 2500 символов
    prompt = normalized_input.get('prompt')
    if not prompt:
        return False, "Поле 'prompt' обязательно для генерации видео"
    
    if not isinstance(prompt, str):
        prompt = str(prompt)
    
    prompt_len = len(prompt.strip())
    if prompt_len == 0:
        return False, "Поле 'prompt' не может быть пустым"
    if prompt_len > 2500:
        return False, f"Поле 'prompt' слишком длинное: {prompt_len} символов (максимум 2500)"
    
    # Валидация image_url: обязательный string (не массив!)
    image_url = normalized_input.get('image_url')
    if not image_url:
        return False, "Поле 'image_url' обязательно для генерации видео. Укажите URL изображения"
    
    if not isinstance(image_url, str):
        image_url = str(image_url)
    
    image_url = image_url.strip()
    if not image_url:
        return False, "Поле 'image_url' не может быть пустым"
    
    # Проверяем что это валидный URL
    if not image_url.startswith(('http://', 'https://')):
        return False, "Поле 'image_url' должно быть валидным URL (начинается с http:// или https://)"
    
    normalized_input['image_url'] = image_url
    
    # ВАЖНО: Удаляем image_urls если он был передан (для этой модели нужен только image_url как string!)
    if 'image_urls' in normalized_input:
        logger.warning(f"Parameter 'image_urls' is not supported for kling/v2-5-turbo-image-to-video-pro (use 'image_url' as string), removing it")
        del normalized_input['image_urls']
    
    # Валидация tail_image_url: опциональный string
    tail_image_url = normalized_input.get('tail_image_url')
    if tail_image_url is not None:
        if not isinstance(tail_image_url, str):
            tail_image_url = str(tail_image_url)
        
        tail_image_url = tail_image_url.strip()
        # Если пустая строка, удаляем параметр
        if not tail_image_url:
            del normalized_input['tail_image_url']
        else:
            # Проверяем что это валидный URL
            if not tail_image_url.startswith(('http://', 'https://')):
                return False, "Поле 'tail_image_url' должно быть валидным URL (начинается с http:// или https://)"
            normalized_input['tail_image_url'] = tail_image_url
    
    # Валидация duration: опциональный, enum ("5" или "10")
    duration = normalized_input.get('duration')
    if duration is not None:
        normalized_duration = _normalize_duration_for_kling_v2_5_turbo(duration)
        if normalized_duration is None:
            valid_values = ["5", "10"]
            return False, f"Поле 'duration' должно быть одним из: {', '.join(valid_values)} (получено: {duration})"
        normalized_input['duration'] = normalized_duration
    
    # Валидация negative_prompt: опциональный, максимум 2496 символов (не 2500!)
    negative_prompt = normalized_input.get('negative_prompt')
    if negative_prompt is not None:
        if not isinstance(negative_prompt, str):
            negative_prompt = str(negative_prompt)
        
        negative_prompt_len = len(negative_prompt.strip())
        if negative_prompt_len > 2496:
            return False, f"Поле 'negative_prompt' слишком длинное: {negative_prompt_len} символов (максимум 2496)"
        normalized_input['negative_prompt'] = negative_prompt.strip()
    
    # Валидация cfg_scale: опциональный number, диапазон 0-1, шаг 0.1
    cfg_scale = normalized_input.get('cfg_scale')
    if cfg_scale is not None:
        normalized_cfg_scale = _normalize_cfg_scale(cfg_scale)
        if normalized_cfg_scale is None:
            return False, f"Поле 'cfg_scale' должно быть числом от 0 до 1 (шаг 0.1) (получено: {cfg_scale})"
        normalized_input['cfg_scale'] = normalized_cfg_scale
    
    return True, None


def _validate_sora_watermark_remover(
    model_id: str,
    normalized_input: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Специфичная валидация для sora-watermark-remover согласно документации API.
    
    Args:
        model_id: ID модели
        normalized_input: Нормализованные входные данные
    
    Returns:
        (is_valid, error_message)
    """
    # Проверяем оба возможных ID модели
    if model_id not in ["sora-watermark-remover", "openai/sora-watermark-remover", "sora-2-watermark-remover"]:
        return True, None
    
    # Валидация video_url: обязательный, должен начинаться с sora.chatgpt.com, максимум 500 символов
    video_url = normalized_input.get('video_url')
    if not video_url:
        return False, "Поле 'video_url' обязательно для удаления водяного знака. Укажите публично доступную ссылку на видео Sora 2 (начинается с sora.chatgpt.com)"
    
    normalized_video_url = _normalize_video_url_for_sora_watermark_remover(video_url)
    if normalized_video_url is None:
        if len(str(video_url)) > 500:
            return False, f"Поле 'video_url' слишком длинное: {len(str(video_url))} символов (максимум 500)"
        return False, "Поле 'video_url' должно быть публично доступной ссылкой на видео Sora 2 от OpenAI (начинается с sora.chatgpt.com)"
    
    normalized_input['video_url'] = normalized_video_url
    
    return True, None


def build_input(
    model_spec: ModelSpec,
    user_payload: Dict[str, Any],
    mode_index: int = 0
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Строит input для KIE API на основе типа модели и пользовательских данных.
    
    Args:
        model_spec: Спецификация модели из каталога
        user_payload: Пользовательские данные (сырые параметры)
        mode_index: Индекс режима (для извлечения дефолтов из notes)
    
    Returns:
        (input_dict, error_message) где error_message - None если всё ок
    """
    model_type = model_spec.type
    model_id = model_spec.id
    
    # Получаем whitelist и обязательные поля
    allowed_fields = get_schema_for_type(model_type)
    required_fields = get_required_fields_for_type(model_type)
    
    if not allowed_fields:
        logger.warning(f"No schema for model type: {model_type}, model_id: {model_id}")
        # Fallback: разрешаем все поля если схема не найдена
        allowed_fields = set(user_payload.keys())
    
    # Нормализуем и фильтруем поля
    normalized_input: Dict[str, Any] = {}
    
    for key, value in user_payload.items():
        # Нормализуем имя поля через алиасы
        normalized_key = normalize_field_name(key)
        
        # Проверяем что поле разрешено
        if normalized_key not in allowed_fields:
            logger.debug(f"Field '{key}' (normalized: '{normalized_key}') not in whitelist for type {model_type}, skipping")
            continue
        
        # Обрабатываем специальные случаи
        # Для image_urls сохраняем как массив (для wan/2-6-image-to-video)
        if normalized_key == 'image_urls':
            # Если это строка, конвертируем в массив
            if isinstance(value, str) and value.strip():
                value = [value.strip()]
            # Если это массив, оставляем как есть
            elif isinstance(value, list):
                # Фильтруем пустые элементы
                value = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            # Если пустое, пропускаем
            if not value:
                continue
        
        if normalized_key in ['image_url', 'image_base64', 'image']:
            # Если это список, берём первый элемент
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            # Если пустая строка или None, пропускаем
            if not value:
                continue
        
        # Для video_urls сохраняем как массив (для wan/2-6-video-to-video)
        if normalized_key == 'video_urls':
            # Если это строка, конвертируем в массив
            if isinstance(value, str) and value.strip():
                value = [value.strip()]
            # Если это массив, оставляем как есть
            elif isinstance(value, list):
                # Фильтруем пустые элементы
                value = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            # Если пустое, пропускаем
            if not value:
                continue
        
        if normalized_key in ['video_url', 'video']:
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            if not value:
                continue
        
        if normalized_key in ['audio_url', 'audio']:
            if isinstance(value, list) and len(value) > 0:
                value = value[0]
            if not value:
                continue
        
        normalized_input[normalized_key] = value
    
    # Применяем дефолты из схемы
    for field_name in allowed_fields:
        if field_name not in normalized_input:
            default_value = get_default_value(model_type, field_name)
            if default_value is not None:
                normalized_input[field_name] = default_value
    
    # Извлекаем дефолты из notes режима
    if mode_index < len(model_spec.modes):
        mode = model_spec.modes[mode_index]
        if mode.notes:
            # Парсим duration из notes
            if 'duration' not in normalized_input:
                duration = _parse_duration_from_notes(mode.notes)
                if duration is not None:
                    # Для wan/2-6-text-to-video duration должен быть строкой
                    if model_id == "wan/2-6-text-to-video":
                        normalized_input['duration'] = str(int(duration))
                    else:
                        normalized_input['duration'] = duration
            
            # Парсим resolution из notes
            if 'resolution' not in normalized_input:
                resolution = _parse_resolution_from_notes(mode.notes)
                if resolution is not None:
                    normalized_input['resolution'] = resolution
    
    # Специфичная валидация для wan/2-6-text-to-video
    is_valid, error_msg = _validate_wan_2_6_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для wan/2-5-text-to-video
    is_valid, error_msg = _validate_wan_2_5_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для wan/2-5-image-to-video
    is_valid, error_msg = _validate_wan_2_5_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для wan/2-6-image-to-video
    is_valid, error_msg = _validate_wan_2_6_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для wan/2-2-animate-replace
    is_valid, error_msg = _validate_wan_2_2_animate_replace(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для wan/2-2-animate-move
    is_valid, error_msg = _validate_wan_2_2_animate_move(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для wan/2-6-video-to-video
    is_valid, error_msg = _validate_wan_2_6_video_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для wan/2-2-a14b-text-to-video-turbo
    is_valid, error_msg = _validate_wan_2_2_a14b_text_to_video_turbo(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для wan/2-2-a14b-image-to-video-turbo
    is_valid, error_msg = _validate_wan_2_2_a14b_image_to_video_turbo(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для google/imagen4-fast
    is_valid, error_msg = _validate_google_imagen4_fast(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для google/imagen4-ultra
    is_valid, error_msg = _validate_google_imagen4_ultra(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для google/imagen4
    is_valid, error_msg = _validate_google_imagen4(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для seedream/4.5-text-to-image
    is_valid, error_msg = _validate_seedream_4_5_text_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для bytedance/seedream-v4-text-to-image
    is_valid, error_msg = _validate_bytedance_seedream_v4_text_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для bytedance/seedream-v4-edit
    is_valid, error_msg = _validate_bytedance_seedream_v4_edit(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для bytedance/seedream
    is_valid, error_msg = _validate_bytedance_seedream(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для qwen/image-to-image
    is_valid, error_msg = _validate_qwen_image_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для qwen/text-to-image
    is_valid, error_msg = _validate_qwen_text_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для google/nano-banana
    is_valid, error_msg = _validate_google_nano_banana(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для google/nano-banana-edit
    is_valid, error_msg = _validate_google_nano_banana_edit(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для qwen/image-edit
    is_valid, error_msg = _validate_qwen_image_edit(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для ideogram/character-edit
    is_valid, error_msg = _validate_ideogram_character_edit(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для ideogram/character-remix
    is_valid, error_msg = _validate_ideogram_character_remix(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для ideogram/character
    is_valid, error_msg = _validate_ideogram_character(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для bytedance/v1-lite-text-to-video
    is_valid, error_msg = _validate_bytedance_v1_lite_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для bytedance/v1-pro-text-to-video
    is_valid, error_msg = _validate_bytedance_v1_pro_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для bytedance/v1-lite-image-to-video
    is_valid, error_msg = _validate_bytedance_v1_lite_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для bytedance/v1-pro-image-to-video
    is_valid, error_msg = _validate_bytedance_v1_pro_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling/v2-1-master-image-to-video
    is_valid, error_msg = _validate_kling_v2_1_master_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling/v2-1-standard
    is_valid, error_msg = _validate_kling_v2_1_standard(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling/v2-1-pro
    is_valid, error_msg = _validate_kling_v2_1_pro(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling/v2-1-master-text-to-video
    is_valid, error_msg = _validate_kling_v2_1_master_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для seedream/4.5-edit
    is_valid, error_msg = _validate_seedream_4_5_edit(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling-2.6/image-to-video
    is_valid, error_msg = _validate_kling_2_6_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling-2.6/text-to-video
    is_valid, error_msg = _validate_kling_2_6_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для z-image
    is_valid, error_msg = _validate_z_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для flux-2/pro-image-to-image
    is_valid, error_msg = _validate_flux_2_pro_image_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для flux-2/pro-text-to-image
    is_valid, error_msg = _validate_flux_2_pro_text_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для flux-2/flex-image-to-image
    is_valid, error_msg = _validate_flux_2_flex_image_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для flux-2/flex-text-to-image
    is_valid, error_msg = _validate_flux_2_flex_text_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для nano-banana-pro
    is_valid, error_msg = _validate_nano_banana_pro(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для bytedance/v1-pro-fast-image-to-video
    is_valid, error_msg = _validate_bytedance_v1_pro_fast_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для grok-imagine/image-to-video
    is_valid, error_msg = _validate_grok_imagine_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для grok-imagine/text-to-video
    is_valid, error_msg = _validate_grok_imagine_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для grok-imagine/text-to-image
    is_valid, error_msg = _validate_grok_imagine_text_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для recraft/remove-background
    is_valid, error_msg = _validate_recraft_remove_background(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для recraft/crisp-upscale
    is_valid, error_msg = _validate_recraft_crisp_upscale(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для ideogram/v3-reframe
    is_valid, error_msg = _validate_ideogram_v3_reframe(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для ideogram/v3-text-to-image
    is_valid, error_msg = _validate_ideogram_v3_text_to_image(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для ideogram/v3-edit
    is_valid, error_msg = _validate_ideogram_v3_edit(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для ideogram/v3-remix
    is_valid, error_msg = _validate_ideogram_v3_remix(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для elevenlabs/audio-isolation
    is_valid, error_msg = _validate_elevenlabs_audio_isolation(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для elevenlabs/sound-effect-v2
    is_valid, error_msg = _validate_elevenlabs_sound_effect_v2(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для elevenlabs/speech-to-text
    is_valid, error_msg = _validate_elevenlabs_speech_to_text(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для elevenlabs/text-to-speech-multilingual-v2
    is_valid, error_msg = _validate_elevenlabs_text_to_speech_multilingual_v2(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для grok-imagine/upscale
    is_valid, error_msg = _validate_grok_imagine_upscale(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для hailuo/02-text-to-video-pro
    is_valid, error_msg = _validate_hailuo_02_text_to_video_pro(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для hailuo/02-text-to-video-standard
    is_valid, error_msg = _validate_hailuo_02_text_to_video_standard(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для hailuo/02-image-to-video-pro
    is_valid, error_msg = _validate_hailuo_02_image_to_video_pro(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для hailuo/02-image-to-video-standard
    is_valid, error_msg = _validate_hailuo_02_image_to_video_standard(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling/v1-avatar-standard
    is_valid, error_msg = _validate_kling_v1_avatar_standard(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling/ai-avatar-v1-pro
    is_valid, error_msg = _validate_kling_ai_avatar_v1_pro(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для infinitalk/from-audio
    is_valid, error_msg = _validate_infinitalk_from_audio(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для hailuo/2-3-image-to-video-pro
    is_valid, error_msg = _validate_hailuo_2_3_image_to_video_pro(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для hailuo/2-3-image-to-video-standard
    is_valid, error_msg = _validate_hailuo_2_3_image_to_video_standard(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для sora-2-pro-storyboard
    is_valid, error_msg = _validate_sora_2_pro_storyboard(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для sora-2-text-to-video (не pro версия!)
    is_valid, error_msg = _validate_sora_2_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для sora-2-image-to-video (не pro версия!)
    is_valid, error_msg = _validate_sora_2_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для sora-2-pro-text-to-video
    is_valid, error_msg = _validate_sora_2_pro_text_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для sora-2-pro-image-to-video
    is_valid, error_msg = _validate_sora_2_pro_image_to_video(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для sora-watermark-remover
    is_valid, error_msg = _validate_sora_watermark_remover(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для topaz/image-upscale
    is_valid, error_msg = _validate_topaz_image_upscale(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling/v2-5-turbo-text-to-video-pro
    is_valid, error_msg = _validate_kling_v2_5_turbo_text_to_video_pro(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Специфичная валидация для kling/v2-5-turbo-image-to-video-pro
    is_valid, error_msg = _validate_kling_v2_5_turbo_image_to_video_pro(model_id, normalized_input)
    if not is_valid:
        return {}, error_msg
    
    # Применяем дефолты для z-image
    if model_id == "z-image":
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
    
    # Применяем дефолты для flux-2/pro-image-to-image
    if model_id == "flux-2/pro-image-to-image":
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1K"  # Default согласно документации
    
    # Применяем дефолты для flux-2/pro-text-to-image
    if model_id == "flux-2/pro-text-to-image":
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1K"  # Default согласно документации
    
    # Применяем дефолты для flux-2/flex-image-to-image
    if model_id == "flux-2/flex-image-to-image":
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1K"  # Default согласно документации
    
    # Применяем дефолты для flux-2/flex-text-to-image
    if model_id == "flux-2/flex-text-to-image":
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1K"  # Default согласно документации
    
    # Применяем дефолты для nano-banana-pro
    if model_id in ["nano-banana-pro", "google/nano-banana-pro"]:
        if 'image_input' not in normalized_input:
            normalized_input['image_input'] = []  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1K"  # Default согласно документации
        if 'output_format' not in normalized_input:
            normalized_input['output_format'] = "png"  # Default согласно документации
    
    # Применяем дефолты для bytedance/v1-pro-fast-image-to-video
    if model_id in ["bytedance/v1-pro-fast-image-to-video", "bytedance-v1-pro-fast-image-to-video", "v1-pro-fast-image-to-video"]:
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "720p"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
    
    # Применяем дефолты для grok-imagine/image-to-video
    if model_id in ["grok-imagine/image-to-video", "grok/imagine"]:
        if 'index' not in normalized_input:
            normalized_input['index'] = 0  # Default согласно документации
        if 'mode' not in normalized_input:
            normalized_input['mode'] = "normal"  # Default согласно документации
    
    # Применяем дефолты для grok-imagine/text-to-video
    if model_id in ["grok-imagine/text-to-video", "grok/imagine-text-to-video"]:
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "2:3"  # Default согласно документации
        if 'mode' not in normalized_input:
            normalized_input['mode'] = "normal"  # Default согласно документации
    
    # Применяем дефолты для grok-imagine/text-to-image
    if model_id in ["grok-imagine/text-to-image", "grok/imagine-text-to-image"]:
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "3:2"  # Default согласно документации (отличается от text-to-video!)
        # ВАЖНО: Нет параметра mode для text-to-image (в отличие от text-to-video и image-to-video)
    
    # Применяем дефолты для hailuo/02-text-to-video-pro
    if model_id in ["hailuo/02-text-to-video-pro", "hailuo/02-t2v-pro", "hailuo/0.2-text-to-video-pro"]:
        if 'prompt_optimizer' not in normalized_input:
            normalized_input['prompt_optimizer'] = True  # Default согласно документации
    
    # Применяем дефолты для hailuo/02-text-to-video-standard
    if model_id in ["hailuo/02-text-to-video-standard", "hailuo/02-t2v-standard", "hailuo/0.2-text-to-video-standard"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "6"  # Default согласно документации
        if 'prompt_optimizer' not in normalized_input:
            normalized_input['prompt_optimizer'] = True  # Default согласно документации
    
    # Применяем дефолты для hailuo/02-image-to-video-pro
    if model_id in ["hailuo/02-image-to-video-pro", "hailuo/02-i2v-pro", "hailuo/0.2-image-to-video-pro"]:
        if 'image_url' not in normalized_input:
            normalized_input['image_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/17585210783150ispzfo7.png"  # Default согласно документации
        if 'prompt_optimizer' not in normalized_input:
            normalized_input['prompt_optimizer'] = True  # Default согласно документации
        # end_image_url опциональный, default "" (пустая строка) - не добавляем если не указан
    
    # Применяем дефолты для hailuo/02-image-to-video-standard
    if model_id in ["hailuo/02-image-to-video-standard", "hailuo/02-i2v-standard", "hailuo/0.2-image-to-video-standard"]:
        if 'image_url' not in normalized_input:
            normalized_input['image_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/17585207681646umf3lz8.png"  # Default согласно документации
        if 'end_image_url' not in normalized_input:
            normalized_input['end_image_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/1758521423357w8586uq8.png"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "10"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "768P"  # Default согласно документации
        if 'prompt_optimizer' not in normalized_input:
            normalized_input['prompt_optimizer'] = True  # Default согласно документации
    
    # Применяем дефолты для hailuo/2-3-image-to-video-pro
    if model_id in ["hailuo/2-3-image-to-video-pro", "hailuo/2-3-i2v-pro"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "6"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "768P"  # Default согласно документации
    
    # Применяем дефолты для kling/v2-1-master-text-to-video
    if model_id in ["kling/v2-1-master-text-to-video", "kling-v2-1-master-text-to-video", "v2-1-master-text-to-video"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "16:9"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blur, distort, and low quality"  # Default согласно документации
        if 'cfg_scale' not in normalized_input:
            normalized_input['cfg_scale'] = 0.5  # Default согласно документации
    
    # Применяем дефолты для hailuo/2-3-image-to-video-standard
    if model_id in ["hailuo/2-3-image-to-video-standard", "hailuo/2-3-i2v-standard"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "6"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "768P"  # Default согласно документации
    
    # Применяем дефолты для sora-2-pro-storyboard
    if model_id in ["sora-2-pro-storyboard", "sora-2-pro/storyboard", "openai/sora-2-pro-storyboard"]:
        if 'n_frames' not in normalized_input:
            normalized_input['n_frames'] = "15"  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "landscape"  # Default согласно документации
    
    # Применяем дефолты для sora-2-text-to-video (не pro версия!)
    if model_id in ["sora-2-text-to-video", "sora-2/t2v", "openai/sora-2-text-to-video"]:
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "landscape"  # Default согласно документации
        if 'n_frames' not in normalized_input:
            normalized_input['n_frames'] = "10"  # Default согласно документации
        if 'remove_watermark' not in normalized_input:
            normalized_input['remove_watermark'] = True  # Default согласно документации
        # ВАЖНО: НЕТ параметра size в sora-2-text-to-video (только в pro версии!)
    
    # Применяем дефолты для sora-2-image-to-video (не pro версия!)
    if model_id in ["sora-2-image-to-video", "sora-2/i2v", "openai/sora-2-image-to-video"]:
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "landscape"  # Default согласно документации
        if 'n_frames' not in normalized_input:
            normalized_input['n_frames'] = "10"  # Default согласно документации
        if 'remove_watermark' not in normalized_input:
            normalized_input['remove_watermark'] = True  # Default согласно документации
        # ВАЖНО: НЕТ параметра size в sora-2-image-to-video (только в pro версии!)
    
    # Применяем дефолты для sora-2-pro-text-to-video
    if model_id in ["sora-2-pro-text-to-video", "sora-2-pro/t2v", "openai/sora-2-pro-text-to-video"]:
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "landscape"  # Default согласно документации
        if 'n_frames' not in normalized_input:
            normalized_input['n_frames'] = "10"  # Default согласно документации
        if 'size' not in normalized_input:
            normalized_input['size'] = "high"  # Default согласно документации
        if 'remove_watermark' not in normalized_input:
            normalized_input['remove_watermark'] = True  # Default согласно документации
    
    # Применяем дефолты для sora-2-pro-image-to-video
    if model_id in ["sora-2-pro-image-to-video", "sora-2-pro/i2v", "openai/sora-2-pro-image-to-video"]:
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "landscape"  # Default согласно документации
        if 'n_frames' not in normalized_input:
            normalized_input['n_frames'] = "10"  # Default согласно документации
        if 'size' not in normalized_input:
            normalized_input['size'] = "standard"  # Default согласно документации (отличается от text-to-video, где "high"!)
        if 'remove_watermark' not in normalized_input:
            normalized_input['remove_watermark'] = True  # Default согласно документации
    
    # Применяем дефолты для sora-watermark-remover
    if model_id in ["sora-watermark-remover", "openai/sora-watermark-remover", "sora-2-watermark-remover"]:
        if 'video_url' not in normalized_input:
            normalized_input['video_url'] = "https://sora.chatgpt.com/p/s_68e83bd7eee88191be79d2ba7158516f"  # Default согласно документации
    
    # Применяем дефолты для infinitalk/from-audio
    if model_id in ["infinitalk/from-audio", "infinitalk-from-audio"]:
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "480p"  # Default согласно документации
    
    # Применяем дефолты для elevenlabs/sound-effect-v2
    if model_id in ["elevenlabs/sound-effect-v2", "elevenlabs-sound-effect-v2"]:
        if 'loop' not in normalized_input:
            normalized_input['loop'] = False  # Default согласно документации
        if 'prompt_influence' not in normalized_input:
            normalized_input['prompt_influence'] = 0.3  # Default согласно документации
        if 'output_format' not in normalized_input:
            normalized_input['output_format'] = "mp3_44100_128"  # Default согласно документации
    
    # Применяем дефолты для kling/v2-1-standard
    if model_id in ["kling/v2-1-standard", "kling-v2-1-standard", "v2-1-standard"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blur, distort, and low quality"  # Default согласно документации
        if 'cfg_scale' not in normalized_input:
            normalized_input['cfg_scale'] = 0.5  # Default согласно документации
    
    # Применяем дефолты для kling/v2-1-pro
    if model_id in ["kling/v2-1-pro", "kling-v2-1-pro", "v2-1-pro"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blur, distort, and low quality"  # Default согласно документации
        if 'cfg_scale' not in normalized_input:
            normalized_input['cfg_scale'] = 0.5  # Default согласно документации
        if 'tail_image_url' not in normalized_input:
            normalized_input['tail_image_url'] = ""  # Default согласно документации (пустая строка!)
    
    # Применяем дефолты для elevenlabs/speech-to-text
    if model_id in ["elevenlabs/speech-to-text", "elevenlabs-speech-to-text"]:
        if 'language_code' not in normalized_input:
            normalized_input['language_code'] = ""  # Default согласно документации
        if 'tag_audio_events' not in normalized_input:
            normalized_input['tag_audio_events'] = True  # Default согласно документации
        if 'diarize' not in normalized_input:
            normalized_input['diarize'] = True  # Default согласно документации
    
    # Применяем дефолты для elevenlabs/text-to-speech-multilingual-v2
    if model_id in ["elevenlabs/text-to-speech-multilingual-v2", "elevenlabs-text-to-speech-multilingual-v2"]:
        if 'voice' not in normalized_input:
            normalized_input['voice'] = "Rachel"  # Default согласно документации
        if 'stability' not in normalized_input:
            normalized_input['stability'] = 0.5  # Default согласно документации
        if 'similarity_boost' not in normalized_input:
            normalized_input['similarity_boost'] = 0.75  # Default согласно документации
        if 'style' not in normalized_input:
            normalized_input['style'] = 0  # Default согласно документации
        if 'speed' not in normalized_input:
            normalized_input['speed'] = 1  # Default согласно документации
        if 'timestamps' not in normalized_input:
            normalized_input['timestamps'] = False  # Default согласно документации
        if 'previous_text' not in normalized_input:
            normalized_input['previous_text'] = ""  # Default согласно документации
        if 'next_text' not in normalized_input:
            normalized_input['next_text'] = ""  # Default согласно документации
        if 'language_code' not in normalized_input:
            normalized_input['language_code'] = ""  # Default согласно документации
    
    # Применяем дефолты для wan/2-2-a14b-text-to-video-turbo
    if model_id in ["wan/2-2-a14b-text-to-video-turbo", "wan-2-2-a14b-text-to-video-turbo", "wan/2-2-a14b-t2v-turbo", "2-2-a14b-text-to-video-turbo"]:
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "720p"  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "16:9"  # Default согласно документации
        if 'enable_prompt_expansion' not in normalized_input:
            normalized_input['enable_prompt_expansion'] = False  # Default согласно документации
        if 'seed' not in normalized_input:
            normalized_input['seed'] = 0  # Default согласно документации
        if 'acceleration' not in normalized_input:
            normalized_input['acceleration'] = "none"  # Default согласно документации
    
    # Применяем дефолты для wan/2-2-a14b-image-to-video-turbo
    if model_id in ["wan/2-2-a14b-image-to-video-turbo", "wan-2-2-a14b-image-to-video-turbo", "wan/2-2-a14b-i2v-turbo", "2-2-a14b-image-to-video-turbo"]:
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "720p"  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "auto"  # Default согласно документации (ВАЖНО: "auto", а не "16:9"!)
        if 'enable_prompt_expansion' not in normalized_input:
            normalized_input['enable_prompt_expansion'] = False  # Default согласно документации
        if 'seed' not in normalized_input:
            normalized_input['seed'] = 0  # Default согласно документации
        if 'acceleration' not in normalized_input:
            normalized_input['acceleration'] = "none"  # Default согласно документации
    
    # Применяем дефолты для wan/2-2-a14b-speech-to-video-turbo
    if model_id in ["wan/2-2-a14b-speech-to-video-turbo", "wan-2-2-a14b-speech-to-video-turbo"]:
        if 'num_frames' not in normalized_input:
            normalized_input['num_frames'] = 80  # Default согласно документации
        if 'frames_per_second' not in normalized_input:
            normalized_input['frames_per_second'] = 16  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "480p"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации
        if 'num_inference_steps' not in normalized_input:
            normalized_input['num_inference_steps'] = 27  # Default согласно документации
        if 'guidance_scale' not in normalized_input:
            normalized_input['guidance_scale'] = 3.5  # Default согласно документации
        if 'shift' not in normalized_input:
            normalized_input['shift'] = 5  # Default согласно документации
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
    
    # Применяем дефолты для bytedance/seedream
    if model_id in ["bytedance/seedream", "bytedance-seedream", "seedream"]:
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'guidance_scale' not in normalized_input:
            normalized_input['guidance_scale'] = 2.5  # Default согласно документации
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
    
    # Применяем дефолты для qwen/image-to-image
    if model_id in ["qwen/image-to-image", "qwen-image-to-image", "qwen/i2i"]:
        if 'strength' not in normalized_input:
            normalized_input['strength'] = 0.8  # Default согласно документации
        if 'output_format' not in normalized_input:
            normalized_input['output_format'] = "png"  # Default согласно документации
        if 'acceleration' not in normalized_input:
            normalized_input['acceleration'] = "none"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blurry, ugly"  # Default согласно документации
        if 'num_inference_steps' not in normalized_input:
            normalized_input['num_inference_steps'] = 30  # Default согласно документации
        if 'guidance_scale' not in normalized_input:
            normalized_input['guidance_scale'] = 2.5  # Default согласно документации
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
    
    # Применяем дефолты для qwen/text-to-image
    if model_id in ["qwen/text-to-image", "qwen-text-to-image", "qwen/t2i"]:
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'num_inference_steps' not in normalized_input:
            normalized_input['num_inference_steps'] = 30  # Default согласно документации
        if 'guidance_scale' not in normalized_input:
            normalized_input['guidance_scale'] = 2.5  # Default согласно документации
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
        if 'output_format' not in normalized_input:
            normalized_input['output_format'] = "png"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = " "  # Default согласно документации (пробел!)
        if 'acceleration' not in normalized_input:
            normalized_input['acceleration'] = "none"  # Default согласно документации
    
    # Применяем дефолты для kling/v2-1-master-image-to-video
    if model_id in ["kling/v2-1-master-image-to-video", "kling-v2-1-master-image-to-video", "v2-1-master-image-to-video"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blur, distort, and low quality"  # Default согласно документации
        if 'cfg_scale' not in normalized_input:
            normalized_input['cfg_scale'] = 0.5  # Default согласно документации
    
    # Применяем дефолты для google/imagen4-fast
    if model_id in ["google/imagen4-fast", "google-imagen4-fast", "imagen4-fast", "imagen4/fast"]:
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка!)
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "16:9"  # Default согласно документации
        if 'num_images' not in normalized_input:
            normalized_input['num_images'] = "1"  # Default согласно документации
    
    # Применяем дефолты для google/imagen4-ultra
    if model_id in ["google/imagen4-ultra", "google-imagen4-ultra", "imagen4-ultra", "imagen4/ultra"]:
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка!)
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации (ВАЖНО: "1:1", а не "16:9"!)
        if 'seed' not in normalized_input:
            normalized_input['seed'] = ""  # Default согласно документации (пустая строка! ВАЖНО: string, а не number!)
    
    # Применяем дефолты для google/imagen4
    if model_id in ["google/imagen4", "google-imagen4", "imagen4"]:
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка!)
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации (ВАЖНО: "1:1", а не "16:9"!)
        if 'num_images' not in normalized_input:
            normalized_input['num_images'] = "1"  # Default согласно документации
        if 'seed' not in normalized_input:
            normalized_input['seed'] = ""  # Default согласно документации (пустая строка! ВАЖНО: string, а не number!)
    
    # Применяем дефолты для google/nano-banana
    if model_id in ["google/nano-banana", "google-nano-banana", "nano-banana"]:
        if 'output_format' not in normalized_input:
            normalized_input['output_format'] = "png"  # Default согласно документации
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "1:1"  # Default согласно документации
    
    # Применяем дефолты для google/nano-banana-edit
    if model_id in ["google/nano-banana-edit", "google-nano-banana-edit", "nano-banana-edit"]:
        if 'output_format' not in normalized_input:
            normalized_input['output_format'] = "png"  # Default согласно документации
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "1:1"  # Default согласно документации
    
    # Применяем дефолты для qwen/image-edit
    if model_id in ["qwen/image-edit", "qwen-image-edit", "qwen/edit"]:
        if 'acceleration' not in normalized_input:
            normalized_input['acceleration'] = "none"  # Default согласно документации
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "landscape_4_3"  # Default согласно документации
        if 'num_inference_steps' not in normalized_input:
            normalized_input['num_inference_steps'] = 25  # Default согласно документации
        if 'guidance_scale' not in normalized_input:
            normalized_input['guidance_scale'] = 4  # Default согласно документации
        if 'sync_mode' not in normalized_input:
            normalized_input['sync_mode'] = False  # Default согласно документации
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
        if 'output_format' not in normalized_input:
            normalized_input['output_format'] = "png"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blurry, ugly"  # Default согласно документации
    
    # Применяем дефолты для ideogram/character-edit
    if model_id in ["ideogram/character-edit", "ideogram-character-edit", "character-edit"]:
        if 'rendering_speed' not in normalized_input:
            normalized_input['rendering_speed'] = "BALANCED"  # Default согласно документации
        if 'style' not in normalized_input:
            normalized_input['style'] = "AUTO"  # Default согласно документации
        if 'expand_prompt' not in normalized_input:
            normalized_input['expand_prompt'] = True  # Default согласно документации
        if 'num_images' not in normalized_input:
            normalized_input['num_images'] = "1"  # Default согласно документации
    
    # Применяем дефолты для ideogram/character-remix
    if model_id in ["ideogram/character-remix", "ideogram-character-remix", "character-remix"]:
        if 'rendering_speed' not in normalized_input:
            normalized_input['rendering_speed'] = "BALANCED"  # Default согласно документации
        if 'style' not in normalized_input:
            normalized_input['style'] = "AUTO"  # Default согласно документации
        if 'expand_prompt' not in normalized_input:
            normalized_input['expand_prompt'] = True  # Default согласно документации
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'num_images' not in normalized_input:
            normalized_input['num_images'] = "1"  # Default согласно документации
        if 'strength' not in normalized_input:
            normalized_input['strength'] = 0.8  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка!)
        if 'image_urls' not in normalized_input:
            normalized_input['image_urls'] = []  # Default согласно документации
        if 'reference_mask_urls' not in normalized_input:
            normalized_input['reference_mask_urls'] = ""  # Default согласно документации (пустая строка!)
    
    # Применяем дефолты для ideogram/v3-edit
    if model_id in ["ideogram/v3-edit", "ideogram-v3-edit", "v3-edit"]:
        if 'rendering_speed' not in normalized_input:
            normalized_input['rendering_speed'] = "BALANCED"  # Default согласно документации
        if 'expand_prompt' not in normalized_input:
            normalized_input['expand_prompt'] = True  # Default согласно документации
    
    # Применяем дефолты для ideogram/v3-remix
    if model_id in ["ideogram/v3-remix", "ideogram-v3-remix", "v3-remix"]:
        if 'rendering_speed' not in normalized_input:
            normalized_input['rendering_speed'] = "BALANCED"  # Default согласно документации
        if 'style' not in normalized_input:
            normalized_input['style'] = "AUTO"  # Default согласно документации
        if 'expand_prompt' not in normalized_input:
            normalized_input['expand_prompt'] = True  # Default согласно документации
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'num_images' not in normalized_input:
            normalized_input['num_images'] = "1"  # Default согласно документации
        if 'strength' not in normalized_input:
            normalized_input['strength'] = 0.8  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка!)
    
    # Применяем дефолты для ideogram/character
    if model_id in ["ideogram/character", "ideogram-character", "character"]:
        if 'rendering_speed' not in normalized_input:
            normalized_input['rendering_speed'] = "BALANCED"  # Default согласно документации
        if 'style' not in normalized_input:
            normalized_input['style'] = "AUTO"  # Default согласно документации
        if 'expand_prompt' not in normalized_input:
            normalized_input['expand_prompt'] = True  # Default согласно документации
        if 'num_images' not in normalized_input:
            normalized_input['num_images'] = "1"  # Default согласно документации
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка!)
    
    # Применяем дефолты для bytedance/v1-pro-fast-image-to-video
    if model_id in ["bytedance/v1-pro-fast-image-to-video", "bytedance-v1-pro-fast-image-to-video", "v1-pro-fast-image-to-video"]:
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "720p"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
    
    # Применяем дефолты для bytedance/v1-lite-text-to-video
    if model_id in ["bytedance/v1-lite-text-to-video", "bytedance-v1-lite-text-to-video", "v1-lite-text-to-video"]:
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "16:9"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "720p"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'camera_fixed' not in normalized_input:
            normalized_input['camera_fixed'] = False  # Default согласно документации
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
    
    # Применяем дефолты для bytedance/v1-pro-text-to-video
    if model_id in ["bytedance/v1-pro-text-to-video", "bytedance-v1-pro-text-to-video", "v1-pro-text-to-video"]:
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "16:9"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "720p"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'camera_fixed' not in normalized_input:
            normalized_input['camera_fixed'] = False  # Default согласно документации
        if 'seed' not in normalized_input:
            normalized_input['seed'] = -1  # Default согласно документации (случайный seed)
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
    
    # Применяем дефолты для bytedance/v1-lite-image-to-video
    if model_id in ["bytedance/v1-lite-image-to-video", "bytedance-v1-lite-image-to-video", "v1-lite-image-to-video"]:
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "720p"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'camera_fixed' not in normalized_input:
            normalized_input['camera_fixed'] = False  # Default согласно документации
        if 'seed' not in normalized_input:
            normalized_input['seed'] = -1  # Default согласно документации (случайный seed)
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
        if 'end_image_url' not in normalized_input:
            normalized_input['end_image_url'] = ""  # Default согласно документации (пустая строка!)
    
    # Применяем дефолты для bytedance/v1-pro-image-to-video
    if model_id in ["bytedance/v1-pro-image-to-video", "bytedance-v1-pro-image-to-video", "v1-pro-image-to-video"]:
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "720p"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'camera_fixed' not in normalized_input:
            normalized_input['camera_fixed'] = False  # Default согласно документации
        if 'seed' not in normalized_input:
            normalized_input['seed'] = -1  # Default согласно документации (случайный seed)
        if 'enable_safety_checker' not in normalized_input:
            normalized_input['enable_safety_checker'] = True  # Default согласно документации
    
    # Применяем дефолты для ideogram/v3-text-to-image
    if model_id in ["ideogram/v3-text-to-image", "ideogram-v3-text-to-image", "ideogram/v3-t2i", "v3-text-to-image"]:
        if 'rendering_speed' not in normalized_input:
            normalized_input['rendering_speed'] = "BALANCED"  # Default согласно документации
        if 'style' not in normalized_input:
            normalized_input['style'] = "AUTO"  # Default согласно документации
        if 'expand_prompt' not in normalized_input:
            normalized_input['expand_prompt'] = True  # Default согласно документации
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка!)
    
    # Применяем дефолты для ideogram/v3-reframe
    if model_id in ["ideogram/v3-reframe", "ideogram-v3-reframe"]:
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'rendering_speed' not in normalized_input:
            normalized_input['rendering_speed'] = "BALANCED"  # Default согласно документации
        if 'style' not in normalized_input:
            normalized_input['style'] = "AUTO"  # Default согласно документации
        if 'num_images' not in normalized_input:
            normalized_input['num_images'] = "1"  # Default согласно документации
        if 'seed' not in normalized_input:
            normalized_input['seed'] = 0  # Default согласно документации
    
    # Применяем дефолты для topaz/image-upscale
    if model_id in ["topaz/image-upscale", "topaz/image-upscaler", "topaz/upscale"]:
        if 'image_url' not in normalized_input:
            normalized_input['image_url'] = "https://static.aiquickdraw.com/tools/example/1762752805607_mErUj1KR.png"  # Default согласно документации
        if 'upscale_factor' not in normalized_input:
            normalized_input['upscale_factor'] = "2"  # Default согласно документации
    
    # Применяем дефолты для kling/v2-5-turbo-text-to-video-pro
    if model_id in ["kling/v2-5-turbo-text-to-video-pro", "kling/v2-5-turbo-t2v-pro", "kling/v2.5-turbo-text-to-video-pro"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "16:9"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blur, distort, and low quality"  # Default согласно документации
        if 'cfg_scale' not in normalized_input:
            normalized_input['cfg_scale'] = 0.5  # Default согласно документации
    
    # Применяем дефолты для kling-2.6/image-to-video
    if model_id == "kling-2.6/image-to-video":
        if 'sound' not in normalized_input:
            normalized_input['sound'] = False  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
    
    # Применяем дефолты для kling-2.6/text-to-video
    if model_id == "kling-2.6/text-to-video":
        if 'sound' not in normalized_input:
            normalized_input['sound'] = False  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
    
    # Применяем дефолты для kling/v2-5-turbo-text-to-video-pro
    if model_id in ["kling/v2-5-turbo-text-to-video-pro", "kling/v2-5-turbo-t2v-pro", "kling/v2.5-turbo-text-to-video-pro"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "16:9"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blur, distort, and low quality"  # Default согласно документации
        if 'cfg_scale' not in normalized_input:
            normalized_input['cfg_scale'] = 0.5  # Default согласно документации
    
    # Применяем дефолты для kling/v2-5-turbo-image-to-video-pro
    if model_id in ["kling/v2-5-turbo-image-to-video-pro", "kling/v2-5-turbo-i2v-pro", "kling/v2.5-turbo-image-to-video-pro"]:
        if 'image_url' not in normalized_input:
            normalized_input['image_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/1759211376283gfcw5zcy.png"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = "blur, distort, and low quality"  # Default согласно документации
        if 'cfg_scale' not in normalized_input:
            normalized_input['cfg_scale'] = 0.5  # Default согласно документации
        # tail_image_url опциональный, default "" (пустая строка) - не добавляем если не указан
    
    # Применяем дефолты для seedream/4.5-text-to-image
    if model_id == "seedream/4.5-text-to-image":
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
        if 'quality' not in normalized_input:
            normalized_input['quality'] = "basic"  # Default согласно документации
    
    # Применяем дефолты для seedream/4.5-edit
    if model_id == "seedream/4.5-edit":
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "1:1"  # Default согласно документации
        if 'quality' not in normalized_input:
            normalized_input['quality'] = "basic"  # Default согласно документации
    
    # Применяем дефолты для bytedance/seedream-v4-text-to-image
    if model_id in ["bytedance/seedream-v4-text-to-image", "seedream-v4-text-to-image", "seedream-v4-t2i"]:
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'image_resolution' not in normalized_input:
            normalized_input['image_resolution'] = "1K"  # Default согласно документации
        if 'max_images' not in normalized_input:
            normalized_input['max_images'] = 1  # Default согласно документации
    
    # Применяем дефолты для bytedance/seedream-v4-edit
    if model_id in ["bytedance/seedream-v4-edit", "seedream-v4-edit", "seedream-v4-i2i"]:
        if 'image_size' not in normalized_input:
            normalized_input['image_size'] = "square_hd"  # Default согласно документации
        if 'image_resolution' not in normalized_input:
            normalized_input['image_resolution'] = "1K"  # Default согласно документации
        if 'max_images' not in normalized_input:
            normalized_input['max_images'] = 1  # Default согласно документации
    
    # Применяем дефолты для wan/2-6-text-to-video
    if model_id == "wan/2-6-text-to-video":
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1080p"  # Default согласно документации
    
    # Применяем дефолты для wan/2-5-text-to-video
    if model_id in ["wan/2-5-text-to-video", "wan/2.5-text-to-video"]:
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'aspect_ratio' not in normalized_input:
            normalized_input['aspect_ratio'] = "16:9"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1080p"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка)
        if 'enable_prompt_expansion' not in normalized_input:
            normalized_input['enable_prompt_expansion'] = True  # Default согласно документации
    
    # Применяем дефолты для wan/2-5-image-to-video
    if model_id in ["wan/2-5-image-to-video", "wan/2.5-image-to-video"]:
        if 'image_url' not in normalized_input:
            normalized_input['image_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/1758796480945qb63zxq8.webp"  # Default согласно документации
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1080p"  # Default согласно документации
        if 'negative_prompt' not in normalized_input:
            normalized_input['negative_prompt'] = ""  # Default согласно документации (пустая строка)
        if 'enable_prompt_expansion' not in normalized_input:
            normalized_input['enable_prompt_expansion'] = True  # Default согласно документации
    
    # Применяем дефолты для wan/2-6-image-to-video
    if model_id == "wan/2-6-image-to-video":
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1080p"  # Default согласно документации
    
    # Применяем дефолты для wan/2-2-animate-replace
    if model_id in ["wan/2-2-animate-replace", "wan/2.2-animate-replace"]:
        if 'video_url' not in normalized_input:
            normalized_input['video_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/17586199429271xscyd5d.mp4"  # Default согласно документации
        if 'image_url' not in normalized_input:
            normalized_input['image_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/17586199255323tks43kq.png"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "480p"  # Default согласно документации
    
    # Применяем дефолты для wan/2-2-animate-move
    if model_id in ["wan/2-2-animate-move", "wan/2.2-animate-move"]:
        if 'video_url' not in normalized_input:
            normalized_input['video_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/17586254974931y2hottk.mp4"  # Default согласно документации
        if 'image_url' not in normalized_input:
            normalized_input['image_url'] = "https://file.aiquickdraw.com/custom-page/akr/section-images/1758625466310wpehpbnf.png"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "480p"  # Default согласно документации
    
    # Применяем дефолты для wan/2-6-video-to-video
    if model_id == "wan/2-6-video-to-video":
        if 'duration' not in normalized_input:
            normalized_input['duration'] = "5"  # Default согласно документации
        if 'resolution' not in normalized_input:
            normalized_input['resolution'] = "1080p"  # Default согласно документации
    
    # Валидируем обязательные поля
    is_valid, error_msg = _check_required_fields(model_type, normalized_input, required_fields)
    if not is_valid:
        return {}, error_msg
    
    # Логируем (без секретов)
    input_keys = list(normalized_input.keys())
    # Маскируем длинные значения
    safe_input = {}
    for key, value in normalized_input.items():
        if key in ['prompt', 'text', 'negative_prompt']:
            if isinstance(value, str) and len(value) > 50:
                safe_input[key] = value[:50] + "..."
            else:
                safe_input[key] = value
        elif key in ['image_url', 'image_base64', 'video_url', 'audio_url']:
            if isinstance(value, str):
                safe_input[key] = value[:50] + "..." if len(value) > 50 else value
            else:
                safe_input[key] = "<binary>"
        else:
            safe_input[key] = value
    
    logger.info(
        f"MODEL={model_id} TYPE={model_type} INPUT_KEYS={input_keys} "
        f"INPUT_PREVIEW={safe_input}"
    )
    
    return normalized_input, None


def get_callback_url() -> Optional[str]:
    """
    Получает callback URL из настроек.
    
    Returns:
        Callback URL или None
    """
    settings = get_settings()
    callback_url = getattr(settings, 'kie_callback_url', None)
    if not callback_url:
        # Пробуем из env
        import os
        callback_url = os.getenv('KIE_CALLBACK_URL')
    
    return callback_url

