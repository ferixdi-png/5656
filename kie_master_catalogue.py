"""
Master Catalogue для всех моделей KIE.ai Market.
Единая структура данных для всех 47 моделей и их modes.
"""

# Master Catalogue Structure
# {
#   "model_id": {
#     "model_id": "string",
#     "title": "string",
#     "provider": "string",
#     "description": "string",
#     "category": "Image|Video|Audio|Music|Tools",
#     "modes": {
#       "<mode_key>": {
#         "api_model": "string",
#         "generation_type": "text_to_image | text_to_video | ...",
#         "input_schema": {...},
#         "pricing": {
#           "credits": number,
#           "credit_to_rub_rate": number,
#           "markup": 2
#         },
#         "help": "string"
#       }
#     }
#   }
# }

KIE_MASTER_CATALOGUE = {}

# Функции для работы с catalogue

def load_master_catalogue() -> dict:
    """Загружает master catalogue из файла или возвращает пустой."""
    try:
        import json
        catalogue_path = Path(__file__).parent / "master_catalogue.json"
        if catalogue_path.exists():
            with open(catalogue_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить master catalogue: {e}")
    
    return {}


def get_model_by_id(model_id: str) -> Optional[dict]:
    """Получает модель по ID."""
    catalogue = load_master_catalogue()
    return catalogue.get(model_id)


def get_mode_by_model_and_mode(model_id: str, mode_key: str) -> Optional[dict]:
    """Получает mode по model_id и mode_key."""
    model = get_model_by_id(model_id)
    if not model:
        return None
    return model.get("modes", {}).get(mode_key)


def get_all_models() -> dict:
    """Возвращает все модели."""
    return load_master_catalogue()


def get_models_by_category(category: str) -> dict:
    """Получает модели по категории."""
    catalogue = load_master_catalogue()
    return {
        model_id: model_data
        for model_id, model_data in catalogue.items()
        if model_data.get("category") == category
    }


def get_all_modes() -> List[dict]:
    """Возвращает список всех modes."""
    catalogue = load_master_catalogue()
    modes = []
    
    for model_id, model_data in catalogue.items():
        for mode_key, mode_data_item in model_data.get("modes", {}).items():
            modes.append({
                "model_id": model_id,
                "mode_key": mode_key,
                "api_model": mode_data_item.get("api_model"),
                "generation_type": mode_data_item.get("generation_type"),
                "category": model_data.get("category")
            })
    
    return modes


def count_models_and_modes() -> dict:
    """Подсчитывает количество моделей и modes."""
    catalogue = load_master_catalogue()
    total_models = len(catalogue)
    total_modes = sum(len(m.get("modes", {})) for m in catalogue.values())
    
    return {
        "models": total_models,
        "modes": total_modes
    }


# Инициализация при импорте
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Загружаем catalogue при импорте (будет загружен при первом вызове)
KIE_MASTER_CATALOGUE = {}

