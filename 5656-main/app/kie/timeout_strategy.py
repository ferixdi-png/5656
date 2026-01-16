"""
Category-based timeout strategy for KIE AI generations.

Different model categories require different wait times:
- Images: Fast (60-90s)
- Videos: Slow (180-300s)
- Audio: Medium (120-180s)
- Text: Fast (30-60s)
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Timeout constants by category (in seconds)
TIMEOUT_IMAGE = 90      # Image generation: 1.5 minutes
TIMEOUT_VIDEO = 300     # Video generation: 5 minutes (longest)
TIMEOUT_AUDIO = 180     # Audio generation: 3 minutes
TIMEOUT_TEXT = 60       # Text generation: 1 minute
TIMEOUT_DEFAULT = 180   # Default fallback: 3 minutes


def get_timeout_for_model(model_id: str, category: Optional[str] = None) -> int:
    """
    Get appropriate timeout for model based on category.
    
    Args:
        model_id: Model identifier
        category: Optional category (image/video/audio/text)
        
    Returns:
        Timeout in seconds
    """
    # If category provided explicitly, use it
    if category:
        return get_timeout_for_category(category)
    
    # Otherwise, infer from model_id
    category = infer_category_from_model_id(model_id)
    timeout = get_timeout_for_category(category)
    
    logger.info(
        f"[TIMEOUT_STRATEGY] model_id={model_id} category={category} timeout={timeout}s"
    )
    
    return timeout


def get_timeout_for_category(category: str) -> int:
    """
    Get timeout for specific category.
    
    Args:
        category: Category name (image/video/audio/text)
        
    Returns:
        Timeout in seconds
    """
    category_lower = category.lower()
    
    if "image" in category_lower or "photo" in category_lower or "picture" in category_lower:
        return TIMEOUT_IMAGE
    elif "video" in category_lower or "movie" in category_lower or "animation" in category_lower:
        return TIMEOUT_VIDEO
    elif "audio" in category_lower or "sound" in category_lower or "music" in category_lower or "voice" in category_lower:
        return TIMEOUT_AUDIO
    elif "text" in category_lower or "chat" in category_lower or "language" in category_lower:
        return TIMEOUT_TEXT
    else:
        logger.warning(
            f"[TIMEOUT_STRATEGY] Unknown category '{category}', using default timeout {TIMEOUT_DEFAULT}s"
        )
        return TIMEOUT_DEFAULT


def infer_category_from_model_id(model_id: str) -> str:
    """
    Infer category from model ID string.
    
    Args:
        model_id: Model identifier
        
    Returns:
        Inferred category (image/video/audio/text)
    """
    model_lower = model_id.lower()
    
    # Check for video indicators
    video_keywords = ["video", "veo", "movie", "animation", "runway", "pika", "kling", "hailuo"]
    if any(kw in model_lower for kw in video_keywords):
        return "video"
    
    # Check for audio indicators
    audio_keywords = ["audio", "sound", "music", "voice", "tts", "speech", "eleven"]
    if any(kw in model_lower for kw in audio_keywords):
        return "audio"
    
    # Check for text indicators
    text_keywords = ["text", "chat", "gpt", "language", "llm", "grok", "claude"]
    if any(kw in model_lower for kw in text_keywords):
        return "text"
    
    # Check for image indicators (most common, so check last)
    image_keywords = ["image", "photo", "picture", "flux", "midjourney", "dall", "stable", "sd"]
    if any(kw in model_lower for kw in image_keywords):
        return "image"
    
    # Default to image (most models are image models)
    logger.debug(
        f"[TIMEOUT_STRATEGY] Could not infer category for '{model_id}', defaulting to 'image'"
    )
    return "image"


def get_timeout_description(timeout: int) -> str:
    """
    Get user-friendly description of timeout.
    
    Args:
        timeout: Timeout in seconds
        
    Returns:
        Russian description
    """
    if timeout <= 60:
        return "до 1 минуты"
    elif timeout <= 120:
        return "до 2 минут"
    elif timeout <= 180:
        return "до 3 минут"
    elif timeout <= 240:
        return "до 4 минут"
    elif timeout <= 300:
        return "до 5 минут"
    else:
        minutes = timeout // 60
        return f"до {minutes} минут"

