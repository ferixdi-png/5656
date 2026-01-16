"""
Field constraints and options for KIE models.
Maps model_id.field_name to allowed options.
"""

FIELD_OPTIONS = {
    # z-image constraints (VERIFIED from validate_z_image.py)
    "z-image.aspect_ratio": [
        "1:1",
        "4:3",
        "3:4",
        "16:9",
        "9:16",
    ],
    
    # qwen models - FIXED with correct KIE enum values
    # Source: validate_qwen_text_to_image.py and KIE documentation
    "qwen/text-to-image.image_size": [
        "square",           # 1024x1024
        "square_hd",        # 2048x2048 (default)
        "portrait_4_3",     # 896x1152
        "portrait_16_9",    # 768x1344
        "landscape_4_3",    # 1152x896
        "landscape_16_9",   # 1344x768
    ],
    
    "qwen/image-edit.image_size": [
        "square",
        "square_hd",
        "portrait_4_3",
        "portrait_16_9",
        "landscape_4_3",
        "landscape_16_9",
    ],
    
    "qwen/image-to-image.output_format": [
        "png",
        "jpg",
        "webp",
    ],
    
    # bytedance/seedream (FIXED: use correct KIE API enum values from error logs)
    "bytedance/seedream.image_size": [
        "square_hd",        # 2048x2048 (default)
        "square",           # 1024x1024
        "portrait_hd",      # High-res portrait
        "portrait",         # Standard portrait
        "landscape_hd",     # High-res landscape
        "landscape",        # Standard landscape
        "512x512",          # Legacy small square
        "1024x1024",        # Standard square
    ],
    
    # Video aspect ratios (verified from validate_wan_*.py)
    "bytedance/v1-lite-text-to-video.aspect_ratio": [
        "9:16",
        "16:9",
        "1:1",
    ],
    
    "bytedance/v1-pro-text-to-video.aspect_ratio": [
        "9:16",
        "16:9",
        "1:1",
    ],
    
    "wan/2-5-text-to-video.aspect_ratio": [
        "16:9",
        "9:16",
        "1:1",
    ],
    
    "wan/2-2-a14b-text-to-video-turbo.aspect_ratio": [
        "16:9",
        "9:16",
        "1:1",
    ],
    
    "wan/2-2-a14b-image-to-video-turbo.aspect_ratio": [
        "auto",
        "16:9",
        "9:16",
        "1:1",
    ],
    
    # grok-imagine models (from SOURCE_OF_TRUTH)
    "grok-imagine/text-to-image.aspect_ratio": [
        "1:1",
        "3:2",      # Default from SOURCE_OF_TRUTH
        "2:3",
        "16:9",
        "9:16",
    ],
    
    # Google Imagen models (verified from validate_imagen4*.py)
    "google/imagen4.aspect_ratio": [
        "1:1",
        "16:9",
        "9:16",
        "3:4",
        "4:3",
    ],
    
    "google/imagen4-fast.aspect_ratio": [
        "1:1",
        "16:9",
        "9:16",
        "3:4",
        "4:3",
    ],
    
    "google/imagen4-ultra.aspect_ratio": [
        "1:1",
        "16:9",
        "9:16",
        "3:4",
        "4:3",
    ],
    
    # nano-banana models (from SOURCE_OF_TRUTH)
    "nano-banana-pro.aspect_ratio": [
        "1:1",      # Default
        "9:16",
    ],
    
    "nano-banana-pro.resolution": [
        "1K",       # Default
        "2K",
        "4K",
    ],
    
    "nano-banana-pro.output_format": [
        "png",      # Default
        "jpg",
    ],
    
    # google/nano-banana - TEXT2IMAGE
    # SOURCE: models/KIE_SOURCE_OF_TRUTH.json input_schema
    "google/nano-banana.image_size": [
        "1:1",                  # Default
        "portrait_hd",
        "square_hd",
        "landscape_hd",
        "1024x1024",
        "512x512",
        "portrait",
        "square",
        "landscape",
    ],
    "google/nano-banana.output_format": [
        "png",                  # Default
        "jpg",
        "webp",
    ],
    
    # Flux models (verified from validate_flux_2*.py)
    "flux-2/pro-image-to-image.aspect_ratio": [
        "1:1",
        "4:3",
        "3:4",
        "16:9",
        "9:16",
        "3:2",
        "2:3",
        "auto",
    ],
    
    "flux-2/pro-image-to-image.resolution": [
        "1K",
        "2K",
    ],
    
    "flux-2/pro-text-to-image.aspect_ratio": [
        "1:1",
        "4:3",
        "3:4",
        "16:9",
        "9:16",
        "3:2",
        "2:3",
    ],
    
    "flux-2/pro-text-to-image.resolution": [
        "1K",
        "2K",
    ],
    
    "flux-2/flex-image-to-image.aspect_ratio": [
        "1:1",
        "4:3",
        "3:4",
        "16:9",
        "9:16",
        "3:2",
        "2:3",
        "auto",
    ],
    
    "flux-2/flex-text-to-image.aspect_ratio": [
        "1:1",
        "4:3",
        "3:4",
        "16:9",
        "9:16",
        "3:2",
        "2:3",
    ],
}

# Required fields per model
REQUIRED_FIELDS = {
    "z-image": ["prompt", "aspect_ratio"],  # Both required for z-image
    "qwen/text-to-image": ["prompt", "image_size"],
    "qwen/image-edit": ["image_url", "image_size"],
}

# Russian field names mapping (API field -> Russian display name)
FIELD_NAMES_RU = {
    "prompt": "Запрос",
    "aspect_ratio": "Соотношение сторон",
    "image_size": "Размер изображения",
    "image_url": "URL изображения",
    "negative_prompt": "Негативный запрос",
    "num_inference_steps": "Количество шагов",
    "guidance_scale": "Степень следования запросу",
    "seed": "Зерно генерации",
    "width": "Ширина",
    "height": "Высота",
}

def get_russian_field_name(field_name: str) -> str:
    """
    Get Russian display name for a field.
    
    Args:
        field_name: API field name (e.g., 'aspect_ratio')
    
    Returns:
        Russian display name (e.g., 'Соотношение сторон')
    """
    return FIELD_NAMES_RU.get(field_name, field_name)

def get_field_options(model_id: str, field_name: str) -> list:
    """
    Get allowed options for a field.
    
    Args:
        model_id: Model identifier
        field_name: Field name
    
    Returns:
        List of allowed values, or empty list if no constraints
    """
    key = f"{model_id}.{field_name}"
    return FIELD_OPTIONS.get(key, [])

def has_field_constraints(model_id: str, field_name: str) -> bool:
    """Check if field has constraints."""
    key = f"{model_id}.{field_name}"
    return key in FIELD_OPTIONS

def get_required_fields(model_id: str) -> list:
    """
    Get list of required fields for a model.
    
    Args:
        model_id: Model identifier
    
    Returns:
        List of required field names, or empty list if none defined
    """
    return REQUIRED_FIELDS.get(model_id, [])

def validate_required_fields(model_id: str, provided_fields: dict) -> tuple[bool, str]:
    """
    Validate that all required fields are provided.
    
    Args:
        model_id: Model identifier
        provided_fields: Dict of provided field values
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    required = get_required_fields(model_id)
    if not required:
        return True, ""
    
    missing = [f for f in required if f not in provided_fields or not provided_fields[f]]
    if missing:
        # Use Russian field names in error message
        missing_ru = [get_russian_field_name(f) for f in missing]
        return False, f"Не заполнены обязательные поля: {', '.join(missing_ru)}"
    
    return True, ""
