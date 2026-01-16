"""
Схемы входных параметров для каждого типа модели KIE AI.
Whitelist разрешённых полей для каждого типа.
"""

from typing import Dict, Set, List, Optional

# Whitelist разрешённых полей для каждого типа модели
INPUT_SCHEMAS: Dict[str, Set[str]] = {
    # Text-to-Image
    't2i': {
        'prompt',
        'negative_prompt',
        'width',
        'height',
        'steps',
        'seed',
        'guidance',
        'guidance_scale',  # Для bytedance/seedream
        'style',
        'image_count',
        'aspect_ratio',
        'quality',
        'resolution',
        'model',
        'mode',
        'image_size',  # Для bytedance/seedream-v4-text-to-image, bytedance/seedream, qwen/text-to-image, google/nano-banana и ideogram/character
        'image_resolution',  # Для bytedance/seedream-v4-text-to-image
        'max_images',  # Для bytedance/seedream-v4-text-to-image
        'enable_safety_checker',  # Для bytedance/seedream и qwen/text-to-image
        'output_format',  # Для qwen/text-to-image, google/nano-banana и nano-banana-pro
        'acceleration',  # Для qwen/text-to-image
        'num_inference_steps',  # Для qwen/text-to-image
        'image_input',  # Для nano-banana-pro
        'resolution',  # Для nano-banana-pro (1K, 2K, 4K)
        'reference_image_urls',  # Для ideogram/character
        'rendering_speed',  # Для ideogram/character
        'expand_prompt',  # Для ideogram/character
        'num_images'  # Для ideogram/character
    },
    
    # Image-to-Image
    'i2i': {
        'prompt',
        'image_url',
        'image_urls',  # Для bytedance/seedream-v4-edit
        'image_base64',
        'image',
        'strength',
        'width',
        'height',
        'seed',
        'steps',
        'guidance',
        'negative_prompt',
        'style',
        'mode',
        'quality',
        'image_size',  # Для bytedance/seedream-v4-edit, ideogram/v3-reframe, google/nano-banana-edit, qwen/image-edit и ideogram/character-remix
        'image_resolution',  # Для bytedance/seedream-v4-edit
        'max_images',  # Для bytedance/seedream-v4-edit
        'rendering_speed',  # Для ideogram/v3-reframe, ideogram/character-edit и ideogram/character-remix
        'num_images',  # Для ideogram/v3-reframe, qwen/image-edit, ideogram/character-edit и ideogram/character-remix
        'output_format',  # Для qwen/image-to-image, google/nano-banana-edit и qwen/image-edit
        'acceleration',  # Для qwen/image-to-image и qwen/image-edit
        'num_inference_steps',  # Для qwen/image-to-image и qwen/image-edit
        'guidance_scale',  # Для qwen/image-to-image и qwen/image-edit
        'enable_safety_checker',  # Для qwen/image-to-image и qwen/image-edit
        'sync_mode',  # Для qwen/image-edit
        'mask_url',  # Для ideogram/character-edit
        'reference_image_urls',  # Для ideogram/character-edit и ideogram/character-remix
        'expand_prompt',  # Для ideogram/character-edit и ideogram/character-remix
        'reference_mask_urls'  # Для ideogram/character-remix
    },
    
    # Text-to-Video
    't2v': {
        'prompt',
        'duration',
        'fps',
        'frames_per_second',  # Для wan/2-6-text-to-video
        'resolution',
        'seed',
        'with_audio',
        'width',
        'height',
        'guidance',
        'steps',
        'negative_prompt',
        'motion',
        'style',
        'aspect_ratio',
        'cfg_scale',  # Для kling/v2-5-turbo-text-to-video-pro
        'prompt_optimizer',  # Для hailuo/02-text-to-video-pro
        'image_url',  # Для wan/2-2-a14b-speech-to-video-turbo
        'enable_prompt_expansion',  # Для wan/2-2-a14b-text-to-video-turbo
        'acceleration',  # Для wan/2-2-a14b-text-to-video-turbo
        'audio_url',  # Для wan/2-2-a14b-speech-to-video-turbo
        'num_frames',  # Для wan/2-2-a14b-speech-to-video-turbo
        'num_inference_steps',  # Для wan/2-2-a14b-speech-to-video-turbo
        'guidance_scale',  # Для wan/2-2-a14b-speech-to-video-turbo
        'shift',  # Для wan/2-2-a14b-speech-to-video-turbo
        'enable_safety_checker',  # Для wan/2-2-a14b-speech-to-video-turbo и bytedance/v1-lite-text-to-video
        'camera_fixed'  # Для bytedance/v1-lite-text-to-video
    },
    
    # Image-to-Video
    'i2v': {
        'image_url',
        'image_urls',  # Для wan/2-6-image-to-video
        'tail_image_url',  # Для kling/v2-5-turbo-image-to-video-pro
        'end_image_url',  # Для hailuo/02-image-to-video-pro
        'image_base64',
        'image',
        'prompt',
        'duration',
        'resolution',
        'with_audio',
        'fps',
        'seed',
        'strength',
        'width',
        'height',
        'guidance',
        'motion',
        'style',
        'cfg_scale',  # Для kling/v2-5-turbo-image-to-video-pro
        'enable_prompt_expansion',  # Для wan/2-5-image-to-video
        'prompt_optimizer'  # Для hailuo/02-image-to-video-pro
    },
    
    # Video-to-Video
    'v2v': {
        'video_url',
        'video_urls',  # Для wan/2-6-video-to-video
        'image_url',  # Для wan/2-2-animate-move
        'video',
        'prompt',
        'duration',
        'resolution',
        'fps',
        'seed',
        'strength',
        'with_audio',
        'guidance',
        'motion',
        'style'
    },
    
    # Text-to-Speech
    'tts': {
        'text',
        'voice',
        'language',
        'language_code',  # Для elevenlabs/text-to-speech-multilingual-v2
        'speed',
        'model',
        'style',
        'emotion',
        'stability',  # Для elevenlabs/text-to-speech-multilingual-v2
        'similarity_boost',  # Для elevenlabs/text-to-speech-multilingual-v2
        'timestamps',  # Для elevenlabs/text-to-speech-multilingual-v2
        'previous_text',  # Для elevenlabs/text-to-speech-multilingual-v2
        'next_text'  # Для elevenlabs/text-to-speech-multilingual-v2
    },
    
    # Speech-to-Text
    'stt': {
        'audio_url',
        'audio',
        'language',
        'language_code',  # Для elevenlabs/speech-to-text
        'model',
        'format',
        'tag_audio_events',  # Для elevenlabs/speech-to-text
        'diarize'  # Для elevenlabs/speech-to-text
    },
    
    # Sound Effects
    'sfx': {
        'prompt',
        'text',  # Для elevenlabs/sound-effect-v2
        'duration',
        'duration_seconds',  # Для elevenlabs/sound-effect-v2
        'style',
        'seed',
        'loop',  # Для elevenlabs/sound-effect-v2
        'prompt_influence',  # Для elevenlabs/sound-effect-v2
        'output_format'  # Для elevenlabs/sound-effect-v2
    },
    
    # Audio Isolation
    'audio_isolation': {
        'audio_url',
        'audio',
        'mode',
        'strength'
    },
    
    # Upscale
    'upscale': {
        'image_url',
        'image_base64',
        'image',
        'scale',
        'upscale_factor',
        'model',
        'quality',
        'task_id'  # Для grok-imagine/upscale (только KIE AI task_id)
    },
    
    # Background Remove
    'bg_remove': {
        'image_url',
        'image_base64',
        'image'
    },
    
    # Watermark Remove
    'watermark_remove': {
        'image_url',
        'image_base64',
        'image',
        'video_url',  # Для sora-watermark-remover
        'strength'
    },
    
    # Music Generation
    'music': {
        'prompt',
        'duration',
        'style',
        'tempo',
        'seed',
        'model',
        'format'
    },
    
    # Lip Sync
    'lip_sync': {
        'video_url',
        'video',
        'audio_url',
        'audio',
        'image_url',
        'image',
        'resolution',
        'model',
        'prompt',  # Для kling/v1-avatar-standard и infinitalk/from-audio
        'seed'  # Для infinitalk/from-audio
    }
}

