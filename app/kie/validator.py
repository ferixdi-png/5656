"""
Strict model contract validator.
Ensures impossible to reach createTask with invalid data.
"""
import logging
from typing import Dict, Any, Optional, List, Set
import re

logger = logging.getLogger(__name__)


class ModelContractError(Exception):
    """Raised when model contract is violated."""
    pass


def validate_input_type(value: Any, expected_type: str, field_name: str) -> None:
    """
    Validate input type matches expected type.
    
    Raises:
        ModelContractError: If type mismatch
    """
    if expected_type in ['file', 'file_id', 'file_url']:
        # File type: must be string (file_id or URL)
        if not isinstance(value, str):
            raise ModelContractError(
                f"Field '{field_name}' requires file (file_id or URL), "
                f"got {type(value).__name__}"
            )
        # Check if it's a valid file identifier or URL
        if not (value.startswith('http://') or value.startswith('https://') or len(value) > 10):
            raise ModelContractError(
                f"Field '{field_name}' requires valid file_id or file URL"
            )
    
    elif expected_type in ['url', 'link', 'source_url']:
        # URL type: must be valid HTTP/HTTPS URL
        if not isinstance(value, str):
            raise ModelContractError(
                f"Field '{field_name}' requires URL, got {type(value).__name__}"
            )
        if not (value.startswith('http://') or value.startswith('https://')):
            raise ModelContractError(
                f"Field '{field_name}' requires valid URL (http:// or https://)"
            )
    
    elif expected_type in ['text', 'string', 'prompt', 'input', 'message']:
        # Text type: must be non-empty string
        if not isinstance(value, str):
            raise ModelContractError(
                f"Field '{field_name}' requires text, got {type(value).__name__}"
            )
        if not value.strip():
            raise ModelContractError(
                f"Field '{field_name}' requires non-empty text"
            )
    
    elif expected_type in ['integer', 'int']:
        # Integer type
        if not isinstance(value, (int, str)):
            raise ModelContractError(
                f"Field '{field_name}' requires integer, got {type(value).__name__}"
            )
        try:
            int(value)
        except (ValueError, TypeError):
            raise ModelContractError(
                f"Field '{field_name}' must be a valid integer"
            )
    
    elif expected_type in ['number', 'float']:
        # Number type
        if not isinstance(value, (int, float, str)):
            raise ModelContractError(
                f"Field '{field_name}' requires number, got {type(value).__name__}"
            )
        try:
            float(value)
        except (ValueError, TypeError):
            raise ModelContractError(
                f"Field '{field_name}' must be a valid number"
            )
    
    elif expected_type in ['boolean', 'bool']:
        # Boolean type
        if not isinstance(value, (bool, str, int)):
            raise ModelContractError(
                f"Field '{field_name}' requires boolean, got {type(value).__name__}"
            )


