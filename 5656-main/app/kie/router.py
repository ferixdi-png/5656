"""
API Router для новой архитектуры Kie.ai.
Маршрутизирует запросы к правильным category-specific endpoints.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache

from app.kie.field_options import get_field_options
from app.utils.webhook import build_kie_callback_url

logger = logging.getLogger(__name__)

# Загрузка source of truth с кэшированием
@lru_cache(maxsize=1)
def load_v4_source_of_truth() -> Dict[str, Any]:
    """
    Load source of truth with new API architecture (cached for performance).
    
    Tries in order:
    1. models/kie_source_of_truth_v4.json (old name)
    2. models/KIE_SOURCE_OF_TRUTH.json (new canonical name)
    3. Fallback to stub
    
    Note: Cached with @lru_cache to avoid repeated file reads on hot path.
    """
    # Try old v4 path first (for backwards compatibility)
    v4_path_old = Path(__file__).parent.parent.parent / "models" / "kie_source_of_truth_v4.json"
    if v4_path_old.exists():
        logger.info(f"✅ Loading SOURCE_OF_TRUTH (cached): {v4_path_old}")
        with open(v4_path_old, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Try new canonical path
    sot_path = Path(__file__).parent.parent.parent / "models" / "KIE_SOURCE_OF_TRUTH.json"
    if sot_path.exists():
        logger.info(f"✅ Loading SOURCE_OF_TRUTH (cached): {sot_path}")
        with open(sot_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Fallback to stub
    logger.warning("No source of truth found, using empty stub")
    return {"version": "stub", "models": {}, "categories": {}}


def get_api_category_for_model(model_id: str, source_v4: Optional[Dict] = None) -> Optional[str]:
    """
    Determine which API category a model belongs to.
    
    Args:
        model_id: Model identifier (e.g. 'veo3', 'suno-v4', 'gpt-4o-image')
        source_v4: Optional pre-loaded v4 source of truth
    
    Returns:
        API category name ('veo3', 'suno', 'runway', etc.) or None
    """
    if source_v4 is None:
        source_v4 = load_v4_source_of_truth()
    
    # Handle both dict and list structures
    models = source_v4.get('models', {})
    
    # If models is dict (new format), iterate over values
    if isinstance(models, dict):
        for model_id_key, model in models.items():
            if model.get('model_id') == model_id:
                return model.get('category')  # Use 'category' field from new SOT
    # If models is list (old v4 format), iterate directly
    elif isinstance(models, list):
        for model in models:
            if model.get('model_id') == model_id:
                return model.get('api_category')
    
    logger.warning(f"Model {model_id} not found in source of truth")
    return None


def _default_callback_url() -> str:
    """Return a real callback URL built from webhook env settings."""
    return build_kie_callback_url()


def build_category_payload(
    model_id: str, 
    user_inputs: Dict[str, Any],
    source_v4: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Build payload for category-specific API endpoint.
    
    Handles both:
    - Direct format: {prompt: "...", aspect_ratio: "1:1"}
    - Wrapped format: {model: "z-image", input: {prompt: "...", aspect_ratio: "1:1"}, callBackUrl: "..."}
    
    Args:
        model_id: Model ID
        user_inputs: User-provided inputs (should NOT include model/callBackUrl)
        source_v4: Optional pre-loaded v4 source of truth
    
    Returns:
        Payload dict ready for category-specific API
    """
    # BATCH 48.51: Unwrap if user_inputs is already wrapped (contains model/callBackUrl/input)
    # This can happen if build_category_payload is called twice or user_inputs is pre-wrapped
    if 'model' in user_inputs or 'callBackUrl' in user_inputs:
        if 'input' in user_inputs and isinstance(user_inputs['input'], dict):
            # Extract inner input dict
            logger.debug(f"Unwrapping pre-wrapped payload for model {model_id}")
            user_inputs = user_inputs['input']
        elif 'input' not in user_inputs:
            # Has model/callBackUrl but no input - likely already a payload, extract only input fields
            # Remove system fields (model, callBackUrl) and keep only input fields
            user_inputs = {k: v for k, v in user_inputs.items() if k not in ('model', 'callBackUrl')}
            logger.debug(f"Removed system fields from pre-wrapped payload for model {model_id}")
    
    if source_v4 is None:
        source_v4 = load_v4_source_of_truth()
    
    # Handle both dict and list structures
    models = source_v4.get('models', {})
    
    model_schema = None
    # If models is dict (new format)
    if isinstance(models, dict):
        model_schema = models.get(model_id)
    # If models is list (old v4 format)
    elif isinstance(models, list):
        for model in models:
            if model.get('model_id') == model_id:
                model_schema = model
                break
    
    if not model_schema:
        raise ValueError(f"Model {model_id} not found in source of truth")
    
    category = model_schema.get('category') or model_schema.get('api_category')
    input_schema = model_schema.get('input_schema', {})
    
    # CRITICAL: input_schema in SOURCE_OF_TRUTH is PROPERTIES DIRECTLY, not {properties: ...}
    # Check format
    if 'properties' in input_schema and isinstance(input_schema['properties'], dict):
        # Nested format: {properties: {...}, required: [...]}
        properties = input_schema.get('properties', {})
        required_fields = input_schema.get('required', [])
    else:
        # FLAT format (SOURCE_OF_TRUTH): input_schema IS properties dict directly
        # Example: {'model': {...}, 'callBackUrl': {...}, 'input': {...}}
        properties = input_schema
        required_fields = [k for k, v in properties.items() if v.get('required', False)]
    
    # CRITICAL: Filter out system fields from required - they're added by system
    system_fields = {'model', 'callBackUrl', 'webhookUrl'}
    user_required_fields = [f for f in required_fields if f not in system_fields]
    
    # IMPORTANT: Check if this is wrapped format (input field contains dict)
    has_input_wrapper = False
    actual_properties = properties
    
    if 'input' in properties and isinstance(properties['input'], dict):
        input_field_spec = properties['input']
        
        # Check if input has examples
        if 'examples' in input_field_spec and isinstance(input_field_spec['examples'], list):
            examples = input_field_spec['examples']
            if examples and isinstance(examples[0], dict):
                # Extract field list from first example
                example_structure = examples[0]
                actual_properties = {}
                for field_name, field_value in example_structure.items():
                    # Infer type from example value
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
                    
                    actual_properties[field_name] = {
                        'type': field_type,
                        'required': False  # Conservative default
                    }
                
                # Mark prompt as required if it exists
                if 'prompt' in actual_properties:
                    actual_properties['prompt']['required'] = True
                
                has_input_wrapper = True
                logger.debug(f"Extracted input wrapper schema for {model_id}: {list(actual_properties.keys())}")
        
        elif 'properties' in input_field_spec:
            # input has nested properties schema
            actual_properties = input_field_spec['properties']
            has_input_wrapper = True
            logger.debug(f"Using nested input properties for {model_id}")
    
    # Build payload
    payload = {
        'model': model_id,
        'callBackUrl': _default_callback_url(),
    }
    
    # If wrapped format, add input container
    if has_input_wrapper:
        payload['input'] = {}
    
    # Process fields
    user_field_names = set(actual_properties.keys()) - system_fields
    
    # BATCH 48.47: Handle field aliases for image-to-image and image-edit models
    # Map common aliases to actual field names (e.g., url -> image_url for image-to-image/image-edit)
    field_aliases = {}
    if 'image-to-image' in model_id.lower() or 'image_to_image' in model_id.lower() or \
       'image-edit' in model_id.lower() or 'image_edit' in model_id.lower():
        # For image-to-image and image-edit models, map url -> image_url
        if 'image_url' in actual_properties:
            field_aliases['url'] = 'image_url'
            field_aliases['input_url'] = 'image_url'
            field_aliases['imageUrl'] = 'image_url'
    elif 'video' in model_id.lower() and 'to' in model_id.lower():
        # For video models, map url -> video_url
        if 'video_url' in actual_properties:
            field_aliases['url'] = 'video_url'
            field_aliases['input_url'] = 'video_url'
    
    for field_name in user_field_names:
        field_spec = actual_properties.get(field_name, {})
        is_required = field_spec.get('required', False)
        
        # BATCH 48.47: Check field name and aliases
        value = None
        if field_name in user_inputs:
            value = user_inputs[field_name]
        else:
            # Check aliases
            for alias, actual_field in field_aliases.items():
                if alias in user_inputs and actual_field == field_name:
                    value = user_inputs[alias]
                    logger.debug(f"Using alias '{alias}' -> '{field_name}' for model {model_id}")
                    break
        
        if value is not None:
            # BATCH 48.50: Ensure string enum values remain strings (e.g., n_frames="10" not 10)
            # For sora-2 models, n_frames must be string ("10" or "15"), not integer
            if field_name == 'n_frames' and isinstance(value, (int, float)):
                # Convert numeric n_frames to string for sora-2 models
                value = str(int(value))
                logger.debug(f"Converted n_frames from number to string: {value} for model {model_id}")
            
            # Validate enum constraints if present
            field_enum = field_spec.get('enum')
            if not field_enum:
                # Check if field has predefined options
                field_enum = get_field_options(model_id, field_name)
                if field_enum:
                    field_spec['enum'] = field_enum
            
            if field_enum and value not in field_enum:
                logger.warning(
                    f"Field '{field_name}' value '{value}' not in allowed options {field_enum} "
                    f"for model {model_id}"
                )
            
            if has_input_wrapper:
                payload['input'][field_name] = value
            else:
                payload[field_name] = value
        elif is_required and 'default' in field_spec:
            default_value = field_spec['default']
            if has_input_wrapper:
                payload['input'][field_name] = default_value
            else:
                payload[field_name] = default_value
        elif is_required:
            logger.warning(f"Required field '{field_name}' missing for model {model_id}")
    
    logger.info(f"Built {category} payload for {model_id}: {list(payload.keys())}")
    
    # DETAILED LOGGING FOR DEBUGGING
    logger.debug(f"  - has_input_wrapper: {has_input_wrapper}")
    logger.debug(f"  - user_inputs keys: {list(user_inputs.keys())}")
    if has_input_wrapper:
        logger.debug(f"  - payload['input'] keys: {list(payload.get('input', {}).keys())}")
        logger.debug(f"  - payload['input'] content: {payload.get('input', {})}")
    else:
        logger.debug(f"  - payload top-level keys: {[k for k in payload.keys() if k not in ['model', 'callBackUrl']]}")
    
    return payload


