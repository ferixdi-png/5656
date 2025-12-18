#!/usr/bin/env python3
"""
Полная проверка и интеграция всех 47 моделей с KIE.ai Market.
Автоматически получает, проверяет и интегрирует все модели.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
from dotenv import load_dotenv
from datetime import datetime, timezone, timezone

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_all_47_models() -> List[Dict[str, Any]]:
    """Получает все 47 моделей из KIE API."""
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
        for i, model in enumerate(models, 1):
            model_id = model.get('id') or model.get('model_id') or model.get('name', '')
            if not model_id:
                continue
            
            logger.info(f"📋 [{i}/{len(models)}] Получение деталей для {model_id}...")
            
            # Получаем детали модели
            model_details = await client.get_model(model_id)
            if model_details:
                detailed_models.append({
                    **model,
                    **model_details
                })
            else:
                detailed_models.append(model)
            
            # Небольшая задержка чтобы не перегружать API
            await asyncio.sleep(0.1)
        
        return detailed_models
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении моделей: {e}", exc_info=True)
        return []


def extract_model_types_and_modes(api_model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Извлекает все Model Types и modes из модели API.
    
    Returns:
        {
            "model_id": "...",
            "title": "...",
            "provider": "...",
            "category": "...",
            "modes": {
                "mode_key": {
                    "api_model": "...",
                    "generation_type": "...",
                    "input_schema": {...},
                    "help": "..."
                }
            }
        }
    """
    model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
    
    # Определяем provider
    provider = determine_provider(model_id)
    
    # Определяем category
    category = determine_category_from_model(api_model)
    
    # Извлекаем modes из model_types
    modes = {}
    model_types = api_model.get('model_types', [])
    
    if model_types:
        for model_type in model_types:
            type_id = model_type.get('id') or model_type.get('type_id') or model_type.get('name', '')
            if not type_id:
                continue
            
            type_schema = model_type.get('input_schema') or model_type.get('inputSchema') or {}
            generation_type = determine_generation_type(type_id, type_schema)
            
            mode_data = {
                "api_model": model_id,  # Реальный API model string
                "generation_type": generation_type,
                "input_schema": normalize_input_schema(type_schema),
                "help": model_type.get('description') or model_type.get('help') or api_model.get('description', '')
            }
            
            modes[type_id] = mode_data
    else:
        # Если нет model_types, создаём один mode
        input_schema = api_model.get('input_schema') or api_model.get('inputSchema') or {}
        generation_type = determine_generation_type(model_id, input_schema)
        
        mode_data = {
            "api_model": model_id,
            "generation_type": generation_type,
            "input_schema": normalize_input_schema(input_schema),
            "help": api_model.get('description') or api_model.get('help', '')
        }
        
        modes[generation_type] = mode_data
    
    return {
        "model_id": model_id,
        "title": api_model.get('title') or api_model.get('name') or model_id,
        "provider": provider,
        "category": category,
        "modes": modes
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
    elif 'audio' in category or 'audio' in model_id or 'speech' in model_id:
        return 'Audio'
    elif 'music' in category or 'suno' in model_id:
        return 'Music'
    elif 'edit' in model_id or 'upscale' in model_id or 'remove' in model_id or 'watermark' in model_id:
        return 'Tools'
    else:
        return 'Other'


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
    elif 'edit' in model_id_lower:
        return 'image_edit'
    elif 'upscale' in model_id_lower:
        return 'image_upscale'
    elif 'watermark' in model_id_lower or 'remove' in model_id_lower:
        return 'video_edit'
    elif 'music' in model_id_lower:
        return 'music_generation'
    
    # Проверяем по input_schema
    if 'video_url' in properties:
        return 'video_to_video'
    elif 'image_url' in properties or 'image_input' in properties:
        if 'prompt' in properties:
            return 'image_to_video' if 'duration' in properties else 'image_to_image'
        else:
            return 'image_upscale'
    elif 'prompt' in properties:
        return 'text_to_video' if 'duration' in properties else 'text_to_image'
    
    return 'unknown'


def normalize_input_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализует input_schema к стандартному формату."""
    if not schema:
        return {"type": "object", "properties": {}, "required": []}
    
    if 'type' in schema and schema.get('type') == 'object':
        return schema
    
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


def load_current_models() -> Dict[str, Any]:
    """Загружает текущие модели из kie_models.py."""
    try:
        from kie_models import KIE_MODELS
        return {m.get('id', ''): m for m in KIE_MODELS if m.get('id')}
    except ImportError:
        try:
            from kie_models_new import KIE_MODELS
            return KIE_MODELS
        except ImportError:
            logger.warning("⚠️ Не удалось загрузить текущие модели")
            return {}


def check_model_integration(
    api_model_data: Dict[str, Any],
    current_models: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Проверяет интеграцию модели.
    
    Returns:
        {
            "is_present": bool,
            "has_all_modes": bool,
            "missing_modes": List[str],
            "has_input_schema": bool,
            "needs_update": bool
        }
    """
    model_id = api_model_data["model_id"]
    api_modes = set(api_model_data["modes"].keys())
    
    result = {
        "is_present": False,
        "has_all_modes": False,
        "missing_modes": [],
        "has_input_schema": True,
        "needs_update": False
    }
    
    if model_id in current_models:
        result["is_present"] = True
        
        current_model = current_models[model_id]
        
        # Проверяем modes
        if 'modes' in current_model:
            current_modes = set(current_model['modes'].keys())
            missing = api_modes - current_modes
            result["missing_modes"] = list(missing)
            result["has_all_modes"] = len(missing) == 0
        elif 'generation_type' in current_model:
            # Старая структура - один mode
            current_mode = current_model['generation_type']
            if current_mode not in api_modes:
                result["missing_modes"] = list(api_modes)
                result["has_all_modes"] = False
            else:
                result["has_all_modes"] = True
        
        # Проверяем input_schema
        for mode_key, mode_data in api_model_data["modes"].items():
            input_schema = mode_data.get("input_schema", {})
            if not input_schema or not input_schema.get("properties"):
                result["has_input_schema"] = False
                break
        
        result["needs_update"] = (
            not result["has_all_modes"] or
            not result["has_input_schema"]
        )
    else:
        result["needs_update"] = True
    
    return result


def generate_model_code(api_model_data: Dict[str, Any]) -> str:
    """Генерирует код для добавления модели в kie_models.py."""
    model_id = api_model_data["model_id"]
    title = api_model_data["title"]
    provider = api_model_data["provider"]
    category = api_model_data["category"]
    modes = api_model_data["modes"]
    
    code = f"""    {{
        "id": "{model_id}",
        "name": "{title}",
        "provider": "{provider}",
        "category": "{category}",
        "description": "{api_model_data.get('description', '')}",
        "modes": {{
"""
    
    for mode_key, mode_data in modes.items():
        generation_type = mode_data["generation_type"]
        input_schema = mode_data["input_schema"]
        help_text = mode_data.get("help", "").replace('"', '\\"')
        
        code += f"""            "{mode_key}": {{
                "model": "{mode_data['api_model']}",
                "generation_type": "{generation_type}",
                "category": "{category}",
                "input_schema": {json.dumps(input_schema, ensure_ascii=False, indent=20)},
                "help": "{help_text}"
            }},
"""
    
    code += """        }
    },
"""
    
    return code


async def main():
    """Основная функция полной интеграции."""
    logger.info("🚀 Начало полной проверки и интеграции всех 47 моделей...")
    
    # 1. Получаем все модели из API
    logger.info("📡 Получение всех моделей из KIE API...")
    api_models = await fetch_all_47_models()
    
    if not api_models:
        logger.error("❌ Не удалось получить модели из API")
        return 1
    
    logger.info(f"✅ Получено {len(api_models)} моделей из API")
    
    # 2. Извлекаем данные о моделях
    logger.info("📋 Извлечение данных о моделях...")
    processed_models = []
    for api_model in api_models:
        model_data = extract_model_types_and_modes(api_model)
        processed_models.append(model_data)
    
    # 3. Загружаем текущие модели
    current_models = load_current_models()
    
    # 4. Проверяем интеграцию каждой модели
    logger.info("🔍 Проверка интеграции моделей...")
    integration_report = {
        "total_models": len(processed_models),
        "present_models": 0,
        "missing_models": [],
        "models_needing_update": [],
        "models_with_missing_modes": [],
        "models_without_schema": []
    }
    
    for model_data in processed_models:
        check_result = check_model_integration(model_data, current_models)
        
        if not check_result["is_present"]:
            integration_report["missing_models"].append(model_data["model_id"])
        else:
            integration_report["present_models"] += 1
        
        if check_result["needs_update"]:
            integration_report["models_needing_update"].append({
                "model_id": model_data["model_id"],
                "missing_modes": check_result["missing_modes"],
                "has_input_schema": check_result["has_input_schema"]
            })
        
        if check_result["missing_modes"]:
            integration_report["models_with_missing_modes"].append({
                "model_id": model_data["model_id"],
                "missing_modes": check_result["missing_modes"]
            })
        
        if not check_result["has_input_schema"]:
            integration_report["models_without_schema"].append(model_data["model_id"])
    
    # 5. Выводим отчёт
    print("\n" + "="*80)
    print("📊 ОТЧЁТ ПОЛНОЙ ИНТЕГРАЦИИ ВСЕХ 47 МОДЕЛЕЙ")
    print("="*80)
    
    print(f"\n📋 СТАТИСТИКА:")
    print(f"  Всего моделей в API: {integration_report['total_models']}")
    print(f"  Моделей присутствует: {integration_report['present_models']}")
    print(f"  Моделей отсутствует: {len(integration_report['missing_models'])}")
    print(f"  Моделей требуют обновления: {len(integration_report['models_needing_update'])}")
    
    if integration_report['missing_models']:
        print(f"\n❌ ОТСУТСТВУЮЩИЕ МОДЕЛИ ({len(integration_report['missing_models'])}):")
        for model_id in integration_report['missing_models']:
            print(f"  - {model_id}")
    
    if integration_report['models_with_missing_modes']:
        print(f"\n⚠️ МОДЕЛИ С ОТСУТСТВУЮЩИМИ MODES ({len(integration_report['models_with_missing_modes'])}):")
        for item in integration_report['models_with_missing_modes']:
            print(f"  {item['model_id']}:")
            for mode in item['missing_modes']:
                print(f"    - {mode}")
    
    if integration_report['models_without_schema']:
        print(f"\n⚠️ МОДЕЛИ БЕЗ INPUT_SCHEMA ({len(integration_report['models_without_schema'])}):")
        for model_id in integration_report['models_without_schema']:
            print(f"  - {model_id}")
            print(f"    НЕ ХВАТАЕТ ДАННЫХ:")
            print(f"    - Уточнить required input_schema")
            print(f"    - Уточнить available modes")
    
    # 6. Генерируем код для добавления моделей
    if integration_report['missing_models'] or integration_report['models_needing_update']:
        print(f"\n💾 ГЕНЕРАЦИЯ КОДА ДЛЯ ДОБАВЛЕНИЯ МОДЕЛЕЙ...")
        
        new_models_code = []
        for model_data in processed_models:
            if model_data["model_id"] in integration_report['missing_models']:
                code = generate_model_code(model_data)
                new_models_code.append(code)
        
        if new_models_code:
            output_file = root_dir / "new_models_to_add.py"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# Автоматически сгенерированный код для добавления новых моделей\n")
                f.write("# Добавьте эти модели в kie_models.py\n\n")
                f.write("NEW_MODELS = [\n")
                f.write("".join(new_models_code))
                f.write("]\n")
            
            logger.info(f"✅ Код для добавления моделей сохранён в {output_file}")
            print(f"\n✅ Код для добавления {len(new_models_code)} моделей сохранён в {output_file}")
    
    # 7. Сохраняем полный отчёт
    report_file = root_dir / "FULL_INTEGRATION_REPORT.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "integration_report": integration_report,
            "processed_models": processed_models
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Полный отчёт сохранён в {report_file}")
    
    print("\n" + "="*80)
    print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
    print("="*80)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

