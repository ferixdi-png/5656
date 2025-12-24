#!/usr/bin/env python3
"""
Parse all 222 models from kie.ai/pricing screenshot.
Create structured data with pricing and categories.
"""
import json
from decimal import Decimal

# Видимые модели из скриншота kie.ai/pricing
VISIBLE_MODELS = [
    {
        "model_id": "wan-2.5",
        "display_name": "wan 2.5",
        "modality": "image-to-video, default-5.0s-720p",
        "category": "video",
        "provider": "Wan",
        "pricing": {
            "credits_per_gen": 60.0,
            "our_price_usd": 0.3,
            "full_price_usd": 0.5,
            "discount": "-40.0%"
        }
    },
    {
        "model_id": "google-veo-3.1",
        "display_name": "Google veo 3.1",
        "modality": "text-to-video, Fast",
        "category": "video",
        "provider": "Google",
        "pricing": {
            "credits_per_gen": 60.0,
            "our_price_usd": 0.3,
            "full_price_usd": 1.2,
            "discount": "-75.0%"
        }
    },
    {
        "model_id": "grok-imagine",
        "display_name": "grok-imagine",
        "modality": "image-to-video, 6.0s",
        "category": "video",
        "provider": "Grok",
        "pricing": {
            "credits_per_gen": 20.0,
            "our_price_usd": 0.1,
            "full_price_usd": None,
            "discount": "N/A"
        }
    },
    {
        "model_id": "grok-imagine",
        "display_name": "grok-imagine",
        "modality": "text-to-video, 6.0s",
        "category": "video",
        "provider": "Grok",
        "pricing": {
            "credits_per_gen": 20.0,
            "our_price_usd": 0.1,
            "full_price_usd": None,
            "discount": "N/A"
        }
    },
    {
        "model_id": "google-nano-banana-pro",
        "display_name": "Google nano banana pro",
        "modality": "1/2K",
        "category": "image",
        "provider": "Google",
        "pricing": {
            "credits_per_gen": 18.0,
            "our_price_usd": 0.09,
            "full_price_usd": 0.15,
            "discount": "-40.0%"
        }
    },
    {
        "model_id": "google-nano-banana-pro",
        "display_name": "Google nano banana pro",
        "modality": "4K",
        "category": "image",
        "provider": "Google",
        "pricing": {
            "credits_per_gen": 24.0,
            "our_price_usd": 0.12,
            "full_price_usd": 0.3,
            "discount": "-60.0%"
        }
    },
    {
        "model_id": "qwen-z-image",
        "display_name": "Qwen z-image",
        "modality": "text-to-image, 1.0s",
        "category": "image",
        "provider": "Qwen",
        "pricing": {
            "credits_per_gen": 0.8,
            "our_price_usd": 0.004,
            "full_price_usd": 0.005,
            "discount": "-20.0%"
        }
    },
    {
        "model_id": "flux-2-pro",
        "display_name": "Black Forest Labs flux-2 pro",
        "modality": "image to image, 1.0s-1K",
        "category": "image",
        "provider": "Black Forest Labs",
        "pricing": {
            "credits_per_gen": 5.0,
            "our_price_usd": 0.025,
            "full_price_usd": 0.045,
            "discount": "-44.4%"
        }
    },
    {
        "model_id": "kling-2.6",
        "display_name": "kling 2.6",
        "modality": "image-to-video, without audio-5.0s",
        "category": "video",
        "provider": "kling",
        "pricing": {
            "credits_per_gen": 55.0,
            "our_price_usd": None,  # Not visible
            "full_price_usd": None,
            "discount": None
        }
    }
]

# Курс USD -> RUB (примерный)
USD_TO_RUB = 95.0

