"""
Pricing calculator: USER_PRICE_RUB = PRICE_USD × USD_TO_RUB × 2

ФОРМУЛА ЦЕНООБРАЗОВАНИЯ:
  1. Цены в source_of_truth.json в USD
  2. Конвертация в RUB: kie_cost_rub = price_usd × USD_TO_RUB
  3. Наценка пользователю: user_price_rub = kie_cost_rub × 2
  
  Итого: user_price_rub = price_usd × USD_TO_RUB × MARKUP_MULTIPLIER

ЗАКОН ПРОЕКТА: цена для пользователя всегда в 2 раза выше стоимости Kie.ai.
Это правило НЕ конфигурируется и применяется ко всем моделям.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Exchange rate (MUST match scripts/audit_pricing.py)
USD_TO_RUB = 78.0

# Markup коэффициент (НЕ ИЗМЕНЯТЬ)
MARKUP_MULTIPLIER = 2.0

# Fallback цены в USD (если модель не в source_of_truth)
# Синхронизировано с scripts/enrich_registry.py
# Формат: {model_id: price_usd}
FALLBACK_PRICES_USD = {
    # Text-to-Image
    "flux/pro": 12.0,
    "flux/dev": 8.0,
    "flux/kontext": 12.0,
    "flux-2/pro-text-to-image": 15.0,
    "flux-2/flex-text-to-image": 10.0,
    
    # Image-to-Image
    "flux-2/pro-image-to-image": 18.0,
    "flux-2/flex-image-to-image": 12.0,
    
    # Google Imagen
    "google/imagen4": 15.0,
    "google/imagen4-fast": 10.0,
    "google/imagen4-ultra": 20.0,
    "google/nano-banana": 8.0,
    "google/nano-banana-edit": 10.0,
    "google/nano-banana-pro": 12.0,
    "google/veo-3": 150.0,
    "google/veo-3.1": 180.0,
    
    # Grok Imagine
    "grok-imagine/text-to-image": 12.0,
    "grok-imagine/text-to-video": 100.0,
    "grok-imagine/image-to-video": 90.0,
    "grok/imagine": 70.0,
    
    # Hailuo (MiniMax)
    "hailuo/02-text-to-video-pro": 120.0,
    "hailuo/02-text-to-video-standard": 90.0,
    "hailuo/02-image-to-video-pro": 110.0,
    "hailuo/02-image-to-video-standard": 85.0,
    "hailuo/2-3-image-to-video-pro": 110.0,
    "hailuo/2-3-image-to-video-standard": 85.0,
    "hailuo/2.3": 100.0,
    
    # Ideogram v3
    "ideogram/character": 15.0,
    "ideogram/character-edit": 18.0,
    "ideogram/character-remix": 18.0,
    "ideogram/v3-text-to-image": 15.0,
    "ideogram/v3-edit": 18.0,
    "ideogram/v3-remix": 18.0,
    "ideogram/v3-reframe": 18.0,
    
    # Kling
    "kling/v1-standard": 80.0,
    "kling/v1-pro": 120.0,
    "kling/v1-image-to-video": 100.0,
    "kling-2.6/image-to-video": 100.0,
    "kling-2.6/text-to-video": 110.0,
    
    # Luma Ray
    "luma-ray/extend": 90.0,
    "luma-ray/image-to-video": 100.0,
    "luma-ray/text-to-video": 110.0,
    
    # Minimax
    "minimax/image-01-live": 80.0,
    "minimax/text-01-live": 90.0,
    "minimax/v1-image-to-video": 85.0,
    "minimax/v1-text-to-video": 95.0,
    
    # Nolipix
    "nolipix/add-face": 20.0,
    "nolipix/change-costume": 20.0,
    "nolipix/flux-face-swap": 15.0,
    "nolipix/recraft-face-swap": 15.0,
    
    # Pika
    "pika/image-to-video": 90.0,
    "pika/text-to-video": 100.0,
    "pika/video-to-video": 95.0,
    
    # Recraft
    "recraft/remove-background": 8.0,
    "recraft/recolor-image": 10.0,
    "recraft/vectorize": 12.0,
    "recraft/crisp-upscale": 12.0,
    
    # Runway
    "runway/gen3-alpha-image-to-video": 120.0,
    "runway/gen3-alpha-text-to-video": 130.0,
    "runway/gen3-text-to-video": 130.0,
    "runway/gen3-turbo-image-to-video": 110.0,
    "runway/gen3-turbo-text-to-video": 120.0,
    
    # Suno
    "suno/v4": 30.0,
    "suno/v5": 25.0,
    
    # Topaz
    "topaz/image-upscale": 15.0,
    "topaz/image-upscale-prototype": 18.0,
    "topaz/video-upscale": 50.0,
    "topaz/video-upscale-prototype": 55.0,
    
    # ByteDance (Seedream)
    "bytedance/seedream": 10.0,
    "bytedance/seedream-v4-text-to-image": 12.0,
    "bytedance/seedream-v4-edit": 15.0,
    "bytedance/v1-lite-text-to-video": 70.0,
    "bytedance/v1-pro-text-to-video": 110.0,
    "bytedance/v1-pro-fast-image-to-video": 95.0,
    
    # InfiniTalk
    "infinitalk/from-audio": 20.0,
    "infinitalk/from-image": 20.0,
    
    # ElevenLabs
    "elevenlabs/text-to-speech": 5.0,
    "elevenlabs/speech-to-text": 3.0,
    "elevenlabs/sound-effect": 8.0,
    "elevenlabs/audio-isolation": 5.0,
    "elevenlabs/text-to-speech-multilingual-v2": 5.0,
    "elevenlabs/sound-effect-v2": 8.0,
}


def calculate_kie_cost(
    model: Dict[str, Any],
    user_inputs: Dict[str, Any],
    kie_response: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate real Kie.ai cost in RUB.
    
    Priority:
    1. kie_response['cost'] or ['price'] if available (assumed in RUB)
    2. model['price'] from registry (in USD) → convert to RUB
    3. FALLBACK_PRICES_USD (in USD) → convert to RUB
    4. Default 10.0 USD → convert to RUB
    
    Args:
        model: Model metadata from registry
        user_inputs: User parameters (steps, duration, resolution, etc.)
        kie_response: Optional Kie.ai API response with actual cost (in RUB)
        
    Returns:
        Cost in RUB (float)
    """
    model_id = model.get("model_id", "unknown")
    
    # Priority 1: Use Kie.ai response cost if available (assumed in RUB)
    if kie_response:
        for key in ["cost", "price", "usage_cost", "credits_used"]:
            if key in kie_response:
                cost_rub = float(kie_response[key])
                logger.info(f"Using Kie.ai response cost for {model_id}: {cost_rub} RUB")
                return cost_rub
    
    # Priority 2: Model registry price (in USD → convert to RUB)
    registry_price_usd = model.get("price")
    if registry_price_usd is not None:
        try:
            price_usd = float(registry_price_usd)
            if price_usd > 0:
                cost_rub = price_usd * USD_TO_RUB
                logger.info(f"Using registry price for {model_id}: ${price_usd} → {cost_rub} RUB")
                return cost_rub
        except (TypeError, ValueError):
            logger.warning(f"Invalid registry price for {model_id}: {registry_price_usd}")
            pass
    
    # Priority 3: Fallback table (in USD → convert to RUB)
    if model_id in FALLBACK_PRICES_USD:
        price_usd = FALLBACK_PRICES_USD[model_id]
        cost_rub = price_usd * USD_TO_RUB
        logger.info(f"Using fallback price for {model_id}: ${price_usd} → {cost_rub} RUB")
        return cost_rub
    
    # Priority 4: Default (in USD → convert to RUB)
    default_usd = 10.0
    cost_rub = default_usd * USD_TO_RUB
    logger.warning(f"No price info for {model_id}, using default ${default_usd} → {cost_rub} RUB")
    return cost_rub


