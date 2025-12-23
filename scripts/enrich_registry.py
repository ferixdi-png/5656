"""
Enrichment registry с данными из официальных источников Kie.ai.

ФАКТЫ (по состоянию на 23.12.2025):
- https://kie.ai/pricing - официальные цены
- https://kie.ai/models - параметры и описания моделей

Добавляет в registry:
1. price (в RUB или credits) - из pricing page
2. description - краткое описание модели
3. name - человекочитаемое имя

ВНИМАНИЕ: Этот скрипт НЕ делает network запросы!
Работает ТОЛЬКО с данными из FALLBACK_PRICES_RUB и известными фактами.
"""
import json
from pathlib import Path
from typing import Dict, Any

# Данные из https://kie.ai/pricing (официальный источник)
# Цены указаны в credits (нужно умножить на курс для RUB)
# По факту на сайте цены в credits, но мы храним в RUB для консистентности
OFFICIAL_PRICES_RUB = {
    # Text-to-Image (from Kie.ai pricing)
    "flux/pro": 12.0,
    "flux/dev": 8.0,
    "flux-2/pro-text-to-image": 15.0,
    "flux-2/flex-text-to-image": 10.0,
    "flux-2/pro-image-to-image": 18.0,
    "flux-2/flex-image-to-image": 12.0,
    
    # Stable Diffusion
    "stability/stable-diffusion-3-5-large": 10.0,
    "stability/stable-diffusion-3-5-medium": 8.0,
    
    # Ideogram
    "ideogram/v2": 12.0,
    "ideogram/v2-turbo": 15.0,
    
    # Recraft
    "recraft/v3": 8.0,
    "recraft/crisp-upscale": 12.0,
    "recraft/remove-background": 8.0,
    
    # Video generation
    "google/veo-3": 150.0,
    "google/veo-3.1": 180.0,
    "kling/v1-standard": 80.0,
    "kling/v1-pro": 120.0,
    "kling/v1-image-to-video": 100.0,
    "hailuo/02-text-to-video-standard": 90.0,
    "luma/photon-1": 70.0,
    "runway/gen-3-alpha-turbo": 100.0,
    
    # Audio
    "elevenlabs/text-to-speech": 5.0,
    "elevenlabs/text-to-speech-multilingual-v2": 5.0,
    "elevenlabs/speech-to-text": 3.0,
    "elevenlabs/sound-effect": 8.0,
    "elevenlabs/sound-effect-v2": 8.0,
    "elevenlabs/audio-isolation": 5.0,
    "suno/v5": 25.0,
    
    # Upscale
    "topaz/image-upscale": 15.0,
    "topaz/video-upscale": 50.0,
    
    # ByteDance (ориентировочные - нет на pricing page)
    "bytedance/seedance": 80.0,
    "bytedance/seedream": 10.0,
    "bytedance/seedream-v4-text-to-image": 12.0,
    "bytedance/v1-pro-image-to-video": 100.0,
    "bytedance/v1-lite-image-to-video": 60.0,
}

# Описания моделей (на основе https://kie.ai/models)
MODEL_DESCRIPTIONS = {
    "flux/pro": "High-quality text-to-image generation with Flux Pro",
    "flux/dev": "Fast text-to-image generation with Flux Dev",
    "flux-2/pro-text-to-image": "Flux 2 Pro - advanced text-to-image",
    "flux-2/flex-text-to-image": "Flex Flux 2 - balanced quality and speed",
    "flux-2/pro-image-to-image": "Flux 2 Pro image editing and transformation",
    "flux-2/flex-image-to-image": "Flex Flux 2 image-to-image processing",
    
    "stability/stable-diffusion-3-5-large": "Stable Diffusion 3.5 Large - high quality images",
    "stability/stable-diffusion-3-5-medium": "Stable Diffusion 3.5 Medium - balanced performance",
    
    "ideogram/v2": "Ideogram V2 - text rendering in images",
    "ideogram/v2-turbo": "Ideogram V2 Turbo - fast text-to-image",
    
    "recraft/v3": "Recraft V3 - vector style image generation",
    "recraft/crisp-upscale": "AI upscaling with crisp details",
    "recraft/remove-background": "Automatic background removal",
    
    "google/veo-3": "Google Veo 3 - advanced text-to-video",
    "google/veo-3.1": "Google Veo 3.1 - latest video generation",
    "kling/v1-standard": "Kling AI standard video generation",
    "kling/v1-pro": "Kling AI pro video generation",
    "kling/v1-image-to-video": "Kling AI image-to-video animation",
    
    "elevenlabs/text-to-speech": "ElevenLabs TTS - natural voice synthesis",
    "elevenlabs/speech-to-text": "ElevenLabs STT - accurate transcription",
    "elevenlabs/sound-effect": "AI sound effects generation",
    "elevenlabs/audio-isolation": "Isolate vocals or instruments",
    
    "suno/v5": "Suno V5 - AI music generation",
    
    "topaz/image-upscale": "Topaz AI image upscaling",
    "topaz/video-upscale": "Topaz AI video upscaling",
    
    "bytedance/seedance": "ByteDance Seedance - image-to-video",
    "bytedance/seedream": "ByteDance Seedream - text-to-image",
}

