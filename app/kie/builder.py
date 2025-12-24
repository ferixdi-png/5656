"""
Universal payload builder for Kie.ai createTask based on model schema from source_of_truth.
"""
import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def load_source_of_truth(file_path: str = "models/kie_api_models.json") -> Dict[str, Any]:
    """
    Load source of truth file.
    
    Priority:
    1. kie_parsed_models.json (v6 - auto-parsed from kie_pricing_raw.txt, 77 models)
    2. kie_api_models.json (v5 - from API docs)
    3. kie_source_of_truth_v4.json (v4 - category-specific)
    4. kie_source_of_truth.json (v3 - legacy)
    5. kie_models_source_of_truth.json (v2 - very old)
    """
    # Try v6 (auto-parsed) first
    v6_path = "models/kie_parsed_models.json"
    if os.path.exists(v6_path):
        logger.info(f"Using V6 (77 models): {v6_path}")
        file_path = v6_path
    # Try v5 (API docs)
    elif not os.path.exists(file_path):
        # Try v4
        v4_path = "models/kie_source_of_truth_v4.json"
        if os.path.exists(v4_path):
            logger.info(f"Using V4: {v4_path}")
            file_path = v4_path
        else:
            # Try v3
            v3_path = "models/kie_source_of_truth.json"
            if os.path.exists(v3_path):
                logger.warning(f"Using V3 (legacy): {v3_path}")
                file_path = v3_path
            else:
                # Try v2 (very old)
                v2_path = "models/kie_models_source_of_truth.json"
                if os.path.exists(v2_path):
                    logger.warning(f"Using V2 (very old): {v2_path}")
                    file_path = v2_path
                else:
                    logger.error(f"No source of truth file found")
                    return {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_model_schema(model_id: str, source_of_truth: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """Get model schema from source of truth."""
    if source_of_truth is None:
        source_of_truth = load_source_of_truth()
    
    models = source_of_truth.get('models', [])
    for model in models:
        if model.get('model_id') == model_id:
            return model
    
    logger.warning(f"Model {model_id} not found in source of truth")
    return None


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

    input_schema = model_schema.get('input_schema', {})
    
    # CRITICAL: Use api_endpoint for Kie.ai API (not model_id)
    api_endpoint = model_schema.get('api_endpoint', model_id)
    
    # Build payload based on schema
    payload = {
        'model': api_endpoint,  # Use api_endpoint, not model_id
        'input': {}  # All fields go into 'input' object
    }
    
    # Parse input_schema: support BOTH flat and nested formats
    # FLAT format (source_of_truth.json): {"field": {"type": "...", "required": true}}
    # NESTED format (old): {"required": [...], "properties": {...}}
    
    if 'properties' in input_schema:
        # Nested format
        required_fields = input_schema.get('required', [])
        properties = input_schema.get('properties', {})
        # Calculate optional fields as difference
        optional_fields = [k for k in properties.keys() if k not in required_fields]
    else:
        # Flat format - convert to nested
        properties = input_schema
        required_fields = [k for k, v in properties.items() if v.get('required', False)]
        optional_fields = [k for k in properties.keys() if k not in required_fields]
    
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
            if field_name in required_fields:
                raise ValueError(f"Required field '{field_name}' is missing")
        else:
            # Type conversion if needed
            if field_type == 'integer' or field_type == 'int':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Field '{field_name}' must be an integer")
            elif field_type == 'number' or field_type == 'float':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Field '{field_name}' must be a number")
            elif field_type == 'boolean' or field_type == 'bool':
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                value = bool(value)
            
            payload['input'][field_name] = value
    
    # Process optional fields
    for field_name in optional_fields:
        field_spec = properties.get(field_name, {})
        field_type = field_spec.get('type', 'string')
        
        value = user_inputs.get(field_name)
        if value is not None:
            # Type conversion
            if field_type == 'integer' or field_type == 'int':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    continue  # Skip invalid values
            elif field_type == 'number' or field_type == 'float':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    continue
            elif field_type == 'boolean' or field_type == 'bool':
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                value = bool(value)
            
            payload['input'][field_name] = value
    
    validate_payload_before_create_task(model_id, payload, model_schema)
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