def validate_model_inputs(
    model_id: str,
    model_schema: Dict[str, Any],
    user_inputs: Dict[str, Any]
) -> None:
    """
    Strictly validate user inputs against model schema.
    
    Contract:
    - Model MUST accept the provided input types
    - File-requiring models MUST NOT accept text
    - URL-requiring models MUST NOT accept file uploads
    - Required fields MUST be present
    
    Raises:
        ModelContractError: If contract is violated
    """
    input_schema = model_schema.get('input_schema', {})
    
    # FALLBACK: If no properties defined in schema, validate based on category
    if not input_schema or not input_schema.get('properties'):
        logger.info(f"Using fallback validation for {model_id} (no schema properties)")
        
        category = model_schema.get('category', '')
        
        # Get available inputs
        has_prompt = bool(user_inputs.get('prompt') or user_inputs.get('text'))
        has_url = bool(user_inputs.get('url') or user_inputs.get('image_url') or 
                      user_inputs.get('video_url') or user_inputs.get('audio_url'))
        has_file = bool(user_inputs.get('file') or user_inputs.get('file_id'))
        
        # Text-based models require prompt
        if category in ['t2i', 't2v', 'tts', 'music', 'sfx'] or 'text' in model_id.lower():
            if not has_prompt:
                raise ModelContractError(
                    f"Text-based model {model_id} requires 'prompt' or 'text' field"
                )
        
        # Media input models require url or file
        elif category in ['i2v', 'i2i', 'v2v', 'lip_sync', 'upscale', 'bg_remove', 
                         'watermark_remove', 'stt', 'audio_isolation']:
            if not has_url and not has_file:
                raise ModelContractError(
                    f"Media model {model_id} requires URL or file input"
                )
        
        # Unknown category: accept if any input provided
        else:
            if not user_inputs or all(v is None for v in user_inputs.values()):
                raise ModelContractError(
                    f"Model {model_id} requires at least one input"
                )
        
        # Fallback validation passed
        return
    
    required_fields = input_schema.get('required', [])
    optional_fields = input_schema.get('optional', [])
    properties = input_schema.get('properties', {})
    
    all_fields = set(required_fields) | set(optional_fields)
    
    # Check required fields
    for field_name in required_fields:
        if field_name not in user_inputs:
            # Try common aliases
            value = None
            field_spec = properties.get(field_name, {})
            field_type = field_spec.get('type', 'string')
            
            # Common field mappings
            if field_name in ['prompt', 'text', 'input', 'message']:
                value = user_inputs.get('text') or user_inputs.get('prompt') or user_inputs.get('input')
            elif field_name in ['url', 'link', 'source_url']:
                value = user_inputs.get('url') or user_inputs.get('link')
            elif field_name in ['file', 'file_id', 'file_url']:
                value = user_inputs.get('file') or user_inputs.get('file_id') or user_inputs.get('file_url')
            
            if value is None:
                raise ModelContractError(
                    f"Model {model_id} requires field '{field_name}' (type: {field_type}), "
                    f"but it is missing from user inputs"
                )
    
    # Validate field types and constraints
    for field_name in all_fields:
        field_spec = properties.get(field_name, {})
        field_type = field_spec.get('type', 'string')
        
        # Get value (with alias resolution)
        value = user_inputs.get(field_name)
        if value is None:
            # Try aliases
            if field_name in ['prompt', 'text', 'input', 'message']:
                value = user_inputs.get('text') or user_inputs.get('prompt') or user_inputs.get('input')
            elif field_name in ['url', 'link', 'source_url']:
                value = user_inputs.get('url') or user_inputs.get('link')
            elif field_name in ['file', 'file_id', 'file_url']:
                value = user_inputs.get('file') or user_inputs.get('file_id') or user_inputs.get('file_url')
        
        # Skip validation if field is optional and not provided
        if value is None and field_name in optional_fields:
            continue
        
        # Validate type
        if value is not None:
            validate_input_type(value, field_type, field_name)
            
            # Check enum constraints
            if 'enum' in field_spec:
                enum_values = field_spec['enum']
                if value not in enum_values:
                    raise ModelContractError(
                        f"Field '{field_name}' must be one of {enum_values}, got '{value}'"
                    )
            
            # Check min/max constraints
            if 'minimum' in field_spec:
                try:
                    num_value = float(value)
                    if num_value < field_spec['minimum']:
                        raise ModelContractError(
                            f"Field '{field_name}' must be >= {field_spec['minimum']}, got {num_value}"
                        )
                except (ValueError, TypeError):
                    pass  # Type validation will catch this
            
            if 'maximum' in field_spec:
                try:
                    num_value = float(value)
                    if num_value > field_spec['maximum']:
                        raise ModelContractError(
                            f"Field '{field_name}' must be <= {field_spec['maximum']}, got {num_value}"
                        )
                except (ValueError, TypeError):
                    pass  # Type validation will catch this
    
    # Cross-field validation: file vs text vs URL
    # If model requires file, reject text/URL
    file_fields = [f for f in all_fields 
                   if properties.get(f, {}).get('type') in ['file', 'file_id', 'file_url']]
    text_fields = [f for f in all_fields 
                   if properties.get(f, {}).get('type') in ['text', 'string', 'prompt', 'input', 'message']]
    url_fields = [f for f in all_fields 
                  if properties.get(f, {}).get('type') in ['url', 'link', 'source_url']]
    
    # Check for type conflicts
    has_file_input = any(
        user_inputs.get(f) or 
        user_inputs.get('file') or 
        user_inputs.get('file_id') or 
        user_inputs.get('file_url')
        for f in file_fields
    )
    
    has_text_input = any(
        user_inputs.get(f) or 
        user_inputs.get('text') or 
        user_inputs.get('prompt') or 
        user_inputs.get('input')
        for f in text_fields
    )
    
    has_url_input = any(
        user_inputs.get(f) or 
        user_inputs.get('url') or 
        user_inputs.get('link')
        for f in url_fields
    )
    
    # If model requires file but got text/URL
    if file_fields and required_fields:
        required_file_fields = [f for f in file_fields if f in required_fields]
        if required_file_fields and not has_file_input:
            if has_text_input:
                raise ModelContractError(
                    f"Model {model_id} requires file input, but text was provided. "
                    f"Please provide a file instead."
                )
            if has_url_input:
                raise ModelContractError(
                    f"Model {model_id} requires file input, but URL was provided. "
                    f"Please provide a file instead."
                )
    
    # If model requires URL but got file
    if url_fields and required_fields:
        required_url_fields = [f for f in url_fields if f in required_fields]
        if required_url_fields and not has_url_input:
            if has_file_input:
                raise ModelContractError(
                    f"Model {model_id} requires URL input, but file was provided. "
                    f"Please provide a URL instead."
                )
    
    # If model requires text but got file/URL
    if text_fields and required_fields:
        required_text_fields = [f for f in text_fields if f in required_fields]
        if required_text_fields and not has_text_input:
            if has_file_input:
                raise ModelContractError(
                    f"Model {model_id} requires text input, but file was provided. "
                    f"Please provide text instead."
                )
            if has_url_input:
                raise ModelContractError(
                    f"Model {model_id} requires text input, but URL was provided. "
                    f"Please provide text instead."
                )


