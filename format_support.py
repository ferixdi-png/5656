"""
Модуль для поддержки дополнительных форматов данных.
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class SupportedFormat(Enum):
    """Поддерживаемые форматы данных."""
    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    IMAGE_WEBP = "image/webp"
    IMAGE_GIF = "image/gif"
    VIDEO_MP4 = "video/mp4"
    VIDEO_WEBM = "video/webm"
    VIDEO_MOV = "video/quicktime"
    AUDIO_MP3 = "audio/mpeg"
    AUDIO_WAV = "audio/wav"
    AUDIO_OGG = "audio/ogg"
    MODEL_3D_OBJ = "model/obj"
    MODEL_3D_GLTF = "model/gltf"
    ANIMATION_GIF = "image/gif"


def get_supported_formats_for_model(model_id: str) -> List[str]:
    """
    Возвращает список поддерживаемых форматов для модели.
    
    Args:
        model_id: ID модели
    
    Returns:
        Список форматов
    """
    # Определяем форматы на основе типа модели
    model_id_lower = model_id.lower()
    
    if 'image' in model_id_lower or 'photo' in model_id_lower:
        return [
            SupportedFormat.IMAGE_JPEG.value,
            SupportedFormat.IMAGE_PNG.value,
            SupportedFormat.IMAGE_WEBP.value
        ]
    elif 'video' in model_id_lower:
        return [
            SupportedFormat.VIDEO_MP4.value,
            SupportedFormat.VIDEO_WEBM.value
        ]
    elif 'audio' in model_id_lower or 'speech' in model_id_lower:
        return [
            SupportedFormat.AUDIO_MP3.value,
            SupportedFormat.AUDIO_WAV.value
        ]
    elif '3d' in model_id_lower or 'model' in model_id_lower:
        return [
            SupportedFormat.MODEL_3D_OBJ.value,
            SupportedFormat.MODEL_3D_GLTF.value
        ]
    elif 'gif' in model_id_lower or 'animate' in model_id_lower:
        return [
            SupportedFormat.ANIMATION_GIF.value
        ]
    else:
        # По умолчанию поддерживаем изображения
        return [
            SupportedFormat.IMAGE_JPEG.value,
            SupportedFormat.IMAGE_PNG.value
        ]


def validate_format(format: str, model_id: str) -> bool:
    """
    Проверяет, поддерживается ли формат для модели.
    
    Args:
        format: Формат для проверки
        model_id: ID модели
    
    Returns:
        True, если формат поддерживается
    """
    supported = get_supported_formats_for_model(model_id)
    return format in supported


def convert_format(input_url: str, output_format: str) -> Optional[str]:
    """
    Конвертирует файл в другой формат.
    
    Args:
        input_url: URL входного файла
        output_format: Целевой формат
    
    Returns:
        URL конвертированного файла или None
    """
    # В реальной реализации здесь будет конвертация через API
    logger.info(f"🔄 Конвертация {input_url} в {output_format}")
    return None

