#!/usr/bin/env python3
"""
Глубокий анализ KIE.ai Market для идеальной интеграции.
Собирает метаданные всех 47 моделей, их modes, pricing, input_schema.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
from dotenv import load_dotenv
from datetime import datetime

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

load_dotenv()

# Настройка логирования
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_all_models_deep() -> List[Dict[str, Any]]:
    """Получает полный список моделей из KIE API с детальной информацией."""
    try:
        from kie_client import get_client
        
        client = get_client()
        models = await client.list_models()
        
        if not models:
            logger.warning("⚠️ API не вернул модели")
            return []
        
        logger.info(f"✅ Получено {len(models)} моделей из API")
        
        # Получаем детальную информацию о каждой модели
        detailed_models = []
        for model in models:
            model_id = model.get('id') or model.get('model_id') or model.get('name', '')
            if not model_id:
                continue
            
            # Получаем детали модели
            model_details = await client.get_model(model_id)
            if model_details:
                detailed_models.append({
                    **model,
                    **model_details
                })
            else:
                detailed_models.append(model)
        
        return detailed_models
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении моделей: {e}", exc_info=True)
        return []


def extract_model_metadata(api_model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Извлекает метаданные модели из ответа API.
    
    Returns:
        Структурированные метаданные модели
    """
    model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
    
    # Определяем provider
    provider = determine_provider(model_id)
    
    # Определяем category
    category = determine_category_from_model(api_model)
    
    # Извлекаем modes
    modes = extract_all_modes(api_model)
    
    # Извлекаем pricing
    pricing_info = extract_pricing_info(api_model)
    
    return {
        "model_id": model_id,
        "title": api_model.get('title') or api_model.get('name') or model_id,
        "provider": provider,
        "description": api_model.get('description') or api_model.get('help') or '',
        "category": category,
        "modes": modes,
        "pricing_info": pricing_info
    }


def determine_provider(model_id: str) -> str:
    """Определяет provider на основе model_id."""
    model_id_lower = model_id.lower()
    
    provider_map = {
        'sora': 'openai',
        'kling': 'kling',
        'wan': 'wan',
        'seedream': 'bytedance',
        'bytedance': 'bytedance',
        'nano': 'google',
        'banana': 'google',
        'gemini': 'google',
        'veo': 'google',
        'flux': 'blackforest',
        'qwen': 'qwen',
        'elevenlabs': 'elevenlabs',
        'hailuo': 'hailuo',
        'topaz': 'topaz',
        'recraft': 'recraft',
        'ideogram': 'ideogram',
        'infinitalk': 'infinitalk',
        'suno': 'suno',
        'midjourney': 'midjourney',
        'runway': 'runway',
        'grok': 'xai',
        'z-image': 'tongyi',
        '4o': 'openai',
        'openai': 'openai'
    }
    
    for key, provider in provider_map.items():
        if key in model_id_lower:
            return provider
    
    return 'unknown'


def determine_category_from_model(api_model: Dict[str, Any]) -> str:
    """Определяет категорию модели."""
    category = api_model.get('category', '').lower()
    model_id = (api_model.get('id') or api_model.get('model_id') or '').lower()
    
    if 'video' in category or 'video' in model_id:
        return 'Video'
    elif 'image' in category or 'image' in model_id or 'photo' in category:
        return 'Image'
    elif 'audio' in category or 'audio' in model_id or 'speech' in model_id or 'music' in model_id:
        return 'Audio'
    elif 'music' in category or 'suno' in model_id:
        return 'Music'
    elif 'edit' in model_id or 'upscale' in model_id or 'remove' in model_id or 'watermark' in model_id:
        return 'Tools'
    else:
        return 'Other'