# Критичные обязательные поля для каждого типа
REQUIRED_FIELDS: Dict[str, Set[str]] = {
    't2i': {'prompt'},
    'i2i': {'image_url', 'image_base64', 'image'},  # Хотя бы одно
    't2v': {'prompt'},
    'i2v': {'image_url', 'image_base64', 'image'},  # Хотя бы одно
    'v2v': {'video_url', 'video'},  # Хотя бы одно
    'tts': {'text'},
    'stt': {'audio_url', 'audio'},  # Хотя бы одно
    'sfx': {'prompt'},
    'audio_isolation': {'audio_url', 'audio'},  # Хотя бы одно
    'upscale': {'image_url', 'image_base64', 'image'},  # Хотя бы одно
    'bg_remove': {'image_url', 'image_base64', 'image'},  # Хотя бы одно
    'watermark_remove': {'image_url', 'image_base64', 'image'},  # Хотя бы одно
    'music': {'prompt'},
    'lip_sync': {'video_url', 'video', 'image_url', 'image'}  # Хотя бы одно из каждой группы
}

# Алиасы для нормализации полей
FIELD_ALIASES: Dict[str, str] = {
    # Image aliases
    'img': 'image_url',
    'image_input': 'image_url',
    'input_image': 'image_url',
    'photo': 'image_url',
    
    # Video aliases
    'vid': 'video_url',
    'video_input': 'video_url',
    'input_video': 'video_url',
    
    # Audio aliases
    'audio_input': 'audio_url',
    'input_audio': 'audio_url',
    
    # Prompt aliases
    'neg': 'negative_prompt',
    'neg_prompt': 'negative_prompt',
    'negative': 'negative_prompt',
    
    # Other aliases
    'scale_factor': 'scale',
    'upscale_scale': 'scale',
    'fps_value': 'fps',
    'duration_seconds': 'duration',
    'audio_enabled': 'with_audio',
    'has_audio': 'with_audio'
}

