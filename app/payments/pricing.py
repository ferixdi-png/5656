"""
Pricing calculator: USER_PRICE_RUB = KIE_PRICE_RUB × 2

ЗАКОН ПРОЕКТА: цена для пользователя всегда в 2 раза выше стоимости Kie.ai.
Это правило НЕ конфигурируется и применяется ко всем моделям.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Markup коэффициент (НЕ ИЗМЕНЯТЬ)
MARKUP_MULTIPLIER = 2.0

# Fallback цены если Kie.ai не возвращает cost
# Формат: {model_id: base_price_rub}
FALLBACK_PRICES_RUB = {
    # Text-to-Image
    "flux/pro": 12.0,
    "flux/dev": 8.0,
    "flux-2/pro-text-to-image": 15.0,
    "flux-2/flex-text-to-image": 10.0,
    
    # Image-to-Image
    "flux-2/pro-image-to-image": 18.0,
    "flux-2/flex-image-to-image": 12.0,
    
    # Text-to-Video
    "google/veo-3": 150.0,
    "google/veo-3.1": 180.0,
    "kling/v1-standard": 80.0,
    "kling/v1-pro": 120.0,
    "hailuo/02-text-to-video-standard": 90.0,
    
    # Image-to-Video
    "kling/v1-image-to-video": 100.0,
    "grok/imagine": 70.0,
    
    # Upscale
    "topaz/image-upscale": 15.0,
    "topaz/video-upscale": 50.0,
    "recraft/crisp-upscale": 12.0,
    
    # Audio
    "elevenlabs/text-to-speech": 5.0,
    "elevenlabs/speech-to-text": 3.0,
    "elevenlabs/sound-effect": 8.0,
    "suno/v5": 25.0,
    
    # Other
    "recraft/remove-background": 8.0,
}


def calculate_kie_cost(
    model: Dict[str, Any],
    user_inputs: Dict[str, Any],
    kie_response: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate real Kie.ai cost in RUB.
    
    Priority:
    1. kie_response['cost'] or ['price'] if available
    2. model['price'] from registry (may have parameter-based formula)
    3. FALLBACK_PRICES_RUB
    4. Default 10.0 RUB
    
    Args:
        model: Model metadata from registry
        user_inputs: User parameters (steps, duration, resolution, etc.)
        kie_response: Optional Kie.ai API response with actual cost
        
    Returns:
        Cost in RUB (float)
    """
    model_id = model.get("model_id", "unknown")
    
    # Priority 1: Use Kie.ai response cost if available
    if kie_response:
        for key in ["cost", "price", "usage_cost", "credits_used"]:
            if key in kie_response:
                cost = float(kie_response[key])
                logger.info(f"Using Kie.ai response cost for {model_id}: {cost} RUB")
                return cost
    
    # Priority 2: Model registry price (может быть формула)
    registry_price = model.get("price")
    if registry_price is not None:
        try:
            cost = float(registry_price)
            if cost > 0:
                logger.info(f"Using registry price for {model_id}: {cost} RUB")
                return cost
        except (TypeError, ValueError):
            # Может быть строка с формулой, но пока не реализуем
            pass
    
    # Priority 3: Fallback table
    if model_id in FALLBACK_PRICES_RUB:
        cost = FALLBACK_PRICES_RUB[model_id]
        logger.info(f"Using fallback price for {model_id}: {cost} RUB")
        return cost
    
    # Priority 4: Default
    logger.warning(f"No price info for {model_id}, using default 10.0 RUB")
    return 10.0


def calculate_user_price(kie_cost_rub: float) -> float:
    """
    Calculate user price: USER_PRICE_RUB = KIE_COST_RUB × 2
    
    Args:
        kie_cost_rub: Kie.ai cost in RUB
        
    Returns:
        User price in RUB (rounded to 2 decimals)
    """
    user_price = kie_cost_rub * MARKUP_MULTIPLIER
    return round(user_price, 2)


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