def get_api_endpoint_for_model(model_id: str, source_v4: Optional[Dict] = None) -> str:
    """
    Get the full API endpoint path for a model.
    
    Args:
        model_id: Model ID
        source_v4: Optional pre-loaded v4 source of truth
    
    Returns:
        Full endpoint path (e.g. '/api/v1/jobs/createTask')
    """
    if source_v4 is None:
        source_v4 = load_v4_source_of_truth()
    
    # Handle both dict and list structures
    models = source_v4.get('models', {})
    
    # If models is dict (new format)
    if isinstance(models, dict):
        model = models.get(model_id)
        if model:
            return model.get('endpoint', '/api/v1/jobs/createTask')
    # If models is list (old v4 format)
    elif isinstance(models, list):
        for model in models:
            if model.get('model_id') == model_id:
                return model.get('api_endpoint', '/api/v1/jobs/createTask')
    
    # Fallback to default endpoint
    logger.warning(f"Model {model_id} not found, using default endpoint")
    return '/api/v1/jobs/createTask'


def get_base_url_for_category(category: str, source_v4: Optional[Dict] = None) -> str:
    """
    Get base URL for API category.
    
    Args:
        category: API category ('veo3', 'suno', etc.)
        source_v4: Optional pre-loaded v4 source of truth
    
    Returns:
        Base URL (typically 'https://api.kie.ai')
    """
    if source_v4 is None:
        source_v4 = load_v4_source_of_truth()
    
    categories = source_v4.get('categories', {})
    if category in categories:
        return categories[category].get('base_url', 'https://api.kie.ai')
    
    # Fallback
    return 'https://api.kie.ai'


# Compatibility helpers для старого кода
def is_v4_model(model_id: str) -> bool:
    """Check if model exists in v4 source of truth."""
    try:
        source_v4 = load_v4_source_of_truth()
        models = source_v4.get('models', {})
        # models is dict, not list
        return model_id in models
    except Exception as e:
        logger.error(f"Failed to check v4 model: {e}")
        return False


def get_all_v4_models() -> list:
    """Get list of all available v4 models."""
    try:
        source_v4 = load_v4_source_of_truth()
        models = source_v4.get('models', {})
        # models is dict - return list of model objects
        return list(models.values())
    except Exception as e:
        logger.error(f"Failed to load v4 models: {e}")
        return []