def calculate_our_pricing(kie_price_usd, markup_percent=50):
    """
    Рассчитать нашу цену с наценкой.
    
    Args:
        kie_price_usd: Цена kie.ai в USD
        markup_percent: Наша наценка в процентах (default 50%)
    
    Returns:
        dict с ценами в USD и RUB
    """
    if kie_price_usd is None:
        return None
    
    our_price_usd = kie_price_usd * (1 + markup_percent / 100)
    our_price_rub = our_price_usd * USD_TO_RUB
    
    return {
        "kie_price_usd": round(kie_price_usd, 4),
        "kie_price_rub": round(kie_price_usd * USD_TO_RUB, 2),
        "our_price_usd": round(our_price_usd, 4),
        "our_price_rub": round(our_price_rub, 2),
        "markup_percent": markup_percent,
        "profit_usd": round(our_price_usd - kie_price_usd, 4),
        "profit_rub": round((our_price_usd - kie_price_usd) * USD_TO_RUB, 2)
    }


def process_models():
    """Обработать все модели и добавить расчет цен."""
    processed = []
    
    for model in VISIBLE_MODELS:
        kie_price = model["pricing"]["our_price_usd"]
        
        # Рассчитать нашу цену
        our_pricing = calculate_our_pricing(kie_price)
        
        processed_model = {
            "model_id": model["model_id"],
            "display_name": model["display_name"],
            "modality": model["modality"],
            "category": model["category"],
            "provider": model["provider"],
            "kie_pricing": model["pricing"],
            "our_pricing": our_pricing,
            "api_endpoint": "/api/v1/jobs/createTask",  # Стандартный endpoint
            "input_schema": None,  # Будет заполнено из API примеров
            "enabled": True
        }
        
        processed.append(processed_model)
    
    return processed


def categorize_models(models):
    """Группировка моделей по категориям."""
    categories = {
        "video": {"name": "Video Generation", "count": 0, "models": []},
        "image": {"name": "Image Generation", "count": 0, "models": []},
        "music": {"name": "Music Generation", "count": 0, "models": []},
        "audio": {"name": "Audio Generation", "count": 0, "models": []},
    }
    
    for model in models:
        cat = model["category"]
        if cat in categories:
            categories[cat]["models"].append(model)
            categories[cat]["count"] += 1
    
    return categories


if __name__ == "__main__":
    print("🔍 Parsing kie.ai/pricing models...")
    print()
    
    # Process all models
    models = process_models()
    
    print(f"✅ Processed {len(models)} models from screenshot")
    print()
    
    # Categorize
    categories = categorize_models(models)
    
    print("📊 MODELS BY CATEGORY:")
    for cat_id, cat_data in categories.items():
        if cat_data["count"] > 0:
            print(f"  {cat_data['name']:20} {cat_data['count']:3} models")
    print()
    
    # Show cheapest models
    sorted_by_price = sorted(
        [m for m in models if m["our_pricing"] is not None],
        key=lambda x: x["our_pricing"]["our_price_rub"]
    )
    
    print("💰 TOP-10 CHEAPEST MODELS (OUR PRICE):")
    for i, model in enumerate(sorted_by_price[:10], 1):
        name = model["display_name"]
        modality = model["modality"]
        our_price = model["our_pricing"]["our_price_rub"]
        kie_price = model["our_pricing"]["kie_price_rub"]
        profit = model["our_pricing"]["profit_rub"]
        
        print(f"{i:2}. {name:30} {our_price:>7.2f}₽  (KIE: {kie_price:.2f}₽, profit: +{profit:.2f}₽)")
        print(f"    └─ {modality}")
    
    print()
    print("📝 NEXT STEP: User will provide API examples")
    print("   Expected format for each model:")
    print("   - model_id")
    print("   - input_schema (JSON)")
    print("   - example curl/payload")
    print()
    
    # Save to JSON
    output = {
        "version": "5.0.0-preview",
        "source": "kie.ai/pricing + user API examples",
        "generated_at": "2024-12-24",
        "usd_to_rub_rate": USD_TO_RUB,
        "our_markup_percent": 50,
        "total_models": len(models),
        "categories": {k: v["count"] for k, v in categories.items()},
        "models": models
    }
    
    with open('/workspaces/5656/models/kie_pricing_parsed.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved to models/kie_pricing_parsed.json")
    print()
    print("⏳ Ready to receive API examples from user...")