def calculate_user_price(kie_cost_rub: float) -> float:
    """
    Calculate user price: USER_PRICE_RUB = KIE_COST_RUB × 2
    
    Args:
        kie_cost_rub: Kie.ai cost in RUB (already converted from USD if needed)
        
    Returns:
        User price in RUB (rounded to 2 decimals)
    """
    user_price = kie_cost_rub * MARKUP_MULTIPLIER
    result = round(user_price, 2)
    
    # ASSERT: verify pricing formula
    assert result == round(kie_cost_rub * 2, 2), \
        f"Pricing formula violated: {result} != {kie_cost_rub} * 2"
    
    return result


def format_price_rub(price: float) -> str:
    """Format price for display: '96.00 ₽' or 'Бесплатно'."""
    if price == 0:
        return "Бесплатно"
    return f"{price:.2f} ₽"


def create_charge_metadata(
    model: Dict[str, Any],
    user_inputs: Dict[str, Any],
    kie_response: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create charge metadata with pricing info.
    
    Returns:
        {
            'kie_cost_rub': float,
            'user_price_rub': float,
            'markup': 'x2',
            'model_id': str,
            'timestamp': str
        }
    """
    from datetime import datetime
    
    kie_cost = calculate_kie_cost(model, user_inputs, kie_response)
    user_price = calculate_user_price(kie_cost)
    
    # ASSERT: проверка формулы
    assert user_price == round(kie_cost * 2, 2), f"Pricing formula violated: {user_price} != {kie_cost} * 2"
    
    return {
        'kie_cost_rub': kie_cost,
        'user_price_rub': user_price,
        'markup': 'x2',
        'model_id': model.get('model_id'),
        'timestamp': datetime.now().isoformat()
    }
