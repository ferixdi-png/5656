"""
Flow type definitions and mapping for typed UX flows.
Each model gets a flow_type that determines the order and nature of user input collection.
"""
from typing import Dict, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Flow type constants
FLOW_TEXT2IMAGE = "text2image"
FLOW_TEXT2VIDEO = "text2video"
FLOW_TEXT2AUDIO = "text2audio"
FLOW_IMAGE2IMAGE = "image2image"
FLOW_IMAGE2VIDEO = "image2video"
FLOW_IMAGE_EDIT = "image_edit"
FLOW_IMAGE_UPSCALE = "image_upscale"
FLOW_VIDEO_EDIT = "video_edit"
FLOW_AUDIO_PROCESSING = "audio_processing"
FLOW_UNKNOWN = "unknown"

# Human-readable descriptions for each flow type
FLOW_DESCRIPTIONS = {
    FLOW_TEXT2IMAGE: "Создание изображения по описанию",
    FLOW_TEXT2VIDEO: "Создание видео по описанию",
    FLOW_TEXT2AUDIO: "Создание аудио/музыки по описанию",
    FLOW_IMAGE2IMAGE: "Преобразование изображения с промптом",
    FLOW_IMAGE2VIDEO: "Создание видео из изображения",
    FLOW_IMAGE_EDIT: "Редактирование изображения по инструкции",
    FLOW_IMAGE_UPSCALE: "Улучшение качества изображения/видео",
    FLOW_VIDEO_EDIT: "Редактирование видео",
    FLOW_AUDIO_PROCESSING: "Обработка аудио",
    FLOW_UNKNOWN: "Специальная обработка",
}

# Input order for each flow type
# CRITICAL: image_edit MUST collect image BEFORE prompt
FLOW_INPUT_ORDER = {
    FLOW_TEXT2IMAGE: ["prompt"],  # Text first
    FLOW_TEXT2VIDEO: ["prompt"],  # Text first
    FLOW_TEXT2AUDIO: ["prompt"],  # Text first
    FLOW_IMAGE2IMAGE: ["image_url", "prompt"],  # Image first, then prompt
    FLOW_IMAGE2VIDEO: ["image_url", "prompt"],  # Image first, then optional prompt
    FLOW_IMAGE_EDIT: ["image_url", "prompt"],  # Image FIRST (CRITICAL), then edit instructions
    FLOW_IMAGE_UPSCALE: ["image_url"],  # Only image, no prompt needed
    FLOW_VIDEO_EDIT: ["video_url", "prompt"],  # Video first, then instructions
    FLOW_AUDIO_PROCESSING: ["audio_url"],  # Audio first
    FLOW_UNKNOWN: [],  # Auto-detect from schema
}


def determine_flow_type(model_id: str, model_spec: Dict) -> str:
    """
    Determine input flow type based on model metadata.
    
    Returns one of:
    - text2image: prompt → image
    - text2video: prompt → video
    - text2audio: prompt → audio
    - image2image: image + prompt → image
    - image2video: image + prompt → video
    - image_edit: image + edit_prompt → edited_image (CRITICAL DISTINCTION)
    - image_upscale: image → upscaled_image
    - video_edit: video + prompt → edited_video
    - audio_processing: audio → processed_audio
    - unknown: auto-detect from schema
    """
    category = model_spec.get("category", "").lower()
    name = (model_spec.get("name") or model_spec.get("display_name") or "").lower()
    model_id_lower = model_id.lower()
    
    # Get input schema
    input_schema = model_spec.get("input_schema", {})
    input_field = input_schema.get("input", {})
    
    # Extract required fields from examples
    required_fields = []
    if "examples" in input_field:
        for example in input_field.get("examples", []):
            if isinstance(example, dict):
                required_fields = list(example.keys())
                break
    
    # Detect field presence
    has_image_url = any(f in required_fields for f in ["image_url", "image_urls", "input_image", "reference_image_urls", "image"])
    has_prompt = any(f in required_fields for f in ["prompt", "text"])
    has_video = any(f in required_fields for f in ["video_url", "video_urls"])
    has_audio = any(f in required_fields for f in ["audio_url", "audio_urls", "audio_file"])
    
    # Classification logic (order matters!)
    
    # 1. CRITICAL: Check edit/background_removal BEFORE generic image2image
    if any(keyword in model_id_lower for keyword in ["edit", "image-edit", "reframe"]):
        return FLOW_IMAGE_EDIT
    elif any(keyword in model_id_lower for keyword in ["remove-background", "background", "removal"]):
        return FLOW_IMAGE_UPSCALE  # Treat BG removal as image enhancement
    elif any(keyword in model_id_lower for keyword in ["watermark"]):
        return FLOW_VIDEO_EDIT if has_video else FLOW_IMAGE_EDIT
    elif "upscal" in name or "upscal" in model_id_lower:
        return FLOW_IMAGE_UPSCALE
    
    # 2. Multi-input combinations
    elif has_image_url and has_video:
        return FLOW_IMAGE2VIDEO
    elif has_image_url and has_prompt:
        return FLOW_IMAGE2IMAGE
    elif has_video and has_prompt:
        return FLOW_VIDEO_EDIT
    elif has_image_url:
        # Image-only input
        return FLOW_IMAGE_UPSCALE
    
    # 3. Audio flows
    elif has_audio:
        if has_prompt:
            return FLOW_TEXT2AUDIO
        else:
            return FLOW_AUDIO_PROCESSING
    
    # 4. Text-only flows (with category hints)
    elif has_prompt:
        if "video" in category or "v2-5-turbo-text-to-video" in model_id_lower or "veo3" in model_id_lower:
            return FLOW_TEXT2VIDEO
        elif "audio" in category or "music" in category:
            return FLOW_TEXT2AUDIO
        else:
            # Default text prompt = text2image
            return FLOW_TEXT2IMAGE
    
    # 5. Category-based fallbacks
    elif "video" in category:
        return FLOW_TEXT2VIDEO
    elif "music" in category or "audio" in category:
        return FLOW_TEXT2AUDIO
    elif "image" in category:
        return FLOW_TEXT2IMAGE
    else:
        logger.warning(f"Could not determine flow type for {model_id} (category={category}), using UNKNOWN")
        return FLOW_UNKNOWN


