"""
Human-friendly parameter labels and descriptions.
Replaces technical names (aspect_ratio, resolution, etc) with понятные кнопки.
"""
from typing import Dict, List, Optional, Tuple

# Aspect ratio human labels with use cases
ASPECT_RATIO_LABELS = {
    "1:1": "🟦 Квадрат 1:1 — Посты в соцсетях",
    "9:16": "📱 Вертикаль 9:16 — Stories, Reels",
    "16:9": "🖥️ Горизонталь 16:9 — YouTube, презентации",
    "4:3": "📺 4:3 — Классическое фото",
    "3:4": "📸 3:4 — Портрет",
    "21:9": "🎬 21:9 — Кинематограф",
}

# Resolution/size labels
IMAGE_SIZE_LABELS = {
    "512x512": "🔹 512×512 — Быстро, базовое качество",
    "768x768": "🔸 768×768 — Среднее качество",
    "1024x1024": "⭐ 1024×1024 — Высокое качество (рекомендуется)",
    "1280x720": "📺 HD 720p",
    "1920x1080": "🎬 Full HD 1080p",
    "2560x1440": "💎 2K Quad HD",
    "3840x2160": "🌟 4K Ultra HD",
}

# Rendering quality
QUALITY_LABELS = {
    "draft": "⚡ Черновик — Быстро, низкое качество",
    "normal": "✅ Нормальное — Баланс скорость/качество",
    "high": "⭐ Высокое — Медленнее, лучше детализация",
    "ultra": "💎 Ультра — Максимальное качество",
}

# Steps/inference steps
STEPS_LABELS = {
    "20": "⚡ 20 шагов — Быстро",
    "30": "✅ 30 шагов — Рекомендуется",
    "50": "⭐ 50 шагов — Детально",
    "100": "💎 100 шагов — Максимум деталей",
}

# Upscale factors
UPSCALE_LABELS = {
    "2": "2× — Удвоить разрешение",
    "4": "4× — Увеличить в 4 раза (рекомендуется)",
    "8": "8× — Максимальное увеличение",
}

# Duration (for videos)
DURATION_LABELS = {
    "3": "3 сек — Короткий клип",
    "5": "5 сек — Стандарт",
    "10": "10 сек — Длинный",
}


def get_parameter_label(param_name: str, value: any) -> str:
    """
    Get human-friendly label for parameter value.
    
    Args:
        param_name: Technical parameter name (e.g., "aspect_ratio", "resolution")
        value: Current value
        
    Returns:
        Human-friendly label or original value if no mapping exists
    """
    value_str = str(value)
    
    if param_name in {"aspect_ratio", "ratio"}:
        return ASPECT_RATIO_LABELS.get(value_str, value_str)
    elif param_name in {"image_size", "resolution", "size"}:
        return IMAGE_SIZE_LABELS.get(value_str, value_str)
    elif param_name in {"quality", "rendering_quality"}:
        return QUALITY_LABELS.get(value_str, value_str)
    elif param_name in {"steps", "num_inference_steps", "inference_steps"}:
        return STEPS_LABELS.get(value_str, value_str)
    elif param_name in {"upscale_factor", "scale"}:
        return UPSCALE_LABELS.get(value_str, value_str)
    elif param_name in {"duration", "video_duration"}:
        return DURATION_LABELS.get(value_str, value_str)
    
    return value_str


def get_parameter_options(param_name: str) -> Optional[List[Tuple[str, str]]]:
    """
    Get list of (value, label) pairs for parameter.
    Returns None if parameter should not use buttons.
    
    Args:
        param_name: Parameter name
        
    Returns:
        List of (value, label) tuples or None
    """
    if param_name in {"aspect_ratio", "ratio"}:
        return [(k, v) for k, v in ASPECT_RATIO_LABELS.items()]
    elif param_name in {"image_size", "resolution", "size"}:
        # Return most common sizes
        return [
            ("1024x1024", IMAGE_SIZE_LABELS["1024x1024"]),
            ("1920x1080", IMAGE_SIZE_LABELS["1920x1080"]),
            ("768x768", IMAGE_SIZE_LABELS["768x768"]),
        ]
    elif param_name in {"quality", "rendering_quality"}:
        return [(k, v) for k, v in QUALITY_LABELS.items()]
    elif param_name in {"steps", "num_inference_steps", "inference_steps"}:
        return [
            ("30", STEPS_LABELS["30"]),
            ("50", STEPS_LABELS["50"]),
            ("20", STEPS_LABELS["20"]),
        ]
    elif param_name in {"upscale_factor", "scale"}:
        return [(k, v) for k, v in UPSCALE_LABELS.items()]
    elif param_name in {"duration", "video_duration"}:
        return [(k, v) for k, v in DURATION_LABELS.items()]
    
    return None