def extract_all_modes(api_model: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Извлекает все modes из модели.
    KIE API может возвращать model_types или определять по input_schema.
    """
    modes = {}
    
    model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
    
    # Проверяем model_types
    model_types = api_model.get('model_types', [])
    if model_types:
        for model_type in model_types:
            type_id = model_type.get('id') or model_type.get('type_id') or model_type.get('name', '')
            if not type_id:
                continue
            
            generation_type = determine_generation_type(type_id, model_type.get('input_schema', {}))
            
            mode_data = {
                "api_model": model_id,  # Реальный API model string
                "generation_type": generation_type,
                "input_schema": normalize_input_schema(model_type.get('input_schema', {})),
                "pricing": extract_mode_pricing(model_type, api_model),
                "help": model_type.get('description') or model_type.get('help') or api_model.get('description', '')
            }
            
            modes[type_id] = mode_data
    else:
        # Если нет model_types, определяем mode по input_schema
        input_schema = api_model.get('input_schema') or api_model.get('inputSchema') or {}
        generation_type = determine_generation_type(model_id, input_schema)
        
        mode_data = {
            "api_model": model_id,
            "generation_type": generation_type,
            "input_schema": normalize_input_schema(input_schema),
            "pricing": extract_mode_pricing(api_model, api_model),
            "help": api_model.get('description') or api_model.get('help', '')
        }
        
        modes[generation_type] = mode_data
    
    return modes


def determine_generation_type(model_id: str, input_schema: Dict[str, Any]) -> str:
    """Определяет тип генерации."""
    model_id_lower = model_id.lower()
    properties = input_schema.get('properties', {})
    
    # Проверяем по названию модели
    if 'text-to-video' in model_id_lower or 'text_to_video' in model_id_lower:
        return 'text_to_video'
    elif 'image-to-video' in model_id_lower or 'image_to_video' in model_id_lower:
        return 'image_to_video'
    elif 'video-to-video' in model_id_lower or 'video_to_video' in model_id_lower:
        return 'video_to_video'
    elif 'text-to-image' in model_id_lower or 'text_to_image' in model_id_lower:
        return 'text_to_image'
    elif 'image-to-image' in model_id_lower or 'image_to_image' in model_id_lower:
        return 'image_to_image'
    elif 'image-edit' in model_id_lower or 'image_edit' in model_id_lower or 'edit' in model_id_lower:
        return 'image_edit'
    elif 'upscale' in model_id_lower:
        return 'image_upscale'
    elif 'watermark' in model_id_lower or 'remove' in model_id_lower:
        return 'video_edit'
    elif 'speech-to-video' in model_id_lower:
        return 'speech_to_video'
    elif 'text-to-speech' in model_id_lower:
        return 'text_to_speech'
    elif 'speech-to-text' in model_id_lower:
        return 'speech_to_text'
    elif 'text-to-music' in model_id_lower or 'music' in model_id_lower:
        return 'music_generation'
    elif 'audio' in model_id_lower:
        return 'audio_to_audio'
    
    # Проверяем по input_schema
    if 'video_url' in properties:
        return 'video_to_video'
    elif 'image_urls' in properties or 'image_input' in properties or 'image_url' in properties:
        if 'prompt' in properties:
            if 'duration' in properties or 'n_frames' in properties:
                return 'image_to_video'
            else:
                return 'image_to_image'
        else:
            return 'image_upscale'
    elif 'prompt' in properties or 'text' in properties:
        if 'duration' in properties or 'n_frames' in properties:
            return 'text_to_video'
        else:
            return 'text_to_image'
    elif 'audio_url' in properties:
        return 'speech_to_text'
    
    return 'unknown'


def normalize_input_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализует input_schema к стандартному формату."""
    if not schema:
        return {"type": "object", "properties": {}, "required": []}
    
    # Если уже в правильном формате
    if 'type' in schema and schema.get('type') == 'object':
        return schema
    
    # Если старый формат (input_params)
    if 'input_params' in schema:
        properties = {}
        required = []
        
        for param_name, param_data in schema['input_params'].items():
            prop = {
                "type": param_data.get('type', 'string'),
                "description": param_data.get('description', '')
            }
            
            if 'enum' in param_data:
                prop['enum'] = param_data['enum']
            if 'default' in param_data:
                prop['default'] = param_data['default']
            if 'max_length' in param_data:
                prop['maxLength'] = param_data['max_length']
            if 'min' in param_data:
                prop['minimum'] = param_data['min']
            if 'max' in param_data:
                prop['maximum'] = param_data['max']
            if 'min_items' in param_data:
                prop['minItems'] = param_data['min_items']
            if 'max_items' in param_data:
                prop['maxItems'] = param_data['max_items']
            
            properties[param_name] = prop
            
            if param_data.get('required', False):
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    return schema


def extract_pricing_info(api_model: Dict[str, Any]) -> Dict[str, Any]:
    """Извлекает информацию о ценообразовании."""
    pricing = api_model.get('pricing') or api_model.get('pricing_info') or {}
    
    # Пытаемся извлечь credits из разных форматов
    credits = pricing.get('credits') or pricing.get('credit') or api_model.get('credits', 0)
    
    return {
        "credits": float(credits) if credits else 0.0,
        "description": pricing.get('description') or api_model.get('pricing', ''),
        "billing_rules": pricing.get('billing_rules') or {}
    }


def extract_mode_pricing(mode_data: Dict[str, Any], model_data: Dict[str, Any]) -> Dict[str, Any]:
    """Извлекает pricing для конкретного mode."""
    pricing = mode_data.get('pricing') or model_data.get('pricing') or {}
    
    credits = pricing.get('credits') or pricing.get('credit') or 0.0
    
    return {
        "credits": float(credits) if credits else 0.0,
        "credit_to_rub_rate": 0.1,  # Админский курс (настраивается)
        "markup": 2.0  # Маржа x2
    }


async def analyze_all_models() -> Dict[str, Any]:
    """Анализирует все модели и собирает метаданные."""
    logger.info("🔍 Начало глубокого анализа KIE.ai Market...")
    
    # Получаем модели из API
    api_models = await fetch_all_models_deep()
    
    if not api_models:
        logger.warning("⚠️ Не удалось получить модели из API, используем локальные")
        try:
            from kie_models_new import KIE_MODELS
            # Конвертируем локальные модели
            analyzed = {}
            for model_key, model_data in KIE_MODELS.items():
                analyzed[model_key] = extract_model_metadata_from_local(model_key, model_data)
            return {"models": analyzed, "source": "local"}
        except ImportError:
            return {"models": {}, "source": "none", "error": "No models available"}
    
    # Анализируем каждую модель
    analyzed_models = {}
    for api_model in api_models:
        metadata = extract_model_metadata(api_model)
        model_id = metadata["model_id"]
        analyzed_models[model_id] = metadata
    
    return {
        "models": analyzed_models,
        "source": "api",
        "total": len(analyzed_models)
    }


def extract_model_metadata_from_local(model_key: str, model_data: Dict[str, Any]) -> Dict[str, Any]:
    """Извлекает метаданные из локальной структуры."""
    modes = {}
    for mode_id, mode_data_item in model_data.get("modes", {}).items():
        modes[mode_id] = {
            "api_model": mode_data_item.get("model", model_key),
            "generation_type": mode_data_item.get("generation_type", mode_id),
            "input_schema": mode_data_item.get("input_schema", {}),
            "pricing": {
                "credits": 0.0,
                "credit_to_rub_rate": 0.1,
                "markup": 2.0
            },
            "help": mode_data_item.get("help", "")
        }
    
    return {
        "model_id": model_key,
        "title": model_data.get("title", model_key),
        "provider": model_data.get("provider", "unknown"),
        "description": model_data.get("description", ""),
        "category": list(model_data.get("modes", {}).values())[0].get("category", "Other") if model_data.get("modes") else "Other",
        "modes": modes,
        "pricing_info": {
            "credits": 0.0,
            "description": "",
            "billing_rules": {}
        }
    }


def generate_master_catalogue(analyzed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Генерирует master catalogue в единой структуре."""
    catalogue = {}
    
    for model_id, metadata in analyzed_data.get("models", {}).items():
        catalogue[model_id] = {
            "model_id": model_id,
            "title": metadata.get("title", model_id),
            "provider": metadata.get("provider", "unknown"),
            "description": metadata.get("description", ""),
            "category": metadata.get("category", "Other"),
            "modes": {}
        }
        
        # Обрабатываем modes
        for mode_key, mode_data in metadata.get("modes", {}).items():
            catalogue[model_id]["modes"][mode_key] = {
                "api_model": mode_data.get("api_model", model_id),
                "generation_type": mode_data.get("generation_type", mode_key),
                "input_schema": mode_data.get("input_schema", {}),
                "pricing": mode_data.get("pricing", {
                    "credits": 0.0,
                    "credit_to_rub_rate": 0.1,
                    "markup": 2.0
                }),
                "help": mode_data.get("help", "")
            }
    
    return catalogue


def save_master_catalogue(catalogue: Dict[str, Any], filename: str = "master_catalogue.json"):
    """Сохраняет master catalogue в файл."""
    filepath = root_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(catalogue, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Master catalogue сохранен в {filepath}")


def generate_analysis_report(analyzed_data: Dict[str, Any], catalogue: Dict[str, Any]) -> Dict[str, Any]:
    """Генерирует детальный отчёт анализа."""
    total_models = len(catalogue)
    total_modes = sum(len(m.get("modes", {})) for m in catalogue.values())
    
    missing_schemas = []
    invalid_schemas = []
    
    for model_id, model_data in catalogue.items():
        for mode_key, mode_data_item in model_data.get("modes", {}).items():
            input_schema = mode_data_item.get("input_schema", {})
            
            if not input_schema:
                missing_schemas.append(f"{model_id}:{mode_key}")
            elif not isinstance(input_schema, dict):
                invalid_schemas.append(f"{model_id}:{mode_key} - не словарь")
            elif "properties" not in input_schema:
                invalid_schemas.append(f"{model_id}:{mode_key} - нет properties")
    
    return {
        "total_models_found": total_models,
        "total_modes_processed": total_modes,
        "missing_models": [],
        "missing_modes": {},
        "missing_input_schemas": missing_schemas,
        "invalid_input_schemas": invalid_schemas,
        "pricing_issues": [],
        "test_results": "PENDING",
        "api_errors": []
    }


async def main():
    """Основная функция глубокого анализа."""
    logger.info("🚀 Начало глубокого анализа KIE.ai Market...")
    
    # Анализируем все модели
    analyzed_data = await analyze_all_models()
    
    # Генерируем master catalogue
    catalogue = generate_master_catalogue(analyzed_data)
    
    # Сохраняем catalogue
    save_master_catalogue(catalogue)
    
    # Генерируем отчёт
    report = generate_analysis_report(analyzed_data, catalogue)
    
    # Выводим отчёт
    print("\n" + "="*80)
    print("📊 ОТЧЁТ ГЛУБОКОГО АНАЛИЗА KIE.AI MARKET")
    print("="*80)
    
    print(f"\n📋 СТАТИСТИКА:")
    print(f"  Total models found: {report['total_models_found']}")
    print(f"  Total modes processed: {report['total_modes_processed']}")
    print(f"  Source: {analyzed_data.get('source', 'unknown')}")
    
    if report['missing_input_schemas']:
        print(f"\n❌ ОТСУТСТВУЮЩИЕ INPUT_SCHEMA ({len(report['missing_input_schemas'])}):")
        for missing in report['missing_input_schemas'][:20]:
            print(f"  - {missing}")
        if len(report['missing_input_schemas']) > 20:
            print(f"  ... и еще {len(report['missing_input_schemas']) - 20}")
    
    if report['invalid_input_schemas']:
        print(f"\n⚠️ НЕКОРРЕКТНЫЕ INPUT_SCHEMA ({len(report['invalid_input_schemas'])}):")
        for invalid in report['invalid_input_schemas'][:20]:
            print(f"  - {invalid}")
        if len(report['invalid_input_schemas']) > 20:
            print(f"  ... и еще {len(report['invalid_input_schemas']) - 20}")
    
    print("\n" + "="*80)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

