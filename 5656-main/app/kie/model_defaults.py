"""
Model-specific default values for optional/required parameters.
Used when user doesn't provide value via UI.

CRITICAL: These defaults ensure models can run without validation errors.
Source: KIE API error messages + SOURCE_OF_TRUTH examples.
"""
from typing import Dict, Any


# Model-specific defaults (keyed by model_id)
# AUTO-GENERATED from SOURCE_OF_TRUTH examples (69 models)
# SOURCE: models/KIE_SOURCE_OF_TRUTH.json -> input.examples[0]
MODEL_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "bytedance/seedream": {
        "image_size": "square_hd",
        "guidance_scale": 2.5,
        "enable_safety_checker": True,
    },
    
    "bytedance/seedream-v4-edit": {
        "image_urls": ["https://example.com/image.jpg"],
        "image_size": "square_hd",
        "image_resolution": "1K",
        "max_images": 1,
    },
    
    "bytedance/seedream-v4-text-to-image": {
        "image_size": "square_hd",
        "image_resolution": "1K",
        "max_images": 1,
    },
    
    "bytedance/v1-lite-image-to-video": {
        "image_url": "https://example.com/image.jpg",
        "resolution": "720p",
        "duration": "5",
        "camera_fixed": False,
        "seed": -1,
        "enable_safety_checker": True,
    },
    
    "bytedance/v1-lite-text-to-video": {
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "duration": "5",
        "camera_fixed": False,
        "enable_safety_checker": True,
    },
    
    "bytedance/v1-pro-fast-image-to-video": {
        "image_url": "https://example.com/image.jpg",
        "resolution": "720p",
        "duration": "5",
    },
    
    "bytedance/v1-pro-image-to-video": {
        "image_url": "https://example.com/image.jpg",
        "resolution": "720p",
        "duration": "5",
        "camera_fixed": False,
        "seed": -1,
        "enable_safety_checker": True,
    },
    
    "bytedance/v1-pro-text-to-video": {
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "duration": "5",
        "camera_fixed": False,
        "seed": -1,
        "enable_safety_checker": True,
    },
    
    "elevenlabs/audio-isolation": {
        "audio_url": "https://example.com/audio.mp3",
    },
    
    "elevenlabs/sound-effect-v2": {
        "text": "",
        "loop": False,
        "prompt_influence": 0.3,
        "output_format": "mp3_44100_128",
    },
    
    "elevenlabs/speech-to-text": {
        "audio_url": "https://example.com/audio.mp3",
        "language_code": "",
        "tag_audio_events": True,
        "diarize": True,
    },
    
    "elevenlabs/text-to-speech-turbo-2-5": {
        "text": "Unlock powerful API with Kie.ai!",
        "voice": "Rachel",
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0,
        "speed": 1,
        "timestamps": False,
        "previous_text": "",
        "next_text": "",
        "language_code": "",
    },
    
    "flux-2/flex-image-to-image": {
        "input_urls": ["https://example.com/image.jpg"],
        "aspect_ratio": "1:1",
        "resolution": "1K",
    },
    
    "flux-2/flex-text-to-image": {
        "aspect_ratio": "1:1",
        "resolution": "1K",
    },
    
    "flux-2/pro-image-to-image": {
        "input_urls": ["https://example.com/image.jpg"],
        "aspect_ratio": "1:1",
        "resolution": "1K",
    },
    
    "flux-2/pro-text-to-image": {
        "aspect_ratio": "1:1",
        "resolution": "1K",
    },
    
    "google/imagen4": {
        "negative_prompt": "",
        "aspect_ratio": "1:1",
        "num_images": "1",
        "seed": "",
    },
    
    "google/imagen4-fast": {
        "negative_prompt": "",
        "aspect_ratio": "16:9",
        "num_images": "1",
    },
    
    "google/imagen4-ultra": {
        "negative_prompt": "",
        "aspect_ratio": "1:1",
        "seed": "",
    },
    
    "google/nano-banana": {
        "output_format": "png",
        "image_size": "1:1",
    },
    
    "google/nano-banana-edit": {
        "image_urls": ["https://example.com/image.jpg"],
        "output_format": "png",
        "image_size": "1:1",
    },
    
    "grok-imagine/image-to-video": {
        "image_urls": ["https://example.com/image.jpg"],
        "mode": "normal",
    },
    
    "grok-imagine/text-to-image": {
        "aspect_ratio": "3:2",
    },
    
    "grok-imagine/text-to-video": {
        "aspect_ratio": "2:3",
        "mode": "normal",
    },
    
    "grok-imagine/upscale": {
        "task_id": "task_grok_12345678",
    },
    
    "hailuo/02-image-to-video-pro": {
        "image_url": "https://example.com/image.jpg",
        "end_image_url": "",
        "prompt_optimizer": True,
    },
    
    "hailuo/02-image-to-video-standard": {
        "image_url": "https://example.com/image.jpg",
        "end_image_url": "https://example.com/image2.jpg",
        "duration": "10",
        "resolution": "768P",
        "prompt_optimizer": True,
    },
    
    "hailuo/02-text-to-video-pro": {
        "prompt_optimizer": True,
    },
    
    "hailuo/02-text-to-video-standard": {
        "duration": "6",
        "prompt_optimizer": True,
    },
    
    "hailuo/2-3-image-to-video-pro": {
        "image_url": "https://example.com/image.jpg",
        "duration": "6",
        "resolution": "768P",
    },
    
    "hailuo/2-3-image-to-video-standard": {
        "image_url": "https://example.com/image.jpg",
        "duration": "6",
        "resolution": "768P",
    },
    
    "ideogram/character": {
        "reference_image_urls": ["https://example.com/ref.jpg"],
        "rendering_speed": "BALANCED",
        "style": "AUTO",
        "expand_prompt": True,
        "num_images": "1",
        "image_size": "square_hd",
        "negative_prompt": "",
    },
    
    "ideogram/character-edit": {
        "image_url": "https://example.com/image.jpg",
        "mask_url": "https://example.com/mask.jpg",
        "reference_image_urls": ["https://example.com/ref.jpg"],
        "rendering_speed": "BALANCED",
        "style": "AUTO",
        "expand_prompt": True,
        "num_images": "1",
    },
    
    "ideogram/character-remix": {
        "image_url": "https://example.com/image.jpg",
        "reference_image_urls": ["https://example.com/ref.jpg"],
        "rendering_speed": "BALANCED",
        "style": "AUTO",
        "expand_prompt": True,
        "image_size": "square_hd",
        "num_images": "1",
        "strength": 0.8,
        "negative_prompt": "",
        "reference_mask_urls": "",
    },
    
    "ideogram/v3-reframe": {
        "image_url": "https://example.com/image.jpg",
        "image_size": "square_hd",
        "rendering_speed": "BALANCED",
        "style": "AUTO",
        "num_images": "1",
        "seed": 0,
    },
    
    "infinitalk/from-audio": {
        "image_url": "https://example.com/image.jpg",
        "audio_url": "https://example.com/audio.mp3",
        "resolution": "480p",
    },
    
    "kling-2.6/image-to-video": {
        "image_urls": ["https://example.com/image.jpg"],
        "sound": False,
        "duration": "5",
    },
    
    "kling-2.6/text-to-video": {
        "sound": False,
        "aspect_ratio": "1:1",
        "duration": "5",
    },
    
    "kling/ai-avatar-v1-pro": {
        "image_url": "https://example.com/image.jpg",
        "audio_url": "https://example.com/audio.mp3",
    },
    
    "kling/v1-avatar-standard": {
        "image_url": "https://example.com/image.jpg",
        "audio_url": "https://example.com/audio.mp3",
    },
    
    "kling/v2-1-master-image-to-video": {
        "image_url": "https://example.com/image.jpg",
        "duration": "5",
        "negative_prompt": "blur, distort, and low quality",
        "cfg_scale": 0.5,
    },
    
    "kling/v2-1-master-text-to-video": {
        "duration": "5",
        "aspect_ratio": "16:9",
        "negative_prompt": "blur, distort, and low quality",
        "cfg_scale": 0.5,
    },
    
    "kling/v2-1-pro": {
        "image_url": "https://example.com/image.jpg",
        "duration": "5",
        "negative_prompt": "blur, distort, and low quality",
        "cfg_scale": 0.5,
        "tail_image_url": "",
    },
    
    "kling/v2-1-standard": {
        "image_url": "https://example.com/image.jpg",
        "duration": "5",
        "negative_prompt": "blur, distort, and low quality",
        "cfg_scale": 0.5,
    },
    
    "kling/v2-5-turbo-image-to-video-pro": {
        "image_url": "https://example.com/image.jpg",
        "tail_image_url": "",
        "duration": "5",
        "negative_prompt": "blur, distort, and low quality",
        "cfg_scale": 0.5,
    },
    
    "kling/v2-5-turbo-text-to-video-pro": {
        "duration": "5",
        "aspect_ratio": "16:9",
        "negative_prompt": "blur, distort, and low quality",
        "cfg_scale": 0.5,
    },
    
    "nano-banana-pro": {
        "aspect_ratio": "1:1",
        "resolution": "1K",
        "output_format": "png",
    },
    
    "qwen/image-edit": {
        "prompt": "",  # CRITICAL FIX: prompt required but can be empty for image-edit
        "image_url": "https://example.com/image.jpg",
        "acceleration": "none",
        "image_size": "landscape_4_3",
        "num_inference_steps": 25,
        "guidance_scale": 4,
        "sync_mode": False,
        "enable_safety_checker": True,
        "output_format": "png",
        "negative_prompt": "blurry, ugly",
    },
    
    "qwen/image-to-image": {
        "image_url": "https://example.com/image.jpg",
        "strength": 0.8,
        "output_format": "png",
        "acceleration": "none",
        "negative_prompt": "blurry, ugly",
        "num_inference_steps": 30,
        "guidance_scale": 2.5,
        "enable_safety_checker": True,
    },
    
    "qwen/text-to-image": {
        "image_size": "square_hd",
        "num_inference_steps": 30,
        "guidance_scale": 2.5,
        "enable_safety_checker": True,
        "output_format": "png",
        "negative_prompt": " ",
        "acceleration": "none",
    },
    
    "recraft/crisp-upscale": {
        "image": "https://example.com/image.jpg",
    },
    
    "recraft/remove-background": {
        "image": "https://example.com/image.jpg",
    },
    
    "sora-2-characters": {
        "character_file_url": ["https://example.com/char.zip"],
        "character_prompt": "A friendly cartoon character",
        "safety_instruction": "Ensure family-friendly content",
    },
    
    "sora-2-image-to-video": {
        "image_urls": ["https://example.com/image.jpg"],
        "aspect_ratio": "landscape",
        "n_frames": "10",
        "remove_watermark": True,
        "character_id_list": ["example_123456789"],
    },
    
    "sora-2-pro-image-to-video": {
        "aspect_ratio": "landscape",
        "n_frames": "10",
        "size": "standard",
        "remove_watermark": True,
        "character_id_list": ["example_123456789"],
    },
    
    "sora-2-pro-text-to-video": {
        "aspect_ratio": "landscape",
        "n_frames": "10",
        "size": "high",
        "remove_watermark": True,
        "character_id_list": ["example_123456789"],
    },
    
    "sora-2-text-to-video": {
        "aspect_ratio": "landscape",
        "n_frames": "10",
        "remove_watermark": True,
        "character_id_list": ["example_123456789"],
    },
    
    "sora-watermark-remover": {
        "video_url": "https://example.com/video.mp4",
    },
    
    "topaz/image-upscale": {
        "image_url": "https://example.com/image.jpg",
        "upscale_factor": "2",
    },
    
    "topaz/video-upscale": {
        "video_url": "https://example.com/video.mp4",
        "upscale_factor": "2",
    },
    
    "wan/2-2-a14b-image-to-video-turbo": {
        "image_url": "https://example.com/image.jpg",
        "resolution": "720p",
        "aspect_ratio": "auto",
        "enable_prompt_expansion": False,
        "seed": 0,
        "acceleration": "none",
    },
    
    "wan/2-2-a14b-speech-to-video-turbo": {
        "image_url": "https://example.com/image.jpg",
        "audio_url": "https://example.com/audio.mp3",
        "num_frames": 80,
        "frames_per_second": 16,
        "resolution": "480p",
        "negative_prompt": "",
        "num_inference_steps": 27,
        "guidance_scale": 3.5,
        "shift": 5,
        "enable_safety_checker": True,
    },
    
    "wan/2-2-a14b-text-to-video-turbo": {
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "enable_prompt_expansion": False,
        "seed": 0,
        "acceleration": "none",
    },
    
    "wan/2-2-animate-move": {
        "video_url": "https://example.com/video.mp4",
        "image_url": "https://example.com/image.jpg",
        "resolution": "480p",
    },
    
    "wan/2-2-animate-replace": {
        "video_url": "https://example.com/video.mp4",
        "image_url": "https://example.com/image.jpg",
        "resolution": "480p",
    },
    
    "wan/2-6-image-to-video": {
        "image_urls": ["https://example.com/image.jpg"],
        "duration": "5",
        "resolution": "1080p",
    },
    
    "wan/2-6-text-to-video": {
        "duration": "5",
        "resolution": "1080p",
    },
    
    "wan/2-6-video-to-video": {
        "video_urls": ["https://example.com/video.mp4"],
        "duration": "5",
        "resolution": "1080p",
    },
    
    "z-image": {
        "aspect_ratio": "1:1",
    },
}


def get_model_defaults(model_id: str) -> Dict[str, Any]:
    """
    Get default values for model.
    
    Args:
        model_id: Model identifier (e.g., "bytedance/seedream")
        
    Returns:
        Dictionary of default values for optional fields
    """
    return MODEL_DEFAULTS.get(model_id, {}).copy()


def apply_defaults(model_id: str, user_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply model defaults to user inputs (only for missing keys).
    
    Args:
        model_id: Model identifier
        user_inputs: User-provided inputs
        
    Returns:
        Merged dictionary (user inputs + defaults for missing keys)
    """
    defaults = get_model_defaults(model_id)
    result = defaults.copy()
    result.update(user_inputs)  # User values override defaults
    return result
