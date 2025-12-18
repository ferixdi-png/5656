#!/usr/bin/env python3
"""
Сбор канонического списка всех 47 моделей KIE.ai Market + все modes.
Собирает данные с API и сохраняет в data/kie_market_catalog.json
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_all_models_from_api() -> List[Dict[str, Any]]:
    """Получает все модели из KIE API."""
    try:
        from kie_client import get_client
        
        client = get_client()
        models = await client.list_models()
        
        if not models:
            logger.error("❌ Не удалось получить модели из API")
            return []
        
        logger.info(f"✅ Получено {len(models)} моделей из API")
        return models
    
    except Exception as e:
        logger.error(f"❌ Ошибка при получении моделей: {e}", exc_info=True)
        return []


def extract_model_types_and_modes(api_model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Извлекает данные о модели и её modes из API ответа.
    
    Структура API модели:
    {
        "id": "model_id",
        "title": "...",
        "provider": "...",
        "description": "...",
        "category": "...",
        "modelTypes": [
            {
                "id": "mode_id",
                "title": "...",
                "apiModel": "provider/model-id",
                "inputSchema": {...},
                "pricing": {...}
            }
        ]
    }
    """
    model_id = api_model.get("id", "")
    title = api_model.get("title", "")
    provider = api_model.get("provider", "")
    description = api_model.get("description", "")
    category = api_model.get("category", "Unknown")
    
    # Извлекаем modes из modelTypes
    modes = {}
    model_types = api_model.get("modelTypes", [])
    
    for model_type in model_types:
        mode_id = model_type.get("id", "")
        mode_title = model_type.get("title", "")
        api_model_str = model_type.get("apiModel", "")
        input_schema = model_type.get("inputSchema", {})
        pricing = model_type.get("pricing", {})
        help_text = model_type.get("help", description)
        
        if not mode_id:
            # Если нет mode_id, используем apiModel как ключ
            mode_id = api_model_str.replace("/", "_") if api_model_str else f"mode_{len(modes)}"
        
        # Определяем generation_type из названия mode
        generation_type = mode_title.lower().replace(" ", "_")
        
        modes[mode_id] = {
            "api_model": api_model_str,
            "generation_type": generation_type,
            "title": mode_title,
            "input_schema": input_schema,
            "help": help_text,
            "pricing": pricing
        }
    
    # Если нет modes, создаём один default mode
    if not modes:
        api_model_str = api_model.get("apiModel", model_id)
        modes["default"] = {
            "api_model": api_model_str,
            "generation_type": "unknown",
            "title": title,
            "input_schema": api_model.get("inputSchema", {}),
            "help": description,
            "pricing": api_model.get("pricing", {})
        }
    
    return {
        "model_id": model_id,
        "title": title,
        "provider": provider,
        "description": description,
        "category": category,
        "modes": modes
    }


async def build_canonical_catalog() -> Dict[str, Any]:
    """Строит канонический каталог всех моделей."""
    logger.info("📡 Получение всех моделей из KIE API...")
    
    api_models = await fetch_all_models_from_api()
    
    if not api_models:
        logger.error("❌ Не удалось получить модели")
        return {}
    
    catalog = {}
    total_modes = 0
    
    for api_model in api_models:
        model_data = extract_model_types_and_modes(api_model)
        model_id = model_data["model_id"]
        
        catalog[model_id] = {
            "title": model_data["title"],
            "provider": model_data["provider"],
            "description": model_data["description"],
            "category": model_data["category"],
            "modes": model_data["modes"]
        }
        
        total_modes += len(model_data["modes"])
    
    logger.info(f"✅ Обработано моделей: {len(catalog)}")
    logger.info(f"✅ Всего modes: {total_modes}")
    
    return catalog


async def main():
    """Основная функция."""
    logger.info("🚀 Начало сбора канонического каталога KIE.ai Market...")
    
    # Создаём директорию data если её нет
    data_dir = root_dir / "data"
    data_dir.mkdir(exist_ok=True)
    
    # Собираем каталог
    catalog = await build_canonical_catalog()
    
    if not catalog:
        logger.error("❌ Не удалось собрать каталог")
        return 1
    
    # Сохраняем в JSON
    catalog_file = data_dir / "kie_market_catalog.json"
    catalog_data = {
        "timestamp": None,  # Будет установлено при сохранении
        "total_models": len(catalog),
        "total_modes": sum(len(m.get("modes", {})) for m in catalog.values()),
        "catalog": catalog
    }
    
    from datetime import datetime, timezone
    catalog_data["timestamp"] = datetime.now(timezone.utc).astimezone().isoformat()
    
    with open(catalog_file, 'w', encoding='utf-8') as f:
        json.dump(catalog_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Каталог сохранён в {catalog_file}")
    
    # Выводим статистику
    print("\n" + "="*80)
    print("📊 КАТАЛОГ СОБРАН")
    print("="*80)
    print(f"Всего моделей: {catalog_data['total_models']}")
    print(f"Всего modes: {catalog_data['total_modes']}")
    print(f"Файл: {catalog_file}")
    print("="*80)
    
    # Проверяем, что моделей 47
    if catalog_data['total_models'] != 47:
        logger.warning(f"⚠️ Ожидалось 47 моделей, получено {catalog_data['total_models']}")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

