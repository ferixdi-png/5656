"""
Russian UX - BATCH 44

100% русификация ВСЕХ параметров, значений и терминов.
НИ ОДНОГО английского слова в UX!

Принципы:
1. Все enum values → русские варианты для отображения
2. Все технические термины → понятные русские названия  
3. Все кнопки → только русский язык
4. Все подсказки → русский язык
"""
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# RUSSIAN NAMES FOR PARAMETERS (Technical → User-friendly)
# ============================================================================

PARAM_RUSSIAN_NAMES: Dict[str, str] = {
    # Image parameters
    "prompt": "Описание",
    "negative_prompt": "Что НЕ показывать",
    "aspect_ratio": "Формат изображения",
    "ratio": "Соотношение сторон",
    "width": "Ширина",
    "height": "Высота",
    "resolution": "Разрешение",
    "quality": "Качество",
    "size": "Размер",
    "output_format": "Формат файла",
    
    # Generation parameters
    "steps": "Шаги генерации",
    "seed": "Случайное зерно",
    "guidance_scale": "Точность следования описанию",
    "cfg_scale": "Точность следования описанию",
    "num_inference_steps": "Количество шагов",
    "strength": "Сила эффекта",
    
    # Video parameters
    "n_frames": "Длительность",
    "fps": "Частота кадров",
    "duration": "Длительность",
    "motion_strength": "Сила движения",
    "remove_watermark": "Убрать водяной знак",
    
    # Audio parameters
    "text": "Текст",
    "voice": "Голос",
    "speed": "Скорость",
    "pitch": "Высота тона",
    "volume": "Громкость",
    "language": "Язык",
    
    # Image input
    "image_urls": "Изображения",
    "image_url": "Изображение",
    "image_input": "Входное изображение",
    "video_url": "Видео",
    "audio_url": "Аудио",
    
    # Other
    "model": "Модель",
    "style": "Стиль",
    "mood": "Настроение",
    "genre": "Жанр",
}


# ============================================================================
# RUSSIAN VALUES FOR ENUMS (English → Russian display)
# ============================================================================

