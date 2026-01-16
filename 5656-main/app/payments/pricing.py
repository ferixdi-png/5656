"""
Pricing calculator: USER_PRICE_RUB = (PRICE_USD × 79) × 2

ФОРМУЛА ЦЕНООБРАЗОВАНИЯ (ЗАФИКСИРОВАНА НАВСЕГДА):
  1. Kie.ai цены в USD (1 кредит = $0.005)
  2. Курс конвертации: 79 RUB/USD (ФИКСИРОВАННЫЙ, НЕ МЕНЯЕТСЯ)
  3. Цена Kie.ai в RUB: kie_cost_rub = price_usd × 79
  4. Наценка пользователю: user_price_rub = kie_cost_rub × 2
  
  Итого: user_price_rub = price_usd × 79 × 2

ПРИМЕР:
  1 кредит Kie.ai = $0.005 USD
  Цена Kie.ai = 0.005 × 79 = 0.395 RUB
  Цена пользователю = 0.395 × 2 = 0.79 RUB за 1 кредит

ЗАКОН ПРОЕКТА: 
  - Курс 79 RUB/USD ФИКСИРОВАН и НЕ ИЗМЕНЯЕТСЯ
  - Наценка ×2 ФИКСИРОВАНА и НЕ ИЗМЕНЯЕТСЯ
  - Цены в SOURCE_OF_TRUTH хранятся БЕЗ наценки (Kie.ai cost)
  - Наценка применяется только в calculate_user_price()
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ФИКСИРОВАННЫЙ курс (НЕ ИЗМЕНЯТЬ!)
# Используется для всех расчётов, независимо от реального курса ЦБ
USD_TO_RUB = 78.0

# ФИКСИРОВАННЫЙ множитель наценки (НЕ ИЗМЕНЯТЬ!)
# Цена пользователю = Цена Kie.ai × 2
MARKUP_MULTIPLIER = 2.0

# Fallback prices for models without pricing in SOURCE_OF_TRUTH (in USD)
# These are converted to RUB using USD_TO_RUB when needed
FALLBACK_PRICES_USD = {
    "flux/pro": 12.0,
    "flux/dev": 5.0,
    "flux-2/pro-text-to-image": 15.0,
    "flux-2/flex-text-to-image": 8.0,
    "google/veo-3": 20.0,
    "kling/v1-standard": 10.0,
}


def calculate_kie_cost(
    model: Dict[str, Any],
    user_inputs: Dict[str, Any],
    kie_response: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate real Kie.ai cost in RUB.
    
    Priority:
    1. Parameterized pricing from pricing/KIE_PRICING_RUB.json (NEW)
    2. kie_response['cost'] or ['price'] if available (assumed in RUB)
    3. model['pricing']['rub_per_gen'] from SOURCE_OF_TRUTH (direct RUB)
    4. model['price'] from old registry (in USD) → convert to RUB
    5. Default 10.0 USD → convert to RUB
    
    Args:
        model: Model metadata from registry
        user_inputs: User parameters (steps, duration, resolution, etc.)
        kie_response: Optional Kie.ai API response with actual cost (in RUB)
        
    Returns:
        Cost in RUB (float)
    """
    # CRITICAL: Validate inputs
    if not isinstance(model, dict):
        logger.error(f"[PRICING] Invalid model type: {type(model)}")
        return 10.0 * USD_TO_RUB  # Fallback to default
    
    if not isinstance(user_inputs, dict):
        logger.error(f"[PRICING] Invalid user_inputs type: {type(user_inputs)}")
        return 10.0 * USD_TO_RUB  # Fallback to default
    
    model_id = model.get("model_id", "unknown")
    
    if not model_id or model_id == "unknown":
        logger.warning(f"[PRICING] Missing or invalid model_id in model: {model.get('model_id')}")
    
    # Priority 1: Parameterized pricing from pricing/KIE_PRICING_RUB.json
    try:
        from app.pricing.parameterized import calculate_price_rub as get_param_price
        # Determine I/O type from model category
        category = model.get("category", "")
        io_type = None
        if "video" in category.lower():
            if "text" in str(user_inputs.get("prompt", "")).lower() and "image" not in str(user_inputs).lower():
                io_type = "text-to-video"
            elif "image" in str(user_inputs).lower():
                io_type = "image-to-video"
        elif "image" in category.lower():
            if "image" in str(user_inputs).lower() and "prompt" in user_inputs:
                io_type = "image-to-image"
            elif "prompt" in user_inputs:
                io_type = "text-to-image"
        
        param_price = get_param_price(model_id, user_inputs, io_type)
        if param_price is not None:
            cost_rub = float(param_price)
            logger.info(f"[PRICING] Using parameterized pricing for {model_id}: {cost_rub} RUB (params: {user_inputs})")
            return cost_rub
    except ImportError:
        logger.debug(f"[PRICING] Parameterized pricing module not available for {model_id}")
    except Exception as e:
        logger.warning(f"[PRICING] Parameterized pricing failed for {model_id}: {e}", exc_info=True)
    
    # Priority 2: Use Kie.ai response cost if available (assumed in RUB)
    if kie_response and isinstance(kie_response, dict):
        for key in ["cost", "price", "usage_cost", "credits_used"]:
            if key in kie_response:
                try:
                    cost_rub = float(kie_response[key])
                    if cost_rub < 0:
                        logger.warning(f"[PRICING] Negative cost from Kie.ai response for {model_id}: {cost_rub}")
                        continue  # Skip negative costs
                    logger.info(f"[PRICING] Using Kie.ai response cost for {model_id}: {cost_rub} RUB (key={key})")
                    return cost_rub
                except (TypeError, ValueError) as e:
                    logger.warning(f"[PRICING] Invalid cost value in Kie.ai response for {model_id} (key={key}): {e}")
                    continue
    
    # Priority 3: SOURCE_OF_TRUTH format (direct RUB price)
    pricing = model.get("pricing", {})
    if isinstance(pricing, dict):
        # Check for pricing_rules (resolution-based, duration-based, etc.)
        pricing_rules = pricing.get("pricing_rules", {})
        if pricing_rules and isinstance(pricing_rules, dict):
            strategy = pricing_rules.get("strategy", "")
            
            # Resolution-based pricing (e.g., nano-banana-pro: 1K/2K=18, 4K=24)
            if strategy == "by_resolution" and "resolution" in pricing_rules:
                resolution = user_inputs.get("resolution", "1K")
                resolution_map = pricing_rules["resolution"]
                if isinstance(resolution_map, dict):
                    credits = resolution_map.get(str(resolution), resolution_map.get("1K", 18))
                    # Convert credits to RUB: 1 credit = $0.005 USD = 0.005 * 78 RUB = 0.39 RUB
                    cost_rub = credits * 0.005 * USD_TO_RUB
                    logger.info(f"Using pricing_rules (by_resolution) for {model_id}: resolution={resolution} → {credits} credits → {cost_rub} RUB")
                    return cost_rub
            
            # Duration-based pricing (future: for video models)
            if strategy == "by_duration" and "duration" in pricing_rules:
                duration = user_inputs.get("duration") or user_inputs.get("n_frames", "10")
                duration_map = pricing_rules["duration"]
                if isinstance(duration_map, dict):
                    # Find matching duration tier
                    credits = duration_map.get(str(duration), duration_map.get("default", 10))
                    cost_rub = credits * 0.005 * USD_TO_RUB
                    logger.info(f"Using pricing_rules (by_duration) for {model_id}: duration={duration} → {credits} credits → {cost_rub} RUB")
                    return cost_rub
        
        # Fallback to flat pricing
        rub_price = pricing.get("rub_per_gen")
        if rub_price is not None:
            try:
                cost_rub = float(rub_price)
                # Allow 0 for FREE models
                if cost_rub >= 0:
                    if cost_rub == 0:
                        logger.info(f"Using SOURCE_OF_TRUTH price for {model_id}: FREE (0 RUB)")
                    else:
                        logger.info(f"Using SOURCE_OF_TRUTH price for {model_id}: {cost_rub} RUB")
                    return cost_rub
            except (TypeError, ValueError):
                logger.warning(f"Invalid SOURCE_OF_TRUTH price for {model_id}: {rub_price}")
    
    # Priority 4: Old registry format (in USD → convert to RUB)
    registry_price_usd = model.get("price")
    if registry_price_usd is not None:
        try:
            price_usd = float(registry_price_usd)
            if price_usd > 0:
                cost_rub = price_usd * USD_TO_RUB
                logger.info(f"Using old registry price for {model_id}: ${price_usd} → {cost_rub} RUB")
                return cost_rub
        except (TypeError, ValueError):
            logger.warning(f"Invalid registry price for {model_id}: {registry_price_usd}")
            pass
    
    # Priority 5: Fallback table (in USD → convert to RUB)
    if model_id in FALLBACK_PRICES_USD:
        price_usd = FALLBACK_PRICES_USD[model_id]
        cost_rub = price_usd * USD_TO_RUB
        logger.info(f"Using fallback price for {model_id}: ${price_usd} → {cost_rub} RUB")
        return cost_rub
    
    # Priority 6: Default (in USD → convert to RUB)
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
    # CRITICAL: Validate input
    if not isinstance(kie_cost_rub, (int, float)):
        logger.error(f"[PRICING] Invalid kie_cost_rub type: {type(kie_cost_rub)}")
        raise ValueError(f"kie_cost_rub must be a number, got {type(kie_cost_rub)}")
    
    if kie_cost_rub < 0:
        logger.error(f"[PRICING] Negative kie_cost_rub: {kie_cost_rub}")
        raise ValueError(f"kie_cost_rub cannot be negative: {kie_cost_rub}")
    
    user_price = kie_cost_rub * MARKUP_MULTIPLIER
    result = round(user_price, 2)
    
    # ASSERT: verify pricing formula
    expected = round(kie_cost_rub * 2, 2)
    if result != expected:
        logger.error(f"[PRICING] Pricing formula violated: {result} != {expected}")
        raise ValueError(f"Pricing formula violated: {result} != {kie_cost_rub} * 2")
    
    return result


