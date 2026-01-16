"""
YAML Registry - загрузчик models/kie_models.yaml как единого источника истины для model_type и input_params

Структура YAML:
  meta:
    source: ...
    total_models: 72
  models:
    model_id:
      model_type: text_to_image
      input:
        param_name:
          type: string|enum|array|boolean
          required: true|false
          max: 1000
          values: [...]  # для enum
          item_type: string  # для array
"""

import os
import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Global cache
_yaml_cache: Optional[Dict[str, Any]] = None

_ALLOWED_KIE_CATEGORIES = {
    "video",
    "image",
    "avatar",
    "audio",
    "music",
    "enhance",
    "other",
}


def _get_yaml_path() -> Path:
    """Получить путь к YAML файлу."""
    # Пытаемся найти models/kie_models.yaml относительно текущего файла
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent
    yaml_path = project_root / "models" / "kie_models.yaml"
    
    if not yaml_path.exists():
        # Fallback: ищем относительно рабочей директории
        cwd = Path.cwd()
        yaml_path = cwd / "models" / "kie_models.yaml"
        
        if not yaml_path.exists():
            # Еще один fallback: ищем в текущей директории
            yaml_path = Path("models/kie_models.yaml")
    
    return yaml_path


def load_yaml_models() -> Dict[str, Dict[str, Any]]:
    """
    Загружает модели из models/kie_models.yaml.
    
    Returns:
        Dict[model_id, model_data] где model_data содержит:
        - model_type (str)
        - input (dict) - параметры ввода
    """
    global _yaml_cache
    
    if _yaml_cache is not None:
        return _yaml_cache
    
    yaml_path = _get_yaml_path()
    
    if not yaml_path.exists():
        logger.error(f"YAML file not found: {yaml_path}")
        return {}
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        models_dict = data.get('models', {})
        validated = _validate_yaml_models(models_dict)
        
        _yaml_cache = validated
        logger.info(f"Loaded {len(validated)} models from YAML: {yaml_path}")
        return validated
        
    except Exception as e:
        logger.error(f"Failed to load YAML models from {yaml_path}: {e}", exc_info=True)
        return {}


def get_model_from_yaml(model_id: str) -> Optional[Dict[str, Any]]:
    """
    Получить данные модели из YAML по ID.
    
    Returns:
        Dict с model_type и input, или None если не найдено
    """
    yaml_models = load_yaml_models()
    return yaml_models.get(model_id)


def get_yaml_meta() -> Dict[str, Any]:
    """Получить метаданные из YAML."""
    yaml_path = _get_yaml_path()
    if not yaml_path.exists():
        return {}
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data.get('meta', {})
    except Exception as e:
        logger.error(f"Failed to load YAML meta: {e}")
        return {}


