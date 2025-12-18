"""
Каноническая структура моделей KIE AI с поддержкой MODES.
МОДЕЛЬ ≠ MODE. MODE = отдельная генерация + отдельный input_schema + отдельная цена.

Всего: 47 моделей
Каждая модель имеет 1+ MODE.
"""

KIE_MODELS = {
    # ==================== WAN 2.6 ====================
    "wan/2.6": {
        "title": "Wan 2.6",
        "provider": "wan",
        "description": "Продвинутая модель генерации видео с поддержкой text-to-video, image-to-video и video-to-video",
        "modes": {
            "text_to_video": {
                "model": "wan/2-5-text-to-video",
                "generation_type": "text_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание видео",
                            "max_length": 5000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "integer",
                            "description": "Длительность в секундах",
                            "minimum": 5,
                            "maximum": 10,
                            "default": 5
                        },
                        "resolution": {
                            "type": "string",
                            "enum": ["720p", "1080p"],
                            "default": "720p"
                        }
                    },
                    "required": ["prompt"]
                },
                "pricing_unit": "per_5s",
                "help": "Генерация видео из текстового описания"
            },
            "image_to_video": {
                "model": "wan/2-5-image-to-video",
                "generation_type": "image_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "min_items": 1,
                            "max_items": 1,
                            "description": "URL изображения"
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание движения",
                            "max_length": 5000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 10,
                            "default": 5
                        }
                    },
                    "required": ["image_urls", "prompt"]
                },
                "pricing_unit": "per_5s",
                "help": "Генерация видео из изображения"
            },
            "video_to_video": {
                "model": "wan/2-2-animate-move",
                "generation_type": "video_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "video_url": {
                            "type": "string",
                            "description": "URL видео"
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание изменений",
                            "max_length": 5000
                        }
                    },
                    "required": ["video_url", "prompt"]
                },
                "pricing_unit": "per_5s",
                "help": "Анимация и изменение видео"
            }
        }
    },
    
    # ==================== SEEDREAM 4.5 ====================
    "seedream/4.5": {
        "title": "Seedream 4.5",
        "provider": "seedream",
        "description": "Bytedance модель для генерации 4K изображений с точным редактированием",
        "modes": {
            "text_to_image": {
                "model": "seedream/4.5-text-to-image",
                "generation_type": "text_to_image",
                "category": "Image",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание изображения",
                            "max_length": 3000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"],
                            "default": "1:1"
                        },
                        "quality": {
                            "type": "string",
                            "enum": ["basic", "high"],
                            "default": "basic",
                            "description": "Basic = 2K, High = 4K"
                        }
                    },
                    "required": ["prompt"]
                },
                "pricing_unit": "per_image",
                "help": "Генерация изображения из текста"
            },
            "image_to_image": {
                "model": "seedream/4.5-image-to-image",
                "generation_type": "image_to_image",
                "category": "Image",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "min_items": 1,
                            "max_items": 1
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание изменений",
                            "max_length": 3000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"],
                            "default": "1:1"
                        },
                        "quality": {
                            "type": "string",
                            "enum": ["basic", "high"],
                            "default": "basic"
                        }
                    },
                    "required": ["image_urls", "prompt"]
                },
                "pricing_unit": "per_image",
                "help": "Трансформация изображения"
            },
            "image_edit": {
                "model": "seedream/4.5-edit",
                "generation_type": "image_edit",
                "category": "Image",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "min_items": 1,
                            "max_items": 1
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание изменений",
                            "max_length": 3000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"],
                            "default": "1:1"
                        },
                        "quality": {
                            "type": "string",
                            "enum": ["basic", "high"],
                            "default": "basic"
                        }
                    },
                    "required": ["image_urls", "prompt"]
                },
                "pricing_unit": "per_image",
                "help": "Редактирование изображения"
            }
        }
    },
    
    # ==================== KLING 2.6 ====================
    "kling/2.6": {
        "title": "Kling 2.6",
        "provider": "kling",
        "description": "Модель генерации видео с высоким качеством",
        "modes": {
            "text_to_video": {
                "model": "kling-2.6/text-to-video",
                "generation_type": "text_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание видео",
                            "max_length": 5000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["16:9", "9:16", "1:1"],
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 10,
                            "default": 5
                        }
                    },
                    "required": ["prompt"]
                },
                "pricing_unit": "per_5s",
                "help": "Генерация видео из текста"
            },
            "image_to_video": {
                "model": "kling-2.6/image-to-video",
                "generation_type": "image_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "min_items": 1,
                            "max_items": 1
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание движения",
                            "max_length": 5000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["16:9", "9:16", "1:1"],
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 10,
                            "default": 5
                        }
                    },
                    "required": ["image_urls", "prompt"]
                },
                "pricing_unit": "per_5s",
                "help": "Генерация видео из изображения"
            }
        }
    },
    
    # ==================== SORA 2 / 2 PRO / STORYBOARD ====================
    "sora/2": {
        "title": "Sora 2",
        "provider": "openai",
        "description": "OpenAI Sora 2 - генерация видео из текста и изображений",
        "modes": {
            "text_to_video": {
                "model": "sora-2-text-to-video",
                "generation_type": "text_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание видео",
                            "max_length": 10000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["portrait", "landscape"],
                            "default": "landscape"
                        },
                        "n_frames": {
                            "type": "string",
                            "enum": ["10", "15"],
                            "default": "10"
                        },
                        "size": {
                            "type": "string",
                            "enum": ["standard", "high"],
                            "default": "standard"
                        },
                        "remove_watermark": {
                            "type": "boolean",
                            "default": True
                        }
                    },
                    "required": ["prompt"]
                },
                "pricing_unit": "per_10s",
                "help": "Генерация видео из текста"
            },
            "image_to_video": {
                "model": "sora-2-pro-image-to-video",
                "generation_type": "image_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "min_items": 1,
                            "max_items": 1
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание движения",
                            "max_length": 10000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["portrait", "landscape"],
                            "default": "landscape"
                        },
                        "n_frames": {
                            "type": "string",
                            "enum": ["10", "15"],
                            "default": "10"
                        },
                        "size": {
                            "type": "string",
                            "enum": ["standard", "high"],
                            "default": "standard"
                        },
                        "remove_watermark": {
                            "type": "boolean",
                            "default": True
                        }
                    },
                    "required": ["image_urls", "prompt"]
                },
                "pricing_unit": "per_10s",
                "help": "Генерация видео из изображения"
            },
            "watermark_remove": {
                "model": "sora-watermark-remover",
                "generation_type": "video_edit",
                "category": "Tools",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "video_url": {
                            "type": "string",
                            "description": "URL видео с водяным знаком"
                        }
                    },
                    "required": ["video_url"]
                },
                "pricing_unit": "per_use",
                "help": "Удаление водяного знака с видео Sora 2"
            }
        }
    },
    
    # ==================== VEO 3 / 3.1 ====================
    "veo/3": {
        "title": "Veo 3",
        "provider": "google",
        "description": "Google Veo 3 - генерация видео высокого качества",
        "modes": {
            "text_to_video": {
                "model": "veo-3-text-to-video",
                "generation_type": "text_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание видео",
                            "max_length": 5000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["16:9", "9:16", "1:1"],
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 10,
                            "default": 5
                        }
                    },
                    "required": ["prompt"]
                },
                "pricing_unit": "per_5s",
                "help": "Генерация видео из текста"
            },
            "image_to_video": {
                "model": "veo-3-image-to-video",
                "generation_type": "image_to_video",
                "category": "Video",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "min_items": 1,
                            "max_items": 1
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание движения",
                            "max_length": 5000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["16:9", "9:16", "1:1"],
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 10,
                            "default": 5
                        }
                    },
                    "required": ["image_urls", "prompt"]
                },
                "pricing_unit": "per_5s",
                "help": "Генерация видео из изображения"
            }
        }
    },
    
    # ==================== NANO BANANA (GEMINI 2.5) ====================
    "nano-banana/gemini-2.5": {
        "title": "Nano Banana Pro (Gemini 2.5)",
        "provider": "google",
        "description": "Google DeepMind модель с улучшенным качеством 2K/4K",
        "modes": {
            "text_to_image": {
                "model": "nano-banana-pro",
                "generation_type": "text_to_image",
                "category": "Image",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание изображения",
                            "max_length": 10000
                        },
                        "image_input": {
                            "type": "array",
                            "items": {"type": "string"},
                            "min_items": 0,
                            "max_items": 8,
                            "description": "Входные изображения для референса (опционально)"
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"],
                            "default": "1:1"
                        },
                        "resolution": {
                            "type": "string",
                            "enum": ["1K", "2K", "4K"],
                            "default": "1K",
                            "description": "1K/2K = 18 кредитов, 4K = 24 кредита"
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["png", "jpg"],
                            "default": "png"
                        }
                    },
                    "required": ["prompt"]
                },
                "pricing_unit": "per_image",
                "help": "Генерация изображения из текста с поддержкой референса"
            },
            "image_to_image": {
                "model": "nano-banana-pro",
                "generation_type": "image_to_image",
                "category": "Image",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "image_input": {
                            "type": "array",
                            "items": {"type": "string"},
                            "min_items": 1,
                            "max_items": 8,
                            "description": "Входные изображения для трансформации"
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание изменений",
                            "max_length": 10000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"],
                            "default": "1:1"
                        },
                        "resolution": {
                            "type": "string",
                            "enum": ["1K", "2K", "4K"],
                            "default": "1K"
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["png", "jpg"],
                            "default": "png"
                        }
                    },
                    "required": ["image_input", "prompt"]
                },
                "pricing_unit": "per_image",
                "help": "Трансформация изображения"
            }
        }
    },
    
    # ==================== Z-IMAGE ====================
    "z-image": {
        "title": "Z-Image",
        "provider": "tongyi",
        "description": "Эффективная модель генерации изображений от Tongyi-MAI",
        "modes": {
            "text_to_image": {
                "model": "z-image",
                "generation_type": "text_to_image",
                "category": "Image",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Текстовое описание изображения",
                            "max_length": 1000
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["1:1", "4:3", "3:4", "16:9", "9:16"],
                            "default": "1:1"
                        }
                    },
                    "required": ["prompt"]
                },
                "pricing_unit": "per_image",
                "help": "Генерация изображения из текста"
            }
        }
    }
}

