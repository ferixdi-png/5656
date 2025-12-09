"""
Static list of KIE AI models available in the bot
These models are shown in the menu instead of fetching from API
"""

# Available KIE AI models with their details
KIE_MODELS = [
    {
        "id": "z-image",
        "name": "Z-Image",
        "description": "Эффективная модель генерации изображений от Tongyi-MAI. Фотореалистичный вывод, быстрая производительность Turbo и точный двуязычный рендеринг текста.",
        "category": "Фото",
        "emoji": "🖼️",
        "pricing": "0.8 кредитов за изображение",
        "input_params": {
            "prompt": {
                "type": "string",
                "description": "Текстовое описание изображения, которое вы хотите сгенерировать (макс. 1000 символов)",
                "required": True,
                "max_length": 1000
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Соотношение сторон для сгенерированного изображения",
                "required": True,
                "default": "1:1",
                "enum": ["1:1", "4:3", "3:4", "16:9", "9:16"]
            }
        }
    },
    {
        "id": "nano-banana-pro",
        "name": "Nano Banana Pro",
        "description": "Google DeepMind модель с улучшенным качеством 2K/4K, интеллектуальным масштабированием, улучшенным рендерингом текста и согласованностью персонажей.",
        "category": "Фото",
        "emoji": "🍌",
        "pricing": "18 кредитов (1K/2K) или 24 кредита (4K)",
        "input_params": {
            "prompt": {
                "type": "string",
                "description": "Текстовое описание изображения (макс. 10000 символов)",
                "required": True,
                "max_length": 10000
            },
            "image_input": {
                "type": "array",
                "description": "Входные изображения для трансформации или использования как референс (до 8 изображений, опционально)",
                "required": False,
                "item_type": "string"
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Соотношение сторон изображения",
                "required": False,
                "default": "1:1",
                "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"]
            },
            "resolution": {
                "type": "string",
                "description": "Разрешение изображения (1K/2K = 18 кредитов, 4K = 24 кредита)",
                "required": False,
                "default": "1K",
                "enum": ["1K", "2K", "4K"]
            },
            "output_format": {
                "type": "string",
                "description": "Формат выходного изображения",
                "required": False,
                "default": "png",
                "enum": ["png", "jpg"]
            }
        }
    },
    {
        "id": "seedream/4.5-text-to-image",
        "name": "Seedream 4.5 Text-to-Image",
        "description": "Bytedance модель для генерации 4K изображений, точного редактирования и согласованного вывода нескольких изображений. Генерация из текста.",
        "category": "Фото",
        "emoji": "🎨",
        "pricing": "6.5 кредитов за изображение",
        "input_params": {
            "prompt": {
                "type": "string",
                "description": "Текстовое описание изображения, которое вы хотите сгенерировать (макс. 3000 символов)",
                "required": True,
                "max_length": 3000
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Соотношение сторон изображения",
                "required": True,
                "default": "1:1",
                "enum": ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
            },
            "quality": {
                "type": "string",
                "description": "Качество изображения (Basic = 2K, High = 4K)",
                "required": True,
                "default": "basic",
                "enum": ["basic", "high"]
            }
        }
    },
    {
        "id": "seedream/4.5-edit",
        "name": "Seedream 4.5 Edit",
        "description": "Bytedance модель для генерации 4K изображений, точного редактирования и согласованного вывода нескольких изображений. Редактирование изображений.",
        "category": "Фото",
        "emoji": "✏️",
        "pricing": "6.5 кредитов за изображение",
        "input_params": {
            "prompt": {
                "type": "string",
                "description": "Текстовое описание изменений, которые вы хотите внести (макс. 3000 символов)",
                "required": True,
                "max_length": 3000
            },
            "image_urls": {
                "type": "array",
                "description": "Изображение для редактирования (URL после загрузки)",
                "required": True,
                "item_type": "string"
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Соотношение сторон изображения",
                "required": True,
                "default": "1:1",
                "enum": ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
            },
            "quality": {
                "type": "string",
                "description": "Качество изображения (Basic = 2K, High = 4K)",
                "required": True,
                "default": "basic",
                "enum": ["basic", "high"]
            }
        }
    },
    {
        "id": "sora-watermark-remover",
        "name": "Sora 2 Watermark Remover",
        "description": "Удаление динамических водяных знаков с видео Sora 2 с помощью AI-детекции и отслеживания движения. Сохраняет плавность и естественность кадров.",
        "category": "Видео",
        "emoji": "🎬",
        "pricing": "10 кредитов за использование",
        "input_params": {
            "video_url": {
                "type": "string",
                "description": "URL видео Sora 2 от OpenAI (должен быть публично доступным, начинается с sora.chatgpt.com)",
                "required": True,
                "max_length": 500
            }
        }
    },
    {
        "id": "sora-2-text-to-video",
        "name": "Sora 2 Text-to-Video",
        "description": "OpenAI Sora 2 - последняя модель генерации видео из текста. Реалистичное движение, физическая согласованность, улучшенный контроль над стилем, сценой и соотношением сторон. Идеально для креативных приложений и контента для соцсетей.",
        "category": "Видео",
        "emoji": "🎥",
        "pricing": "30 кредитов за 10-секундное видео с аудио",
        "input_params": {
            "prompt": {
                "type": "string",
                "description": "Текстовое описание желаемого движения видео (макс. 10000 символов)",
                "required": True,
                "max_length": 10000
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Соотношение сторон видео",
                "required": False,
                "default": "landscape",
                "enum": ["portrait", "landscape"]
            },
            "n_frames": {
                "type": "string",
                "description": "Количество кадров (длительность видео)",
                "required": False,
                "default": "10",
                "enum": ["10", "15"]
            },
            "remove_watermark": {
                "type": "boolean",
                "description": "Удалить водяной знак с сгенерированного видео",
                "required": False,
                "default": True
            }
        }
    }
]


def get_model_by_id(model_id: str) -> dict:
    """Get model by ID"""
    for model in KIE_MODELS:
        if model["id"] == model_id:
            return model
    return None


def get_models_by_category(category: str = None) -> list:
    """Get models filtered by category"""
    if category:
        return [m for m in KIE_MODELS if m["category"] == category]
    return KIE_MODELS


def get_categories() -> list:
    """Get list of available categories"""
    categories = list(set([m["category"] for m in KIE_MODELS]))
    return sorted(categories)