def validate_payload_before_create_task(
    model_id: str,
    payload: Dict[str, Any],
    model_schema: Dict[str, Any]
) -> None:
    """
    Final validation before createTask API call.
    
    Contract:
    - Payload MUST contain 'model' field
    - Payload MUST contain 'input' object
    - All required fields MUST be present in 'input'
    - No invalid field types
    
    Raises:
        ModelContractError: If payload is invalid
    """
    if 'model' not in payload:
        raise ModelContractError("Payload must contain 'model' field")
    
    if payload['model'] != model_id:
        raise ModelContractError(
            f"Payload model '{payload['model']}' does not match requested model '{model_id}'"
        )
    
    # Check 'input' object exists
    if 'input' not in payload:
        raise ModelContractError("Payload must contain 'input' object")
    
    input_data = payload['input']
    if not isinstance(input_data, dict):
        raise ModelContractError("Payload 'input' must be a dictionary")
    
    input_schema = model_schema.get('input_schema', {})
    required_fields = input_schema.get('required', [])
    properties = input_schema.get('properties', {})
    
    # Check all required fields are in payload['input']
    for field_name in required_fields:
        if field_name not in input_data:
            raise ModelContractError(
                f"Required field '{field_name}' is missing from payload['input']"
            )
        
        # Validate type
        field_spec = properties.get(field_name, {})
        field_type = field_spec.get('type', 'string')
        value = input_data[field_name]
        
        try:
            validate_input_type(value, field_type, field_name)
        except ModelContractError as e:
            raise ModelContractError(
                f"Payload validation failed for field '{field_name}': {str(e)}"
            )