def get_flow_type(model_id: str, model_spec: Dict) -> str:
    """Get flow type for a model (cached)."""
    return determine_flow_type(model_id, model_spec)


def get_flow_description(flow_type: str) -> str:
    """Get human-readable description for flow type."""
    return FLOW_DESCRIPTIONS.get(flow_type, "Обработка")


def get_expected_input_order(flow_type: str) -> List[str]:
    """
    Get expected order of primary inputs for this flow type.
    
    CRITICAL for image_edit: returns ['image_url', 'prompt']
    This ensures image is collected BEFORE edit instructions.
    """
    return FLOW_INPUT_ORDER.get(flow_type, [])


def should_collect_image_first(flow_type: str) -> bool:
    """Returns True if this flow requires image upload before text prompt."""
    order = get_expected_input_order(flow_type)
    return len(order) > 0 and order[0] in ["image_url", "image_urls", "input_image"]


def should_collect_video_first(flow_type: str) -> bool:
    """Returns True if this flow requires video upload before text prompt."""
    order = get_expected_input_order(flow_type)
    return len(order) > 0 and order[0] in ["video_url", "video_urls"]


def should_collect_audio_first(flow_type: str) -> bool:
    """Returns True if this flow requires audio upload before text prompt."""
    order = get_expected_input_order(flow_type)
    return len(order) > 0 and order[0] in ["audio_url", "audio_urls", "audio_file"]


def get_prompt_field_label(flow_type: str, field_name: str) -> str:
    """
    Get contextual label for prompt field based on flow type.
    
    CRITICAL: For image_edit, "prompt" means "edit instructions", not "creation prompt".
    """
    if flow_type == FLOW_IMAGE_EDIT and field_name == "prompt":
        return "Инструкция для редактирования"
    elif flow_type in [FLOW_IMAGE2IMAGE, FLOW_IMAGE2VIDEO] and field_name == "prompt":
        return "Промпт для преобразования"
    elif flow_type == FLOW_VIDEO_EDIT and field_name == "prompt":
        return "Инструкция для редактирования видео"
    elif field_name == "prompt":
        return "Описание того, что создать"
    else:
        return field_name


def get_primary_required_fields(flow_type: str) -> List[str]:
    """
    Get list of EXACT field names that MUST be marked as required for this flow_type.
    
    This determines which fields from the model's schema are mandatory based on the
    flow type contract. Used to enforce that:
    - image_edit: image_url is required (collects photo first)
    - image2image: image_url is required (collects photo first)
    - image2video: image_url is required (collects photo first)
    - image_upscale: image_url is required (only input)
    - text2*: prompt is required
    - video_edit: video_url is required
    - audio: audio_url/audio_file is required
    
    Returns: list of field names to mark as required in properties
    """
    primary_required = FLOW_INPUT_ORDER.get(flow_type, [])
    return [f for f in primary_required if f in ["image_url", "image_urls", "input_image", 
                                                    "video_url", "video_urls",
                                                    "audio_url", "audio_urls", "audio_file",
                                                    "prompt", "text"]]
