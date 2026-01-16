"""
KIE AI Models Catalog - загрузка и кеширование каталога моделей.
"""

import yaml
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from functools import lru_cache

logger = logging.getLogger(__name__)

# Глобальный кеш
_catalog_cache: Optional[List['ModelSpec']] = None


@dataclass
class ModelMode:
    """Режим генерации модели."""
    unit: str  # image, video, second, minute, 1000_chars, request, megapixel, removal, upscale
    credits: float
    official_usd: float
    notes: Optional[str] = None


@dataclass
class ModelSpec:
    """Спецификация модели."""
    id: str  # model_id для KIE API
    title_ru: str  # Название для пользователя
    type: str  # t2i, i2i, t2v, i2v, v2v, tts, stt, sfx, audio_isolation, upscale, bg_remove, watermark_remove, music, lip_sync
    modes: List[ModelMode] = field(default_factory=list)


def _load_yaml_catalog() -> List[Dict[str, Any]]:
    """Загружает YAML каталог."""
    root_dir = Path(__file__).parent.parent.parent
    catalog_file = root_dir / "app" / "kie_catalog" / "models_pricing.yaml"
    
    if not catalog_file.exists():
        logger.error(f"Catalog file not found: {catalog_file}")
        return []
    
    try:
        with open(catalog_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict) or 'models' not in data:
            logger.error("Invalid catalog format: missing 'models' key")
            return []
        
        return data['models']
    except Exception as e:
        logger.error(f"Error loading catalog: {e}", exc_info=True)
        return []


def _parse_model_spec(model_data: Dict[str, Any]) -> ModelSpec:
    """Парсит данные модели в ModelSpec."""
    modes = []
    for mode_data in model_data.get('modes', []):
        mode = ModelMode(
            unit=mode_data.get('unit', 'image'),
            credits=float(mode_data.get('credits', 0.0)),
            official_usd=float(mode_data.get('official_usd', 0.0)),
            notes=mode_data.get('notes')
        )
        modes.append(mode)
    
    return ModelSpec(
        id=model_data.get('id', ''),
        title_ru=model_data.get('title_ru', ''),
        type=model_data.get('type', 't2i'),
        modes=modes
    )


def load_catalog(force_reload: bool = False) -> List[ModelSpec]:
    """
    Загружает каталог моделей.
    
    Args:
        force_reload: Если True, принудительно перезагружает каталог
    
    Returns:
        Список ModelSpec
    """
    global _catalog_cache
    
    if _catalog_cache is not None and not force_reload:
        return _catalog_cache
    
    logger.info("Loading KIE models catalog...")
    raw_models = _load_yaml_catalog()
    
    models = []
    for model_data in raw_models:
        try:
            model_spec = _parse_model_spec(model_data)
            if model_spec.id:
                models.append(model_spec)
        except Exception as e:
            logger.warning(f"Error parsing model {model_data.get('id', 'unknown')}: {e}")
            continue
    
    _catalog_cache = models
    logger.info(f"Loaded {len(models)} models from catalog")
    
    # Проверяем каталог при загрузке (только предупреждения, не останавливаем)
    try:
        _verify_catalog_internal(models)
    except Exception as e:
        logger.warning(f"Catalog verification warning: {e}")
    
    return models


def _verify_catalog_internal(models: List[ModelSpec]) -> None:
    """
    Внутренняя проверка каталога (только логирование, не останавливает работу).
    
    Args:
        models: Список моделей для проверки
    """
    from collections import Counter
    
    # Проверяем дубли model_id
    model_ids = [m.id for m in models]
    duplicates = [model_id for model_id, count in Counter(model_ids).items() if count > 1]
    if duplicates:
        logger.warning(f"Catalog warning: duplicate model_ids found: {duplicates}")
    
    # Проверяем что все official_usd > 0
    invalid_prices = []
    for model in models:
        for mode in model.modes:
            if mode.official_usd <= 0:
                invalid_prices.append(f"{model.id} mode {mode.notes or 'default'}")
    if invalid_prices:
        logger.warning(f"Catalog warning: models with official_usd <= 0: {invalid_prices[:5]}")
    
    # Проверяем типы
    allowed_types = {'t2i', 'i2i', 't2v', 'i2v', 'v2v', 'tts', 'stt', 'sfx', 'audio_isolation', 
                     'upscale', 'bg_remove', 'watermark_remove', 'music', 'lip_sync'}
    invalid_types = [m.id for m in models if m.type not in allowed_types]
    if invalid_types:
        logger.warning(f"Catalog warning: models with invalid types: {invalid_types[:5]}")


def get_model(model_id: str) -> Optional[ModelSpec]:
    """
    Получает модель по ID.
    
    Args:
        model_id: ID модели
    
    Returns:
        ModelSpec или None
    """
    catalog = load_catalog()
    for model in catalog:
        if model.id == model_id:
            return model
    return None


def list_models() -> List[ModelSpec]:
    """
    Возвращает список всех моделей.
    
    Returns:
        Список всех ModelSpec
    """
    return load_catalog()


def reset_catalog_cache():
    """Сбрасывает кеш каталога (для тестов)."""
    global _catalog_cache
    _catalog_cache = None
    logger.debug("Catalog cache reset")