ENUM_RUSSIAN_VALUES: Dict[str, Dict[str, str]] = {
    # Aspect ratios / formats
    "aspect_ratio": {
        "1:1": "🟦 Квадрат (1:1)",
        "4:3": "📺 Классический (4:3)",
        "3:4": "📱 Вертикальный классический (3:4)",
        "16:9": "🖥️ Широкий (16:9)",
        "9:16": "📱 Вертикальный (9:16) - Stories",
        "21:9": "🎬 Кинематографичный (21:9)",
        "2:3": "📄 Портрет (2:3)",
        "3:2": "📄 Альбом (3:2)",
        "landscape": "🖼️ Горизонтальный",
        "portrait": "📱 Вертикальный",
        "square": "🟦 Квадратный",
        "auto": "🤖 Автоматически",
    },
    
    # Quality / resolution
    "quality": {
        "low": "⚡ Быстро (низкое)",
        "basic": "✓ Стандартное",
        "medium": "✓ Среднее",
        "standard": "✓ Стандартное",
        "high": "⭐ Высокое",
        "ultra": "💎 Ультра",
        "hd": "📺 HD",
        "4k": "🎬 4K",
        "8k": "💎 8K",
    },
    
    # Resolution
    "resolution": {
        "512": "⚡ 512px (быстро)",
        "1024": "✓ 1024px (стандарт)",
        "1K": "✓ 1K (стандарт)",
        "2048": "⭐ 2048px (высокое)",
        "2K": "⭐ 2K (высокое)",
        "4096": "💎 4096px (макс)",
        "4K": "💎 4K (максимум)",
    },
    
    # Size (video quality)
    "size": {
        "small": "⚡ Маленький",
        "medium": "✓ Средний",
        "standard": "✓ Стандартный",
        "large": "⭐ Большой",
        "high": "💎 Высокое качество",
    },
    
    # Duration / frames
    "n_frames": {
        "5": "⚡ 5 секунд",
        "10": "✓ 10 секунд",
        "15": "⭐ 15 секунд",
        "20": "💎 20 секунд",
    },
    
    # Output format
    "output_format": {
        "png": "🖼️ PNG (без потерь)",
        "jpg": "📸 JPEG (сжатый)",
        "jpeg": "📸 JPEG (сжатый)",
        "webp": "🌐 WebP (web)",
        "mp4": "🎬 MP4 (видео)",
        "mp3": "🎵 MP3 (аудио)",
        "wav": "🎵 WAV (без сжатия)",
    },
    
    # Boolean values
    "remove_watermark": {
        "true": "✅ Да, убрать",
        "false": "❌ Нет, оставить",
        "True": "✅ Да, убрать",
        "False": "❌ Нет, оставить",
    },
    
    # Style presets
    "style": {
        "realistic": "📷 Реалистичный",
        "anime": "🎨 Аниме",
        "cartoon": "🎭 Мультяшный",
        "oil_painting": "🖌️ Масляная живопись",
        "watercolor": "💧 Акварель",
        "sketch": "✏️ Эскиз",
        "3d_render": "💎 3D рендер",
        "cinematic": "🎬 Кинематографичный",
        "fantasy": "🧙 Фэнтези",
        "cyberpunk": "🤖 Киберпанк",
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_russian_param_name(param_name: str) -> str:
    """
    Get Russian name for parameter.
    
    Args:
        param_name: Technical parameter name (e.g., "aspect_ratio")
        
    Returns:
        Russian name (e.g., "Формат изображения")
    """
    russian = PARAM_RUSSIAN_NAMES.get(param_name)
    if russian:
        return russian
    
    # Fallback: capitalize and replace underscores
    return param_name.replace("_", " ").capitalize()


def get_russian_enum_value(param_name: str, enum_value: Any) -> str:
    """
    Get Russian display value for enum.
    
    Args:
        param_name: Parameter name (e.g., "aspect_ratio")
        enum_value: English enum value (e.g., "landscape")
        
    Returns:
        Russian display value (e.g., "🖼️ Горизонтальный")
    """
    enum_value_str = str(enum_value).lower()
    
    # Get translations for this parameter
    param_translations = ENUM_RUSSIAN_VALUES.get(param_name, {})
    russian = param_translations.get(enum_value_str)
    
    if russian:
        return russian
    
    # Fallback: return as-is (for custom values)
    return str(enum_value)


def get_all_russian_enum_options(param_name: str, enum_list: List[str]) -> List[Tuple[str, str]]:
    """
    Get all Russian options for enum parameter.
    
    Args:
        param_name: Parameter name
        enum_list: List of English enum values
        
    Returns:
        List of (english_value, russian_display) tuples
    """
    options = []
    for enum_value in enum_list:
        russian_display = get_russian_enum_value(param_name, enum_value)
        options.append((enum_value, russian_display))
    
    return options


def format_value_for_display(param_name: str, value: Any, field_spec: Optional[Dict[str, Any]] = None) -> str:
    """
    Format parameter value for user display (100% Russian).
    
    Args:
        param_name: Parameter name
        value: Parameter value
        field_spec: Field specification (optional)
        
    Returns:
        Formatted Russian string
    """
    # Handle boolean
    if isinstance(value, bool):
        return get_russian_enum_value(param_name, str(value))
    
    # Handle enum values
    if field_spec and field_spec.get("enum"):
        return get_russian_enum_value(param_name, value)
    
    # Handle numbers with units
    if param_name in ("width", "height", "resolution"):
        return f"{value} пикселей"
    elif param_name in ("steps", "num_inference_steps"):
        return f"{value} шагов"
    elif param_name in ("duration", "n_frames"):
        if isinstance(value, (int, float)):
            return f"{value} секунд"
        return str(value)
    elif param_name in ("speed",):
        return f"×{value}"
    elif param_name in ("strength", "guidance_scale", "cfg_scale"):
        return f"{value}"
    
    # Default: return as string
    return str(value)


def get_param_description(param_name: str, field_spec: Dict[str, Any]) -> str:
    """
    Get Russian description/help for parameter.
    
    Args:
        param_name: Parameter name
        field_spec: Field specification
        
    Returns:
        Russian description
    """
    # Try to get from spec
    description = field_spec.get("description", "")
    if description and not any(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in description[:50]):
        # Already in Russian
        return description
    
    # Generate from param name
    russian_name = get_russian_param_name(param_name)
    
    # Add hints based on type
    field_type = field_spec.get("type", "string")
    if field_type in ("integer", "int", "number", "float"):
        min_val = field_spec.get("min")
        max_val = field_spec.get("max")
        if min_val is not None and max_val is not None:
            return f"{russian_name} (от {min_val} до {max_val})"
        elif min_val is not None:
            return f"{russian_name} (минимум {min_val})"
        elif max_val is not None:
            return f"{russian_name} (максимум {max_val})"
    
    return russian_name