def get_parameter_help(param_name: str) -> str:
    """
    Get help text explaining what this parameter does.
    
    Args:
        param_name: Parameter name
        
    Returns:
        Help text
    """
    help_texts = {
        "aspect_ratio": (
            "📐 <b>Соотношение сторон</b>\n\n"
            "Определяет пропорции изображения.\n\n"
            "• 1:1 — Квадрат (Instagram посты)\n"
            "• 9:16 — Вертикаль (Stories, Reels, TikTok)\n"
            "• 16:9 — Горизонталь (YouTube, презентации)\n"
            "• 4:3 — Классическое фото"
        ),
        "image_size": (
            "📏 <b>Разрешение изображения</b>\n\n"
            "Чем выше разрешение, тем детальнее результат, но дольше генерация.\n\n"
            "• 1024×1024 — Оптимальный баланс (рекомендуется)\n"
            "• 1920×1080 — Full HD для видео/баннеров\n"
            "• 768×768 — Быстрая генерация"
        ),
        "quality": (
            "⭐ <b>Качество рендера</b>\n\n"
            "• Черновик — Быстро, для тестов\n"
            "• Нормальное — Баланс скорость/качество\n"
            "• Высокое — Детализация важнее скорости\n"
            "• Ультра — Максимум деталей (медленно)"
        ),
        "steps": (
            "🔄 <b>Шаги генерации</b>\n\n"
            "Количество итераций для улучшения изображения.\n\n"
            "• 20 шагов — Быстро, базовое качество\n"
            "• 30 шагов — Оптимально (рекомендуется)\n"
            "• 50+ шагов — Максимальная детализация"
        ),
        "upscale_factor": (
            "🔍 <b>Коэффициент увеличения</b>\n\n"
            "Во сколько раз увеличить разрешение.\n\n"
            "• 2× — Удвоение (512 → 1024)\n"
            "• 4× — Четырёхкратное (512 → 2048)\n"
            "• 8× — Максимум (медленно, много памяти)"
        ),
        "duration": (
            "⏱️ <b>Длительность видео</b>\n\n"
            "• 3 сек — Короткий клип\n"
            "• 5 сек — Стандарт для социальных сетей\n"
            "• 10 сек — Длинное видео (дороже)"
        ),
        "seed": (
            "🎲 <b>Seed (зерно генерации)</b>\n\n"
            "Число для воспроизводимости результата.\n\n"
            "• Одинаковый seed + одинаковый промпт = одинаковый результат\n"
            "• Оставьте пустым для случайного результата"
        ),
        "guidance_scale": (
            "🎯 <b>Сила следования промпту</b>\n\n"
            "Насколько точно следовать вашему описанию.\n\n"
            "• Низкие значения (3-5) — Больше креатива\n"
            "• Средние (7-9) — Баланс (рекомендуется)\n"
            "• Высокие (12+) — Строгое следование промпту"
        ),
        "strength": (
            "💪 <b>Сила изменений</b>\n\n"
            "Насколько сильно изменить исходное изображение.\n\n"
            "• 0.3-0.5 — Лёгкие правки, сохранить основу\n"
            "• 0.6-0.8 — Средние изменения (рекомендуется)\n"
            "• 0.9-1.0 — Сильные изменения, почти новое изображение"
        ),
    }
    
    # Try exact match
    if param_name in help_texts:
        return help_texts[param_name]
    
    # Try partial match
    for key, text in help_texts.items():
        if key in param_name or param_name in key:
            return text
    
    return f"ℹ️ Параметр: {param_name}\n\nИспользуйте значение по умолчанию если не уверены."


def should_use_buttons(param_name: str) -> bool:
    """Returns True if this parameter should use buttons instead of free text input."""
    button_params = {
        "aspect_ratio", "ratio",
        "image_size", "resolution", "size",
        "quality", "rendering_quality",
        "steps", "num_inference_steps",
        "upscale_factor", "scale",
        "duration", "video_duration",
    }
    return param_name in button_params
