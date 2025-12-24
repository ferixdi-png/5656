"""
Free models management - automatic TOP-5 cheapest selection.

RULES:
1. Free models = 5 cheapest models by base cost
2. Selection is AUTOMATIC based on pricing
3. NO manual hardcoding of free model IDs
4. Re-calculated on every source_of_truth update
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

SOURCE_OF_TRUTH = Path("models/kie_source_of_truth.json")
SOURCE_OF_TRUTH_FALLBACK = Path("models/kie_models_final_truth.json")


def get_free_models() -> List[str]:
    """
    Get list of model_ids that are free to use.
    
    Returns TOP-5 cheapest models by RUB price.
    
    Returns:
        List of model_ids (tech IDs)
    """
    # Try new file first, fallback to old
    source_path = SOURCE_OF_TRUTH if SOURCE_OF_TRUTH.exists() else SOURCE_OF_TRUTH_FALLBACK
    
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models = data.get("models", [])
        
        if not models:
            logger.warning("No models in source of truth")
            return []
        
        # Filter enabled models only
        enabled_models = [m for m in models if m.get("enabled", True)]
        
        if not enabled_models:
            logger.warning("No enabled models found")
            return []
        
        # Sort by RUB price (cheapest first)
        sorted_models = sorted(
            enabled_models,
            key=lambda m: m.get("pricing", {}).get("rub_per_use", float('inf'))
        )
        
        # Take TOP-5
        free_models = sorted_models[:5]
        free_model_ids = [m["model_id"] for m in free_models]
        
        logger.info(f"Free models (TOP-5 cheapest): {free_model_ids}")
        for m in free_models:
            price = m.get("pricing", {}).get("rub_per_use", 0)
            logger.info(f"  - {m['model_id']}: {price} RUB")
        
        return free_model_ids
    
    except FileNotFoundError:
        logger.error(f"Source of truth not found: {SOURCE_OF_TRUTH}")
        return []
    except Exception as e:
        logger.error(f"Failed to load free models: {e}", exc_info=True)
        return []


def is_free_model(model_id: str) -> bool:
    """
    Check if model is free.
    
    Args:
        model_id: Tech model ID
    
    Returns:
        True if model is in TOP-5 cheapest
    """
    free_ids = get_free_models()
    return model_id in free_ids


def get_model_price(model_id: str) -> Dict[str, float]:
    """
    Get pricing for specific model.
    
    Args:
        model_id: Tech model ID
    
    Returns:
        {
            "usd_per_use": float,
            "credits_per_use": float,
            "rub_per_use": float,
            "is_free": bool
        }
    """
    try:
        with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models = data.get("models", [])
        
        # Find model
        model = next((m for m in models if m["model_id"] == model_id), None)
        
        if not model:
            logger.warning(f"Model not found: {model_id}")
            return {
                "usd_per_use": 0.0,
                "credits_per_use": 0.0,
                "rub_per_use": 0.0,
                "is_free": False
            }
        
        pricing = model.get("pricing", {})
        is_free = is_free_model(model_id)
        
        return {
            "usd_per_use": pricing.get("usd_per_use", 0.0),
            "credits_per_use": pricing.get("credits_per_use", 0.0),
            "rub_per_use": pricing.get("rub_per_use", 0.0),
            "is_free": is_free
        }
    
    except Exception as e:
        logger.error(f"Failed to get price for {model_id}: {e}")
        return {
            "usd_per_use": 0.0,
            "credits_per_use": 0.0,
            "rub_per_use": 0.0,
            "is_free": False
        }


def get_all_models_by_category() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all models grouped by category.
    
    Returns:
        {
            "category_name": [
                {
                    "model_id": str,
                    "display_name": str,
                    "price_rub": float,
                    "is_free": bool
                },
                ...
            ],
            ...
        }
    """
    try:
        with open(SOURCE_OF_TRUTH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models = data.get("models", [])
        free_ids = get_free_models()
        
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        
        for model in models:
            if not model.get("enabled", True):
                continue
            
            category = model.get("category", "other")
            
            if category not in by_category:
                by_category[category] = []
            
            by_category[category].append({
                "model_id": model["model_id"],
                "display_name": model.get("display_name", model["model_id"]),
                "price_rub": model.get("pricing", {}).get("rub_per_use", 0.0),
                "is_free": model["model_id"] in free_ids,
                "description": model.get("description", "")
            })
        
        # Sort each category by price
        for category in by_category:
            by_category[category].sort(key=lambda m: m["price_rub"])
        
        return by_category
    
    except Exception as e:
        logger.error(f"Failed to get models by category: {e}")
        return {}


def calculate_cost(model_id: str, quantity: int = 1) -> Dict[str, Any]:
    """
    Calculate cost for running model N times.
    
    Args:
        model_id: Tech model ID
        quantity: Number of runs (default: 1)
    
    Returns:
        {
            "model_id": str,
            "quantity": int,
            "price_per_use_rub": float,
            "total_rub": float,
            "is_free": bool
        }
    """
    pricing = get_model_price(model_id)
    
    price_per_use = pricing["rub_per_use"]
    is_free = pricing["is_free"]
    
    # Free models cost nothing
    if is_free:
        total = 0.0
    else:
        total = price_per_use * quantity
    
    return {
        "model_id": model_id,
        "quantity": quantity,
        "price_per_use_rub": price_per_use,
        "total_rub": round(total, 2),
        "is_free": is_free
    }