# Вспомогательные функции для работы с новой структурой

def get_model_by_key(model_key: str) -> dict:
    """Получает модель по ключу (provider/model_name)."""
    return KIE_MODELS.get(model_key)


def get_mode_by_key(model_key: str, mode_id: str) -> dict:
    """Получает mode по ключу модели и ID mode."""
    model = get_model_by_key(model_key)
    if not model:
        return None
    return model.get("modes", {}).get(mode_id)


def get_all_models() -> dict:
    """Возвращает все модели."""
    return KIE_MODELS


def get_models_by_category(category: str) -> dict:
    """Получает модели по категории."""
    result = {}
    for model_key, model_data in KIE_MODELS.items():
        modes = model_data.get("modes", {})
        for mode_id, mode_data in modes.items():
            if mode_data.get("category") == category:
                if model_key not in result:
                    result[model_key] = model_data
                break
    return result


def get_all_modes() -> list:
    """Возвращает список всех modes с полными ключами."""
    result = []
    for model_key, model_data in KIE_MODELS.items():
        modes = model_data.get("modes", {})
        for mode_id, mode_data in modes.items():
            result.append({
                "model_key": model_key,
                "mode_id": mode_id,
                "full_key": f"{model_key}:{mode_id}",
                "model": mode_data.get("model"),
                "generation_type": mode_data.get("generation_type"),
                "category": mode_data.get("category")
            })
    return result


def count_models_and_modes() -> dict:
    """Подсчитывает количество моделей и modes."""
    total_models = len(KIE_MODELS)
    total_modes = sum(len(model.get("modes", {})) for model in KIE_MODELS.values())
    return {
        "models": total_models,
        "modes": total_modes
    }

