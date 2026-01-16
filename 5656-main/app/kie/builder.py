"""
Universal payload builder for Kie.ai createTask based on model schema from source_of_truth.
"""
import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_source_of_truth(file_path: str = "models/KIE_SOURCE_OF_TRUTH.json") -> Dict[str, Any]:
    """
    Load KIE model catalog from SSOT (Single Source of Truth) - cached for performance.
    
    CRITICAL: Only models/KIE_SOURCE_OF_TRUTH.json is used in runtime.
    All other JSON files in models/ are deprecated and moved to models/_deprecated/.
    
    Args:
        file_path: SSOT path (default: models/KIE_SOURCE_OF_TRUTH.json)
    
    Returns:
        Dict with models, pricing, schemas
    """
    # SSOT enforcement: ignore file_path parameter, always use canonical path
    master_path = "models/KIE_SOURCE_OF_TRUTH.json"
    
    if not os.path.exists(master_path):
        logger.error(f"CRITICAL: SOURCE_OF_TRUTH not found: {master_path}")
        return {}
    
    logger.info(f"✅ Loading SOURCE_OF_TRUTH v1.2.0 (cached): {master_path}")
    
    with open(master_path, 'r', encoding='utf-8') as f:
        return json.load(f)



def get_model_schema(model_id: str, source_of_truth: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """
    Get model schema from source of truth.
    
    Supports both formats:
    - V7: {"models": {model_id: {...}}}  (dict)
    - V6: {"models": [{model_id: ...}]}  (list)
    """
    if source_of_truth is None:
        source_of_truth = load_source_of_truth()
    
    models = source_of_truth.get('models', [])
    
    # V7 format: dict
    if isinstance(models, dict):
        return models.get(model_id)
    
    # V6 format: list
    for model in models:
        if model.get('model_id') == model_id:
            return model
    
    logger.warning(f"Model {model_id} not found in source of truth")
    return None


def get_model_config(model_id: str, source_of_truth: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """
    Get full model configuration including metadata, pricing, and schema.
    
    Returns complete model data for UI display:
    - model_id, provider, category
    - display_name, description
    - pricing (rub_per_gen, usd_per_gen)
    - input_schema or parameters
    - endpoint, method
    - examples, tags, ui_example_prompts
    
    Args:
        model_id: Model identifier
        source_of_truth: Optional pre-loaded source of truth
        
    Returns:
        Full model configuration dict or None if not found
    """
    return get_model_schema(model_id, source_of_truth)


def build_payload(
    model_id: str,
    user_inputs: Dict[str, Any],
    source_of_truth: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Build createTask payload for Kie.ai API.
    
    Args:
        model_id: Model identifier
        user_inputs: User-provided inputs (text, url, file, etc.)
        source_of_truth: Optional pre-loaded source of truth
        
    Returns:
        Payload dictionary for createTask API
    """
    model_schema = get_model_schema(model_id, source_of_truth)
    if not model_schema:
        raise ValueError(f"Model {model_id} not found in source of truth")

    from app.kie.validator import validate_model_inputs, validate_payload_before_create_task

    validate_model_inputs(model_id, model_schema, user_inputs)

    # V7 format detection: has 'parameters' instead of 'input_schema'
    is_v7 = 'parameters' in model_schema and 'endpoint' in model_schema
    
    if is_v7:
        # V7: Specialized endpoints, direct parameters (not wrapped in 'input')
        parameters_schema = model_schema.get('parameters', {})
        api_endpoint = model_schema.get('endpoint')
        
        # V7: параметры идут напрямую в payload (БЕЗ обертки 'input')
        payload = {}
        
        # Добавляем параметры из user_inputs
        for param_name, param_spec in parameters_schema.items():
            if param_name in user_inputs:
                payload[param_name] = user_inputs[param_name]
            elif param_spec.get('default') is not None:
                payload[param_name] = param_spec['default']
            elif param_spec.get('required'):
                # Для обязательных параметров без значения - пытаемся подобрать
                if param_name == 'prompt' and 'text' in user_inputs:
                    payload['prompt'] = user_inputs['text']
                elif param_name == 'model':
                    # Используем model_id из schema как default
                    payload['model'] = model_schema.get('model_id')
        
        logger.info(f"V7 payload for {model_id}: {payload}")
        return payload
    
    else:
        # V6: Old format with api_endpoint and input_schema
        input_schema = model_schema.get('input_schema', {})
        
        # КРИТИЧНО: Проверяем формат schema
        # ПРЯМОЙ формат (veo3_fast, V4): {prompt: {...}, imageUrls: {...}, customMode: {...}}
        # Если НЕТ поля 'input', значит это ПРЯМОЙ формат
        has_input_wrapper = 'input' in input_schema and isinstance(input_schema['input'], dict)
        
        # ВАЖНО: Если schema имеет структуру {model: {...}, callBackUrl: {...}, input: {type: dict, examples: [...]}}
        # то реальные user fields находятся в examples первого примера для 'input' поля
        if has_input_wrapper:
            input_field_spec = input_schema['input']
            
            # ВАРИАНТ 1: input имеет properties (вложенная schema) — как у sora-2-pro-storyboard
            if 'properties' in input_field_spec and isinstance(input_field_spec['properties'], dict):
                input_schema = input_field_spec['properties']
                logger.debug(f"Extracted input schema from properties for {model_id}: {list(input_schema.keys())}")
            
            # ВАРИАНТ 2: input имеет examples (большинство моделей)
            elif 'examples' in input_field_spec and isinstance(input_field_spec['examples'], list):
                # Это описание поля - examples показывают структуру user inputs
                examples = input_field_spec['examples']
                if examples and isinstance(examples[0], dict):
                    # Первый example показывает какие поля должны быть в user_inputs
                    # Преобразуем пример в schema-подобную структуру
                    example_structure = examples[0]
                    
                    # Создаем schema из примера
                    input_schema = {}
                    for field_name, field_value in example_structure.items():
                        # Определяем тип по значению
                        # ВАЖНО: bool проверяется FIRST, т.к. bool является подклассом int в Python
                        if isinstance(field_value, bool):
                            field_type = 'boolean'
                        elif isinstance(field_value, str):
                            field_type = 'string'
                        elif isinstance(field_value, (int, float)):
                            field_type = 'number'
                        elif isinstance(field_value, dict):
                            field_type = 'object'
                        elif isinstance(field_value, list):
                            field_type = 'array'
                        else:
                            field_type = 'string'
                        
                        input_schema[field_name] = {
                            'type': field_type,
                            'required': False  # Консервативно
                        }
                    
                    # Для prompt делаем required если он есть
                    if 'prompt' in input_schema:
                        input_schema['prompt']['required'] = True
                    
                    logger.debug(f"Extracted input schema from examples for {model_id}: {list(input_schema.keys())}")
        
        # КРИТИЧНО: Определяем формат payload
        # ПРЯМОЙ формат (veo3_fast, V4): параметры на верхнем уровне, БЕЗ input wrapper
        # ОБЫЧНЫЙ формат: параметры в input wrapper
        is_direct_format = not has_input_wrapper
        
        # CRITICAL: Use api_endpoint for Kie.ai API (not model_id)
        api_endpoint = model_schema.get('api_endpoint', model_id)
        
        # Build payload based on schema format
        if is_direct_format:
            # ПРЯМОЙ формат: параметры на верхнем уровне
            payload = {}
            logger.info(f"Using DIRECT format for {model_id} (no input wrapper)")
        else:
            # ОБЫЧНЫЙ формат: параметры в input wrapper
            payload = {
                'model': api_endpoint,  # Use api_endpoint, not model_id
                'input': {}  # All fields go into 'input' object
            }
            logger.info(f"Using WRAPPED format for {model_id} (input wrapper)")
    
    # Parse input_schema: support BOTH flat and nested formats
    # FLAT format (source_of_truth.json): {"field": {"type": "...", "required": true}}
    # NESTED format (old): {"required": [...], "properties": {...}}
    # BUGGY format (many models): {"required": true/false (boolean!), "examples": [...]}
    
    # ВАЖНО: Системные поля ВСЕГДА фильтруются из пользовательского ввода
    # Они добавляются автоматически при создании задачи
    SYSTEM_FIELDS = {'model', 'callBackUrl', 'callback', 'callback_url', 'webhookUrl', 'webhook_url'}
    
    # Handle buggy "required: true/false" by inferring from examples
    required_fields_inferred = []
    if isinstance(input_schema.get('required'), bool):
        # SOURCE_OF_TRUTH has "required: True" (boolean) instead of list
        # WORKAROUND: Infer required fields from first example
        examples = input_schema.get('examples', [])
        if examples:
            first_example = examples[0]
            required_fields_inferred = list(first_example.keys())
            logger.warning(
                f"[WORKAROUND] {model_id}: required is boolean, inferring from example: {required_fields_inferred}"
            )
    
    # Для ЛЮБОГО формата фильтруем системные поля из required/optional
    if is_direct_format:
        # Для прямого формата берём ВСЕ поля из schema, НО фильтруем системные
        properties = {k: v for k, v in input_schema.items() if k not in SYSTEM_FIELDS}
        required_fields = [k for k, v in properties.items() if v.get('required', False)]
        optional_fields = [k for k in properties.keys() if k not in required_fields]
        logger.info(
            f"📋 SCHEMA | Model: {model_id} | Format: DIRECT | "
            f"Required: {len(required_fields)} | Optional: {len(optional_fields)} | "
            f"Fields: {list(properties.keys())[:10]}"
        )
        logger.debug(f"Direct format fields: required={required_fields}, optional={optional_fields}")
    elif 'properties' in input_schema:
        # Nested format
        required_fields = input_schema.get('required', [])
        # Handle buggy boolean required
        if isinstance(required_fields, bool):
            required_fields = required_fields_inferred
        properties = input_schema.get('properties', {})
        # Calculate optional fields as difference
        optional_fields = [k for k in properties.keys() if k not in required_fields]
        
        # ФИЛЬТРУЕМ системные поля
        required_fields = [f for f in required_fields if f not in SYSTEM_FIELDS]
        optional_fields = [f for f in optional_fields if f not in SYSTEM_FIELDS]
        properties = {k: v for k, v in properties.items() if k not in SYSTEM_FIELDS}
        logger.info(
            f"📋 SCHEMA | Model: {model_id} | Format: NESTED | "
            f"Required: {len(required_fields)} | Optional: {len(optional_fields)}"
        )
    else:
        # Flat format - convert to nested
        properties = input_schema
        required_fields = [k for k, v in properties.items() if v.get('required', False)]
        optional_fields = [k for k in properties.keys() if k not in required_fields]
        
        # ФИЛЬТРУЕМ системные поля
        required_fields = [f for f in required_fields if f not in SYSTEM_FIELDS]
        optional_fields = [f for f in optional_fields if f not in SYSTEM_FIELDS]
        properties = {k: v for k, v in properties.items() if k not in SYSTEM_FIELDS}
        logger.info(
            f"📋 SCHEMA | Model: {model_id} | Format: FLAT | "
            f"Required: {len(required_fields)} | Optional: {len(optional_fields)}"
        )
    
    # If no properties, use FALLBACK logic
    if not properties:
        logger.warning(f"No input_schema for {model_id}, using fallback")
        # FALLBACK logic (keep for backward compatibility)
        category = model_schema.get('category', '')
        
        # Try to find prompt/text in user_inputs
        prompt_value = user_inputs.get('prompt') or user_inputs.get('text')
        url_value = user_inputs.get('url') or user_inputs.get('image_url') or user_inputs.get('video_url') or user_inputs.get('audio_url')
        file_value = user_inputs.get('file') or user_inputs.get('file_id')
        
        # Text-to-X models: need prompt
        if category in ['t2i', 't2v', 'tts', 'music', 'sfx', 'text-to-image', 'text-to-video'] or 'text' in model_id.lower():
            if prompt_value:
                payload['input']['prompt'] = prompt_value
            else:
                raise ValueError(f"Model {model_id} requires 'prompt' or 'text' field")
        
        # Image/Video input models: need url or file
        elif category in ['i2v', 'i2i', 'v2v', 'lip_sync', 'upscale', 'bg_remove', 'watermark_remove']:
            if url_value:
                # Determine correct field name based on category
                if 'image' in category or category in ['i2v', 'i2i', 'upscale', 'bg_remove']:
                    payload['input']['image_url'] = url_value
                elif 'video' in category or category == 'v2v':
                    payload['input']['video_url'] = url_value
                else:
                    payload['input']['source_url'] = url_value
            elif file_value:
                payload['input']['file_id'] = file_value
            else:
                raise ValueError(f"Model {model_id} (category: {category}) requires 'url' or 'file' field")
            
            # Optional prompt for guided processing
            if prompt_value:
                payload['input']['prompt'] = prompt_value
        
        # Audio models
        elif category in ['stt', 'audio_isolation']:
            if url_value:
                payload['input']['audio_url'] = url_value
            elif file_value:
                payload['input']['file_id'] = file_value
            else:
                raise ValueError(f"Model {model_id} (category: {category}) requires audio file or URL")
        
        # Unknown category: try to accept anything user provided
        else:
            logger.warning(f"Unknown category '{category}' for {model_id}, accepting all user inputs")
            for key, value in user_inputs.items():
                if value is not None:
                    payload['input'][key] = value
        
        return payload
    
    # Process required fields
    for field_name in required_fields:
        field_spec = properties.get(field_name, {})
        field_type = field_spec.get('type', 'string')
        
        # CRITICAL FIX: Для image-edit моделей prompt может быть пустой строкой, но должен присутствовать
        if field_name == 'prompt' and ('image-edit' in model_id.lower() or 'image_edit' in model_id.lower()):
            # Для image-edit моделей добавляем пустой prompt если отсутствует
            if field_name not in user_inputs:
                logger.debug(f"Image-edit model {model_id}: adding empty prompt as default")
                user_inputs['prompt'] = ""
        
        # Get value from user_inputs
        value = user_inputs.get(field_name)
        
        # If not provided, try common aliases
        if value is None:
            # Common field mappings
            if field_name in ['prompt', 'text', 'input', 'message']:
                value = user_inputs.get('text') or user_inputs.get('prompt') or user_inputs.get('input')
            elif field_name in ['url', 'link', 'source_url']:
                value = user_inputs.get('url') or user_inputs.get('link')
            elif field_name in ['file', 'file_id', 'file_url']:
                value = user_inputs.get('file') or user_inputs.get('file_id') or user_inputs.get('file_url')
        
        # Validate and set value
        if value is None:
            # Системные поля НИКОГДА не запрашиваем - они добавятся автоматически
            if field_name in SYSTEM_FIELDS:
                continue  # Skip, будет добавлено автоматически при создании задачи
            
            # КРИТИЧНО: Smart defaults для veo3_fast и V4
            # Эти модели имеют много required полей, но большинство имеют разумные defaults
            elif is_direct_format and model_id == 'veo3_fast':
                # veo3_fast defaults
                defaults = {
                    'imageUrls': [],
                    'watermark': False,
                    'aspectRatio': '16:9',
                    'seeds': [1],
                    'enableFallback': True,
                    'enableTranslation': False,
                    'generationType': 'prediction'
                }
                if field_name in defaults:
                    value = defaults[field_name]
                    logger.debug(f"✓ Using default for veo3_fast.{field_name}: {value}")
                elif field_name in required_fields:
                    logger.error(f"❌ Required field '{field_name}' is missing for veo3_fast")
                    raise ValueError(f"Required field '{field_name}' is missing")
            
            elif is_direct_format and model_id == 'V4':
                # V4 defaults
                defaults = {
                    'instrumental': False,
                    'customMode': False,
                    'style': '',
                    'title': '',
                    'negativeTags': '',
                    'vocalGender': 'male',
                    'styleWeight': 1.0,
                    'weirdnessConstraint': 1.0,
                    'audioWeight': 1.0,
                    'personaId': ''
                }
                if field_name in defaults:
                    value = defaults[field_name]
                    logger.debug(f"Using default for V4.{field_name}: {value}")
                elif field_name in required_fields:
                    raise ValueError(f"Required field '{field_name}' is missing")
            
            # Other required fields: raise error
            elif field_name in required_fields:
                raise ValueError(f"Required field '{field_name}' is missing")
        
        # Apply value to payload (if we have one after defaults/aliases)
        if value is not None:
            # Type conversion if needed
            # ВАЖНО: Проверяем boolean FIRST, т.к. bool является подклассом int в Python
            if field_type == 'boolean' or field_type == 'bool':
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                elif isinstance(value, bool):
                    # Already boolean, keep as is
                    pass
                else:
                    value = bool(value)
            elif field_type in ['array', 'list']:
                # Keep lists/arrays as-is
                if not isinstance(value, list):
                    value = [value]  # Wrap single value in list
            elif field_type == 'integer' or field_type == 'int':
                if not isinstance(value, (list, dict)):  # Don't convert complex types
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        raise ValueError(f"Field '{field_name}' must be an integer")
            elif field_type == 'number' or field_type == 'float':
                if not isinstance(value, (list, dict)):  # Don't convert complex types
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        raise ValueError(f"Field '{field_name}' must be a number")
            
            # КРИТИЧНО: Для ПРЯМОГО формата поля на верхнем уровне
            if is_direct_format:
                payload[field_name] = value
            else:
                payload['input'][field_name] = value
    
    # Process optional fields
    for field_name in optional_fields:
        field_spec = properties.get(field_name, {})
        field_type = field_spec.get('type', 'string')
        
        value = user_inputs.get(field_name)
        if value is not None:
            # Type conversion
            # ВАЖНО: Проверяем boolean FIRST, т.к. bool является подклассом int в Python
            if field_type == 'boolean' or field_type == 'bool':
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                elif isinstance(value, bool):
                    # Already boolean, keep as is
                    pass
                else:
                    value = bool(value)
            elif field_type == 'integer' or field_type == 'int':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    continue  # Skip invalid values
            elif field_type == 'number' or field_type == 'float':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    continue
            
            # КРИТИЧНО: Для ПРЯМОГО формата поля на верхнем уровне
            if is_direct_format:
                payload[field_name] = value
            else:
                payload['input'][field_name] = value
    
    # КРИТИЧНО: Для ПРЯМОГО формата добавляем системные поля
    if is_direct_format:
        if 'model' not in payload:
            payload['model'] = model_id
            logger.debug(f"✓ Auto-added 'model': {model_id}")
        
        # callBackUrl - опциональное поле, добавляем пустое значение если требуется
        if 'callBackUrl' not in payload:
            # Проверяем, требуется ли оно в schema
            if 'callBackUrl' in input_schema and input_schema['callBackUrl'].get('required'):
                # Добавляем пустую строку, т.к. это только для синхронного режима
                payload['callBackUrl'] = ""
                logger.debug(f"✓ Auto-added empty 'callBackUrl' (sync mode)")
    
    validate_payload_before_create_task(model_id, payload, model_schema)
    logger.info(f"🎯 FINAL PAYLOAD | Model: {model_id} | Keys: {list(payload.keys())}")
    return payload


def build_payload_from_text(model_id: str, text: str, **kwargs) -> Dict[str, Any]:
    """Convenience method to build payload from text input."""
    user_inputs = {'text': text, 'prompt': text, 'input': text, **kwargs}
    return build_payload(model_id, user_inputs)


def build_payload_from_url(model_id: str, url: str, **kwargs) -> Dict[str, Any]:
    """Convenience method to build payload from URL input."""
    user_inputs = {'url': url, 'link': url, 'source_url': url, **kwargs}
    return build_payload(model_id, user_inputs)


def build_payload_from_file(model_id: str, file_id: str, **kwargs) -> Dict[str, Any]:
    """Convenience method to build payload from file input."""
    user_inputs = {'file': file_id, 'file_id': file_id, 'file_url': file_id, **kwargs}
    return build_payload(model_id, user_inputs)
