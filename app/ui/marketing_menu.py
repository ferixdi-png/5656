"""
Marketing-focused UI structure for bot.

Маркетинговые категории для SMM/маркетологов:
- Видео-креативы (Reels/Shorts/TikTok)
- Визуалы (баннеры, посты, обложки)
- Тексты (посты, описания)
- Аватары/UGC
- Озвучка/аудио
- Улучшалки (апскейл, фон)
- Экспериментальные
"""
from typing import Dict, List
import json
import os


MARKETING_CATEGORIES = {
    "video_creatives": {
        "emoji": "🎥",
        "title": "Видео-креативы",
        "desc": "Reels, Shorts, TikTok",
        "kie_categories": ["t2v", "i2v", "v2v"],
        "tags": ["reels", "shorts", "tiktok", "video"]
    },
    "visuals": {
        "emoji": "🖼️",
        "title": "Визуалы",
        "desc": "Баннеры, посты, обложки",
        "kie_categories": ["t2i", "i2i"],
        "tags": ["banner", "post", "cover", "image"]
    },
    "texts": {
        "emoji": "✍️",
        "title": "Тексты",
        "desc": "Посты, описания, сценарии",
        "kie_categories": ["other"],  # text models
        "tags": ["text", "copy", "script"]
    },
    "avatars_ugc": {
        "emoji": "🧑‍🎤",
        "title": "Аватары/UGC",
        "desc": "Персонажи, говорящие головы",
        "kie_categories": ["lip_sync", "i2i"],
        "tags": ["avatar", "character", "lipsync"]
    },
    "audio": {
        "emoji": "🔊",
        "title": "Озвучка/аудио",
        "desc": "TTS, музыка, эффекты",
        "kie_categories": ["tts", "music", "sfx", "stt"],
        "tags": ["audio", "voice", "music"]
    },
    "tools": {
        "emoji": "🧰",
        "title": "Улучшалки",
        "desc": "Апскейл, фон, рестайл",
        "kie_categories": ["upscale", "bg_remove", "watermark_remove"],
        "tags": ["upscale", "background", "enhance"]
    },
    "experimental": {
        "emoji": "🧪",
        "title": "Экспериментальные",
        "desc": "Новые и редкие модели",
        "kie_categories": ["audio_isolation"],
        "tags": ["experimental", "beta"]
    }
}


def load_registry() -> List[Dict]:
    """Load KIE models registry."""
    registry_path = os.path.join(
        os.path.dirname(__file__),
        "../../models/kie_models_source_of_truth.json"
    )
    
    if not os.path.exists(registry_path):
        return []
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get("models", [])


def map_model_to_marketing_category(model: Dict) -> str:
    """Map KIE model to marketing category."""
    category = model.get("category", "")
    model_id = model.get("model_id", "")
    
    # Check each marketing category
    for mk_cat, mk_data in MARKETING_CATEGORIES.items():
        if category in mk_data["kie_categories"]:
            return mk_cat
        
        # Check by tags
        for tag in mk_data.get("tags", []):
            if tag in model_id.lower():
                return mk_cat
    
    # Default to experimental
    return "experimental"


def build_ui_tree() -> Dict[str, List[Dict]]:
    """
    Build UI tree from registry.
    
    Includes ALL models that are enabled (is_pricing_known=True).
    Models without input_schema will use fallback (prompt-only).
    
    MASTER PROMPT compliance:
    - Sort models by price: cheapest first, then medium, then expensive
    - Show ALL models with known pricing
    """
    registry = load_registry()
    tree = {cat: [] for cat in MARKETING_CATEGORIES.keys()}
    
    for model in registry:
        # Skip non-model entries
        if model.get("type") != "model":
            continue
        
        # Skip disabled models without pricing
        if not model.get("is_pricing_known", False):
            continue
        
        # REMOVED FILTER: All models with pricing are shown
        # Models without input_schema will use fallback in builder/validator
        
        mk_cat = map_model_to_marketing_category(model)
        tree[mk_cat].append(model)
    
    # MASTER PROMPT: Sort each category by price (cheapest first)
    for cat in tree:
        tree[cat].sort(key=lambda m: m.get("price", 999999))
    
    return tree


def get_category_info(category_key: str) -> Dict:
    """Get marketing category info."""
    return MARKETING_CATEGORIES.get(category_key, {})


def get_model_by_id(model_id: str) -> Dict:
    """Get model from registry by ID."""
    registry = load_registry()
    for model in registry:
        if model.get("model_id") == model_id:
            return model
    return {}


def count_models_by_category() -> Dict[str, int]:
    """Count models in each marketing category."""
    tree = build_ui_tree()
    return {cat: len(models) for cat, models in tree.items()}