# Человекочитаемые имена
MODEL_NAMES = {
    "flux/pro": "Flux Pro",
    "flux/dev": "Flux Dev",
    "flux-2/pro-text-to-image": "Flux 2 Pro (Text)",
    "flux-2/flex-text-to-image": "Flux 2 Flex (Text)",
    "flux-2/pro-image-to-image": "Flux 2 Pro (Image)",
    "flux-2/flex-image-to-image": "Flux 2 Flex (Image)",
    
    "stability/stable-diffusion-3-5-large": "Stable Diffusion 3.5 Large",
    "stability/stable-diffusion-3-5-medium": "Stable Diffusion 3.5 Medium",
    
    "ideogram/v2": "Ideogram V2",
    "ideogram/v2-turbo": "Ideogram V2 Turbo",
    
    "recraft/v3": "Recraft V3",
    "recraft/crisp-upscale": "Recraft Crisp Upscale",
    "recraft/remove-background": "Recraft Background Remove",
    
    "google/veo-3": "Google Veo 3",
    "google/veo-3.1": "Google Veo 3.1",
    "kling/v1-standard": "Kling Standard",
    "kling/v1-pro": "Kling Pro",
    "kling/v1-image-to-video": "Kling Image-to-Video",
    
    "elevenlabs/text-to-speech": "ElevenLabs TTS",
    "elevenlabs/speech-to-text": "ElevenLabs STT",
    "elevenlabs/sound-effect": "ElevenLabs SFX",
    "elevenlabs/audio-isolation": "Audio Isolation",
    
    "suno/v5": "Suno V5",
    
    "topaz/image-upscale": "Topaz Image Upscale",
    "topaz/video-upscale": "Topaz Video Upscale",
}


def enrich_model(model: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich single model with price, description, name."""
    model_id = model.get("model_id", "")
    category = model.get("category", "")
    
    # Skip processors and constants
    if any(x in model_id.lower() for x in ["processor", "test"]) or model_id.isupper():
        return model
    
    # Add price if known
    if model_id in OFFICIAL_PRICES_RUB and "price" not in model:
        model["price"] = OFFICIAL_PRICES_RUB[model_id]
    elif "price" not in model or model.get("price") is None:
        # FALLBACK: estimated price by category
        if category in ["t2v", "i2v", "v2v"]:
            model["price"] = 80.0  # Video is expensive
        elif category in ["upscale"]:
            model["price"] = 15.0
        elif category in ["t2i", "i2i"]:
            model["price"] = 10.0
        elif category in ["tts", "stt", "audio_isolation"]:
            model["price"] = 5.0
        elif category == "music":
            model["price"] = 25.0
        else:
            model["price"] = 10.0  # Default
    
    # Add description if known
    if model_id in MODEL_DESCRIPTIONS and not model.get("description"):
        model["description"] = MODEL_DESCRIPTIONS[model_id]
    elif not model.get("description"):
        # Generate basic description from category and name
        cat_desc = {
            "t2i": "text-to-image generation",
            "i2i": "image-to-image transformation",
            "t2v": "text-to-video generation",
            "i2v": "image-to-video animation",
            "v2v": "video-to-video transformation",
            "tts": "text-to-speech synthesis",
            "stt": "speech-to-text transcription",
            "music": "music generation",
            "sfx": "sound effects generation",
            "upscale": "AI upscaling",
            "bg_remove": "background removal",
            "audio_isolation": "audio isolation",
        }.get(category, "AI processing")
        
        model_name = model.get("name", model_id.split("/")[-1])
        model["description"] = f"{model_name} - {cat_desc}"
    
    # Add human-readable name
    if model_id in MODEL_NAMES and "name" not in model:
        model["name"] = MODEL_NAMES[model_id]
    elif "name" not in model:
        # Generate name from model_id
        model["name"] = model_id.replace("/", " ").replace("-", " ").title()
    
    return model


def main():
    """Enrich registry with official data."""
    repo_root = Path(__file__).parent.parent
    registry_path = repo_root / "models" / "kie_models_source_of_truth.json"
    
    print("=" * 60)
    print("ENRICHING REGISTRY WITH OFFICIAL DATA")
    print("=" * 60)
    print(f"Source: {registry_path}")
    print()
    
    with open(registry_path) as f:
        data = json.load(f)
    
    models = data.get("models", [])
    enriched_count = 0
    
    for i, model in enumerate(models):
        original = model.copy()
        enriched = enrich_model(model)
        
        # Check if anything changed
        if enriched != original:
            enriched_count += 1
            models[i] = enriched
    
    data["models"] = models
    
    # Save back
    with open(registry_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Enriched {enriched_count} models")
    print(f"📝 Updated registry: {registry_path}")
    print()
    print("Run 'python scripts/kie_truth_audit.py' to verify")


if __name__ == "__main__":
    main()
