"""
Enforcer для моделей - блокирует использование моделей не из registry.

Единый источник правды: ТОЛЬКО модели из registry (построенного из документации).
"""

import logging
from typing import Optional

from app.kie.spec_registry import get_registry

logger = logging.getLogger(__name__)


def enforce_model_from_registry(model_id: str) -> tuple[bool, Optional[str]]:
    """
    Проверяет что модель есть в registry.
    
    Args:
        model_id: ID модели для проверки
    
    Returns:
        (is_valid, error_message)
        - is_valid=True если модель найдена в registry
        - is_valid=False если модель НЕ найдена, error_message содержит описание ошибки
    """
    registry = get_registry()
    
    if not registry.has_model(model_id):
        error_msg = (
            f"Model '{model_id}' is not in registry. "
            f"Only models from documentation (docs/*_INTEGRATION.md) are allowed. "
            f"Total models in registry: {registry.count()}"
        )
        logger.error(f"[ENFORCER] {error_msg}")
        return False, error_msg
    
    return True, None


def get_model_or_fail(model_id: str):
    """
    Получает модель из registry или выбрасывает исключение.
    
    Args:
        model_id: ID модели
    
    Returns:
        ModelSpecFromRegistry
    
    Raises:
        ValueError: если модель не найдена в registry
    """
    registry = get_registry()
    
    model_spec = registry.get_model(model_id)
    if not model_spec:
        available_models = ", ".join(registry.list_models()[:10])
        raise ValueError(
            f"Model '{model_id}' not found in registry. "
            f"Available models (first 10): {available_models}... "
            f"Total: {registry.count()}"
        )
    
    return model_spec
