def format_price_rub(price: float) -> str:
    """
    Format price for display: '96.00 ₽' or 'Бесплатно'.
    
    Args:
        price: Price in RUB (float)
        
    Returns:
        Formatted price string
    """
    # CRITICAL: Validate input
    if not isinstance(price, (int, float)):
        logger.warning(f"[PRICING] Invalid price type in format_price_rub: {type(price)}")
        return "Ошибка"
    
    if price < 0:
        logger.warning(f"[PRICING] Negative price in format_price_rub: {price}")
        return "Ошибка"
    
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
    
    # CRITICAL: Validate inputs
    if not isinstance(model, dict):
        logger.error(f"[PRICING] Invalid model type in create_charge_metadata: {type(model)}")
        raise ValueError(f"model must be a dict, got {type(model)}")
    
    if not isinstance(user_inputs, dict):
        logger.error(f"[PRICING] Invalid user_inputs type in create_charge_metadata: {type(user_inputs)}")
        raise ValueError(f"user_inputs must be a dict, got {type(user_inputs)}")
    
    try:
        kie_cost = calculate_kie_cost(model, user_inputs, kie_response)
        user_price = calculate_user_price(kie_cost)
        
        # ASSERT: проверка формулы
        expected = round(kie_cost * 2, 2)
        if user_price != expected:
            logger.error(f"[PRICING] Pricing formula violated in create_charge_metadata: {user_price} != {expected}")
            raise ValueError(f"Pricing formula violated: {user_price} != {kie_cost} * 2")
        
        return {
            'kie_cost_rub': kie_cost,
            'user_price_rub': user_price,
            'markup': 'x2',
            'model_id': model.get('model_id', 'unknown'),
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"[PRICING] Error creating charge metadata: {e}", exc_info=True)
        raise
