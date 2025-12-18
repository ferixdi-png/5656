"""
Модуль для оптимизации UX и упрощения ввода параметров.
Включает группировку параметров, подсказки и умные значения по умолчанию.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# Группы связанных параметров для объединения в один шаг
PARAMETER_GROUPS = {
    'video_quality': {
        'params': ['aspect_ratio', 'resolution', 'duration'],
        'description': 'Настройки качества видео',
        'defaults': {
            'aspect_ratio': '16:9',
            'resolution': '720p',
            'duration': '10'
        }
    },
    'image_quality': {
        'params': ['aspect_ratio', 'resolution'],
        'description': 'Настройки качества изображения',
        'defaults': {
            'aspect_ratio': '1:1',
            'resolution': '1024x1024'
        }
    },
    'generation_settings': {
        'params': ['num_images', 'seed', 'guidance_scale'],
        'description': 'Настройки генерации',
        'defaults': {
            'num_images': '1',
            'seed': None,
            'guidance_scale': '7.5'
        }
    }
}


# Подсказки для параметров
PARAMETER_HINTS = {
    'aspect_ratio': {
        'ru': 'Соотношение сторон изображения/видео. Например, 16:9 для широкоформатного видео, 1:1 для квадрата.',
        'en': 'Aspect ratio of image/video. For example, 16:9 for widescreen video, 1:1 for square.'
    },
    'resolution': {
        'ru': 'Разрешение результата. Чем выше разрешение, тем лучше качество, но дольше генерация.',
        'en': 'Output resolution. Higher resolution means better quality but longer generation time.'
    },
    'duration': {
        'ru': 'Длительность видео в секундах. Обычно от 5 до 15 секунд.',
        'en': 'Video duration in seconds. Usually from 5 to 15 seconds.'
    },
    'guidance_scale': {
        'ru': 'Сила следования промпту. Чем выше значение, тем точнее результат соответствует промпту.',
        'en': 'How closely the result follows the prompt. Higher values mean more accurate prompt following.'
    },
    'seed': {
        'ru': 'Случайное число для воспроизводимости результатов. Оставьте пустым для случайного результата.',
        'en': 'Random number for reproducible results. Leave empty for random result.'
    },
    'num_images': {
        'ru': 'Количество изображений для генерации. Обычно от 1 до 4.',
        'en': 'Number of images to generate. Usually from 1 to 4.'
    },
    'remove_watermark': {
        'ru': 'Удалить водяной знак с результата. Может увеличить стоимость генерации.',
        'en': 'Remove watermark from result. May increase generation cost.'
    }
}


def get_parameter_hint(param_name: str, lang: str = 'ru') -> str:
    """Возвращает подсказку для параметра."""
    hint = PARAMETER_HINTS.get(param_name, {}).get(lang)
    if not hint:
        hint = PARAMETER_HINTS.get(param_name, {}).get('ru', '')
    return hint


def get_parameter_group(param_name: str) -> Optional[str]:
    """Определяет, к какой группе относится параметр."""
    for group_name, group_info in PARAMETER_GROUPS.items():
        if param_name in group_info['params']:
            return group_name
    return None


def get_group_parameters(group_name: str) -> List[str]:
    """Возвращает список параметров в группе."""
    group_info = PARAMETER_GROUPS.get(group_name)
    if group_info:
        return group_info['params']
    return []


def get_group_defaults(group_name: str) -> Dict[str, Any]:
    """Возвращает значения по умолчанию для группы параметров."""
    group_info = PARAMETER_GROUPS.get(group_name)
    if group_info:
        return group_info.get('defaults', {})
    return {}


def can_group_parameters(params: List[str], properties: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, можно ли сгруппировать параметры.
    Возвращает (можно_ли, название_группы).
    """
    # Проверяем, есть ли параметры, которые можно сгруппировать
    found_groups = {}
    for param_name in params:
        group_name = get_parameter_group(param_name)
        if group_name:
            if group_name not in found_groups:
                found_groups[group_name] = []
            found_groups[group_name].append(param_name)
    
    # Ищем группу, где все параметры присутствуют
    for group_name, group_params in PARAMETER_GROUPS.items():
        if all(p in params for p in group_params['params']):
            # Проверяем, что все параметры еще не заполнены
            return True, group_name
    
    return False, None


def get_smart_defaults(model_id: str, param_name: str, properties: Dict[str, Any]) -> Optional[Any]:
    """
    Возвращает умное значение по умолчанию для параметра на основе модели и контекста.
    """
    param_info = properties.get(param_name, {})
    enum_values = param_info.get('enum', [])
    param_type = param_info.get('type', 'string')
    
    # Если есть значение по умолчанию в схеме, используем его
    if 'default' in param_info:
        return param_info['default']
    
    # Умные значения по умолчанию на основе типа модели
    model_id_lower = model_id.lower()
    
    if param_name == 'aspect_ratio':
        if 'video' in model_id_lower:
            return '16:9' if '16:9' in enum_values else (enum_values[0] if enum_values else None)
        else:
            return '1:1' if '1:1' in enum_values else (enum_values[0] if enum_values else None)
    
    elif param_name == 'resolution':
        if 'video' in model_id_lower:
            return '720p' if '720p' in enum_values else (enum_values[0] if enum_values else None)
        else:
            # Для изображений выбираем среднее разрешение
            if '1024x1024' in enum_values:
                return '1024x1024'
            elif '512x512' in enum_values:
                return '512x512'
            else:
                return enum_values[0] if enum_values else None
    
    elif param_name == 'duration':
        if '10' in enum_values:
            return '10'
        elif '5' in enum_values:
            return '5'
        else:
            return enum_values[0] if enum_values else None
    
    elif param_name == 'guidance_scale':
        if param_type == 'number':
            return 7.5
        elif '7.5' in enum_values:
            return '7.5'
        else:
            return enum_values[0] if enum_values else None
    
    elif param_name == 'num_images':
        return '1' if '1' in enum_values else (enum_values[0] if enum_values else None)
    
    elif param_name == 'remove_watermark':
        return True if param_type == 'boolean' else None
    
    # Если ничего не подошло, возвращаем первое значение из enum или None
    return enum_values[0] if enum_values else None

