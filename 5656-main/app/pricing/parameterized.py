"""
Parameterized pricing engine - integrates pricing/KIE_PRICING_RUB.json

This module implements the parameterized pricing system where prices depend on
selected parameters (duration, resolution, audio, quality, mode, aspect_ratio, I/O type).

Priority order for fallback:
1. duration → resolution → audio → quality → mode → aspect_ratio
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)

# Path to pricing JSON
PRICING_JSON_PATH = Path(__file__).parent.parent.parent / "pricing" / "KIE_PRICING_RUB.json"

# Fallback priority order
FALLBACK_PRIORITY = [
    "duration",
    "resolution", 
    "audio",
    "quality",
    "mode",
    "aspect_ratio"
]


class ParameterizedPricing:
    """Parameterized pricing engine."""
    
    def __init__(self, pricing_path: Optional[Path] = None):
        """Initialize pricing engine."""
        self.pricing_path = pricing_path or PRICING_JSON_PATH
        self._pricing_data: Optional[Dict[str, Any]] = None
        self._load_pricing()
    
    def _load_pricing(self) -> None:
        """Load pricing data from JSON."""
        try:
            if not self.pricing_path.exists():
                logger.warning(f"Pricing file not found: {self.pricing_path}")
                self._pricing_data = {"models": {}}
                return
            
            # Use sync file I/O (called from __init__, not async context)
            # This is acceptable as it's only called once during initialization
            with open(self.pricing_path, 'r', encoding='utf-8') as f:
                self._pricing_data = json.load(f)
            
            logger.info(f"Loaded pricing for {len(self._pricing_data.get('models', {}))} models")
        except Exception as e:
            logger.error(f"Failed to load pricing: {e}", exc_info=True)
            self._pricing_data = {"models": {}}
    
    def get_price(
        self,
        model_id: str,
        params: Dict[str, Any],
        io_type: Optional[str] = None
    ) -> Optional[Decimal]:
        """
        Get price for model with given parameters.
        
        Args:
            model_id: Model identifier (e.g., "bytedance/seedance-1.5-pro")
            params: User-selected parameters (duration, resolution, audio, etc.)
            io_type: I/O type (text-to-image, image-to-image, text-to-video, etc.)
            
        Returns:
            Price in RUB (Decimal) or None if not found
        """
        # CRITICAL: Validate inputs
        if not model_id or not isinstance(model_id, str):
            logger.warning(f"[PRICING] Invalid model_id: {model_id} (must be non-empty string)")
            return None
        
        if not isinstance(params, dict):
            logger.warning(f"[PRICING] Invalid params: {params} (must be dict)")
            return None
        
        if not self._pricing_data:
            logger.debug("[PRICING] Pricing data not loaded")
            return None
        
        models = self._pricing_data.get("models", {})
        if model_id not in models:
            logger.debug(f"[PRICING] Model {model_id} not in pricing data")
            return None
        
        model_pricing = models[model_id]
        variants = model_pricing.get("variants", [])
        
        if not variants:
            logger.debug(f"No pricing variants for {model_id}")
            return None
        
        # Normalize parameters
        normalized_params = self._normalize_params(params, io_type)
        
        # Try exact match first
        for variant in variants:
            variant_params = variant.get("params", {})
            if self._params_match(normalized_params, variant_params):
                price = variant.get("price_rub")
                if price is not None:
                    logger.debug(f"Exact match for {model_id}: {normalized_params} → {price} RUB")
                    return Decimal(str(price))
        
        # Try fallback (nearest match)
        fallback_price = self._find_fallback_price(variants, normalized_params)
        if fallback_price is not None:
            logger.debug(f"Fallback match for {model_id}: {normalized_params} → {fallback_price} RUB")
            return Decimal(str(fallback_price))
        
        logger.warning(f"No price found for {model_id} with params {normalized_params}")
        return None
    
    def _normalize_params(self, params: Dict[str, Any], io_type: Optional[str] = None) -> Dict[str, str]:
        """Normalize parameters to match pricing JSON format."""
        normalized = {}
        
        # I/O type
        if io_type:
            normalized["io_type"] = io_type
        elif "io_type" in params:
            normalized["io_type"] = str(params["io_type"])
        
        # Duration (convert to string with 's' suffix)
        if "duration" in params:
            duration = params["duration"]
            if isinstance(duration, (int, float)):
                normalized["duration"] = f"{int(duration)}s"
            else:
                normalized["duration"] = str(duration)
        
        # Resolution
        if "resolution" in params:
            normalized["resolution"] = str(params["resolution"]).upper()
        
        # Audio
        if "audio" in params:
            audio = params["audio"]
            if isinstance(audio, bool):
                normalized["audio"] = "WITH" if audio else "NO"
            else:
                normalized["audio"] = str(audio).upper()
        
        # Quality
        if "quality" in params:
            normalized["quality"] = str(params["quality"]).upper()
        
        # Mode
        if "mode" in params:
            normalized["mode"] = str(params["mode"]).upper()
        
        # Aspect ratio
        if "aspect_ratio" in params:
            normalized["aspect_ratio"] = str(params["aspect_ratio"])
        
        return normalized
    
    def _params_match(self, params1: Dict[str, str], params2: Dict[str, str]) -> bool:
        """
        Check if two parameter sets match exactly.
        
        Args:
            params1: First parameter set
            params2: Second parameter set
            
        Returns:
            True if all keys in params1 match params2, False otherwise
        """
        # CRITICAL: Validate inputs
        if not isinstance(params1, dict) or not isinstance(params2, dict):
            logger.warning(f"[PRICING] Invalid params type in _params_match: params1={type(params1)}, params2={type(params2)}")
            return False
        
        # Check all keys in params1 are in params2 with same values
        for key, value in params1.items():
            if key not in params2:
                return False
            if str(params2[key]).upper() != str(value).upper():
                return False
        return True
    
    def _find_fallback_price(
        self,
        variants: List[Dict[str, Any]],
        target_params: Dict[str, str]
    ) -> Optional[float]:
        """
        Find nearest price variant using fallback priority.
        
        Priority: duration → resolution → audio → quality → mode → aspect_ratio
        
        Args:
            variants: List of price variants
            target_params: Target parameters to match
            
        Returns:
            Price in RUB or None if no match found
        """
        # CRITICAL: Validate inputs
        if not isinstance(variants, list):
            logger.warning(f"[PRICING] Invalid variants type in _find_fallback_price: {type(variants)}")
            return None
        
        if not isinstance(target_params, dict):
            logger.warning(f"[PRICING] Invalid target_params type in _find_fallback_price: {type(target_params)}")
            return None
        
        best_match = None
        best_score = 0
        
        for variant in variants:
            if not isinstance(variant, dict):
                logger.warning(f"[PRICING] Invalid variant type in _find_fallback_price: {type(variant)}")
                continue
            
            variant_params = variant.get("params", {})
            if not isinstance(variant_params, dict):
                logger.warning(f"[PRICING] Invalid variant_params type: {type(variant_params)}")
                continue
            
            score = self._calculate_match_score(target_params, variant_params)
            
            if score > best_score:
                best_score = score
                best_match = variant
        
        if best_match and best_score > 0:
            price = best_match.get("price_rub")
            if price is not None:
                logger.debug(f"[PRICING] Fallback match found: score={best_score}, price={price} RUB")
                return float(price)
            else:
                logger.warning(f"[PRICING] Best match variant has no price_rub: {best_match}")
        
        logger.debug(f"[PRICING] No fallback match found: best_score={best_score}")
        return None
    
    def _calculate_match_score(
        self,
        target: Dict[str, str],
        candidate: Dict[str, str]
    ) -> int:
        """Calculate match score based on fallback priority."""
        score = 0
        priority_weight = len(FALLBACK_PRIORITY)
        
        for i, key in enumerate(FALLBACK_PRIORITY):
            if key in target and key in candidate:
                if str(target[key]).upper() == str(candidate[key]).upper():
                    # Higher priority = higher weight
                    score += (priority_weight - i) * 10
        
        # I/O type must match (critical)
        if "io_type" in target and "io_type" in candidate:
            if str(target["io_type"]).upper() == str(candidate["io_type"]).upper():
                score += 100  # High weight for I/O type
            else:
                return 0  # I/O type mismatch = no match
        
        return score
    
    def format_price_display(
        self,
        model_id: str,
        params: Dict[str, Any],
        io_type: Optional[str] = None
    ) -> str:
        """
        Format price display string for user.
        
        Returns:
            Formatted string: "Модель: ... | Параметры: ... | Цена: ... ₽"
        """
        # CRITICAL: Validate inputs
        if not model_id or not isinstance(model_id, str):
            logger.warning(f"[PRICING] Invalid model_id in format_price_display: {model_id}")
            return "Ошибка: неверный идентификатор модели"
        
        if not isinstance(params, dict):
            logger.warning(f"[PRICING] Invalid params in format_price_display: {params}")
            return "Ошибка: неверные параметры"
        
        try:
            price = self.get_price(model_id, params, io_type)
            
            if price is None:
                # Try to get model name for better error message
                model_name = self._pricing_data.get("models", {}).get(model_id, {}).get("model_name", model_id)
                return f"Для модели {model_name} и выбранных параметров цена не задана, выберите другой вариант"
            
            # Format parameters
            param_parts = []
            for key in ["duration", "resolution", "audio", "quality", "mode", "aspect_ratio"]:
                if key in params and params[key] is not None:
                    param_parts.append(f"{key}={params[key]}")
            
            params_str = ", ".join(param_parts) if param_parts else "по умолчанию"
            
            # Get model name for display
            model_name = self._pricing_data.get("models", {}).get(model_id, {}).get("model_name", model_id)
            
            return f"Модель: {model_name} | Параметры: {params_str} | Цена: {price} ₽"
        except Exception as e:
            logger.error(f"[PRICING] Error formatting price display for {model_id}: {e}", exc_info=True)
            return f"Ошибка при расчете цены для модели {model_id}"


# Global instance
_pricing_engine: Optional[ParameterizedPricing] = None


def get_pricing_engine() -> ParameterizedPricing:
    """Get global pricing engine instance."""
    global _pricing_engine
    if _pricing_engine is None:
        _pricing_engine = ParameterizedPricing()
    return _pricing_engine


def calculate_price_rub(
    model_id: str,
    params: Dict[str, Any],
    io_type: Optional[str] = None
) -> Optional[Decimal]:
    """
    Calculate price in RUB for model with parameters.
    
    This is the main entry point for parameterized pricing.
    
    Returns:
        Price in RUB (Decimal) or None if not found/error
    """
    # CRITICAL: Validate inputs
    if not model_id or not isinstance(model_id, str):
        logger.warning(f"[PRICING] Invalid model_id in calculate_price_rub: {model_id}")
        return None
    
    if not isinstance(params, dict):
        logger.warning(f"[PRICING] Invalid params in calculate_price_rub: {params}")
        return None
    
    try:
        engine = get_pricing_engine()
        price = engine.get_price(model_id, params, io_type)
        
        if price is None:
            logger.debug(f"[PRICING] No price found for {model_id} with params {params}")
        
        return price
    except Exception as e:
        logger.error(f"[PRICING] Error calculating price for {model_id}: {e}", exc_info=True)
        return None  # Fail-safe: return None on error