# Дефолтные значения для полей (если не указаны)
DEFAULT_VALUES: Dict[str, Dict[str, any]] = {
    't2i': {
        'width': 1024,
        'height': 1024,
        'steps': 20,
        'guidance': 7.5
    },
    'i2i': {
        'strength': 0.75,
        'width': 1024,
        'height': 1024
    },
    't2v': {
        # Примечание: для wan/2-6-text-to-video duration должен быть строкой "5", "10" или "15"
        # Дефолт применяется только если не указан явно и не извлечён из notes
        'with_audio': False
    },
    'i2v': {
        'duration': 5.0,
        'fps': 24,
        'with_audio': False
    },
    'v2v': {
        'with_audio': False
    },
    'tts': {
        'speed': 1.0
    },
    'stt': {},
    'sfx': {
        'duration': 5.0
    },
    'audio_isolation': {},
    'upscale': {
        'scale': 2
    },
    'bg_remove': {},
    'watermark_remove': {
        'strength': 0.5
    },
    'music': {
        'duration': 30.0
    },
    'lip_sync': {
        'resolution': '720p'
    }
}


def get_schema_for_type(model_type: str) -> Set[str]:
    """
    Получает whitelist разрешённых полей для типа модели.
    
    Args:
        model_type: Тип модели (t2i, i2i, t2v, и т.д.)
    
    Returns:
        Множество разрешённых полей
    """
    return INPUT_SCHEMAS.get(model_type, set())


def get_required_fields_for_type(model_type: str) -> Set[str]:
    """
    Получает обязательные поля для типа модели.
    
    Args:
        model_type: Тип модели
    
    Returns:
        Множество обязательных полей
    """
    return REQUIRED_FIELDS.get(model_type, set())


def normalize_field_name(field_name: str) -> str:
    """
    Нормализует имя поля через алиасы.
    
    Args:
        field_name: Исходное имя поля
    
    Returns:
        Нормализованное имя поля
    """
    return FIELD_ALIASES.get(field_name, field_name)


def get_default_value(model_type: str, field_name: str) -> Optional[any]:
    """
    Получает дефолтное значение для поля типа модели.
    
    Args:
        model_type: Тип модели
        field_name: Имя поля
    
    Returns:
        Дефолтное значение или None
    """
    defaults = DEFAULT_VALUES.get(model_type, {})
    return defaults.get(field_name)