def _validate_yaml_models(models_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Validate YAML model catalog entries and skip invalid ones."""
    validated: Dict[str, Dict[str, Any]] = {}
    seen_ids = set()
    for model_id, model_data in models_dict.items():
        if not model_id or not isinstance(model_id, str):
            logger.warning("Invalid model_id in YAML: %s", model_id)
            continue
        if model_id in seen_ids:
            logger.warning("Duplicate model_id in YAML: %s", model_id)
            continue
        if not isinstance(model_data, dict):
            logger.warning("Invalid model data for %s: expected dict, got %s", model_id, type(model_data))
            continue
        if 'model_type' not in model_data:
            logger.warning("Model %s missing model_type, skipping", model_id)
            continue
        if 'input' not in model_data or not model_data['input']:
            logger.warning("Model %s missing or empty input, skipping", model_id)
            continue
        category = model_data.get("category")
        if category is not None and category not in _ALLOWED_KIE_CATEGORIES:
            logger.warning("Model %s has invalid category: %s", model_id, category)
            continue
        validated[model_id] = {
            'model_type': model_data['model_type'],
            'input': model_data['input']
        }
        seen_ids.add(model_id)
    return validated


def _convert_yaml_input_to_input_params(yaml_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Конвертирует YAML формат input в формат input_params, совместимый с текущим кодом.
    
    YAML формат:
      param_name:
        type: string|enum|array|boolean
        required: true|false
        max: 1000
        values: [...]  # для enum
        item_type: string  # для array
    
    Целевой формат:
      param_name:
        type: "string"|"array"
        description: "..."
        required: True|False
        max_length: 1000
        enum: [...]  # для enum
        item_type: "string"  # для array
    """
    input_params = {}
    
    for param_name, param_spec in yaml_input.items():
        if not isinstance(param_spec, dict):
            continue
        
        param_type = param_spec.get('type', 'string')
        required = param_spec.get('required', False)
        
        converted_param = {
            'type': param_type,
            'required': required
        }
        
        # Добавляем description (может быть сгенерировано)
        if 'description' in param_spec:
            converted_param['description'] = param_spec['description']
        else:
            # Генерируем базовое описание
            if param_type == 'string':
                converted_param['description'] = f"Параметр {param_name}"
            elif param_type == 'array':
                converted_param['description'] = f"Массив {param_name}"
            elif param_type == 'boolean':
                converted_param['description'] = f"Булев параметр {param_name}"
            else:
                converted_param['description'] = f"Параметр {param_name}"
        
        # Обработка max -> max_length
        if 'max' in param_spec:
            converted_param['max_length'] = param_spec['max']
        
        # Обработка enum
        if param_type == 'enum' and 'values' in param_spec:
            converted_param['enum'] = param_spec['values']
            # Для enum обычно type = "string"
            converted_param['type'] = 'string'
        
        # Обработка array
        if param_type == 'array':
            if 'item_type' in param_spec:
                converted_param['item_type'] = param_spec['item_type']
            else:
                converted_param['item_type'] = 'string'  # Дефолт
        
        input_params[param_name] = converted_param
    
    return input_params


def normalize_yaml_model(
    model_id: str,
    yaml_data: Dict[str, Any],
    enrich_from: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Нормализует модель из YAML в формат, совместимый с текущим кодом.
    
    Args:
        model_id: ID модели
        yaml_data: Данные из YAML (model_type, input)
        enrich_from: Дополнительные данные для обогащения (name, category, emoji, pricing)
                    обычно из API или kie_models.py
    
    Returns:
        Нормализованная модель с полями:
        - id, name, category, emoji, model_type, input_params
        - опционально: description, pricing
    """
    model_type = yaml_data.get('model_type', 'text_to_image')
    yaml_input = yaml_data.get('input', {})
    
    # Конвертируем input в input_params
    input_params = _convert_yaml_input_to_input_params(yaml_input)
    
    # Базовые поля из model_id или enrich_from
    name = model_id
    category = "Другое"
    emoji = "🤖"
    description = ""
    pricing = ""
    
    if enrich_from:
        name = enrich_from.get('name') or enrich_from.get('display_name') or enrich_from.get('title') or model_id
        category = enrich_from.get('category') or enrich_from.get('type') or "Другое"
        emoji = enrich_from.get('emoji') or "🤖"
        description = enrich_from.get('description') or ""
        pricing = enrich_from.get('pricing') or enrich_from.get('price') or ""
    else:
        # Генерируем name из model_id (делаем читабельным)
        name = model_id.replace('/', ' ').replace('-', ' ').title()
        # Пытаемся определить category по model_type
        if 'video' in model_type:
            category = "Видео"
        elif 'image' in model_type or 'photo' in model_type:
            category = "Фото"
        elif 'audio' in model_type or 'speech' in model_type or 'music' in model_type:
            category = "Аудио"
        else:
            category = "Другое"
        
        # Пытаемся определить emoji по model_type
        emoji_map = {
            'text_to_image': '🖼️',
            'text_to_video': '🎬',
            'image_to_video': '🎬',
            'image_to_image': '🎨',
            'image_edit': '✏️',
            'text_to_speech': '🗣️',
            'speech_to_text': '🎙️',
            'text_to_music': '🎵',
            'audio_to_audio': '🎧',
        }
        emoji = emoji_map.get(model_type, '🤖')
    
    normalized = {
        'id': model_id,
        'name': name,
        'category': category,
        'emoji': emoji,
        'model_type': model_type,
        'input_params': input_params
    }
    
    if description:
        normalized['description'] = description
    if pricing:
        normalized['pricing'] = pricing
    
    return normalized
