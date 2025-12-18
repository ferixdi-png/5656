#!/usr/bin/env python3
"""
Автоматическая синхронизация моделей KIE AI с локальной структурой.
Проверяет все модели и их modes, выводит детальный отчёт.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
from dotenv import load_dotenv

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


async def fetch_all_models_from_api() -> List[Dict[str, Any]]:
    """Получает все модели из KIE API."""
    try:
        from kie_client import get_client
        
        client = get_client()
        models = await client.list_models()
        
        if not models:
            logger.warning("⚠️ API не вернул модели. Проверьте KIE_API_KEY и KIE_API_URL")
            return []
        
        logger.info(f"✅ Получено {len(models)} моделей из KIE API")
        return models
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении моделей из API: {e}", exc_info=True)
        return []


async def fetch_model_details(model_id: str) -> Optional[Dict[str, Any]]:
    """Получает детальную информацию о модели из API."""
    try:
        from kie_client import get_client
        
        client = get_client()
        model_info = await client.get_model(model_id)
        return model_info
        
    except Exception as e:
        logger.debug(f"⚠️ Не удалось получить детали для {model_id}: {e}")
        return None


def extract_modes_from_api_model(api_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Извлекает modes из модели API.
    KIE API может возвращать модели с разными типами (Model Type).
    """
    modes = []
    
    model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
    model_types = api_model.get('model_types', [])
    input_schema = api_model.get('input_schema') or api_model.get('inputSchema') or {}
    
    # Если есть model_types, создаём mode для каждого типа
    if model_types:
        for model_type in model_types:
            type_id = model_type.get('id') or model_type.get('type_id') or model_type.get('name', '')
            type_schema = model_type.get('input_schema') or model_type.get('inputSchema') or input_schema
            
            # Определяем generation_type по названию типа или схеме
            generation_type = determine_generation_type(type_id, type_schema)
            
            mode = {
                "model": model_id,  # Реальный API model string
                "generation_type": generation_type,
                "category": determine_category(generation_type),
                "input_schema": normalize_input_schema(type_schema),
                "pricing_unit": determine_pricing_unit(generation_type, type_schema),
                "help": model_type.get('description') or model_type.get('help') or api_model.get('description', '')
            }
            
            modes.append({
                "mode_id": type_id or generation_type,
                "mode_data": mode
            })
    else:
        # Если нет model_types, создаём один mode на основе input_schema
        generation_type = determine_generation_type(model_id, input_schema)
        
        mode = {
            "model": model_id,
            "generation_type": generation_type,
            "category": determine_category(generation_type),
            "input_schema": normalize_input_schema(input_schema),
            "pricing_unit": determine_pricing_unit(generation_type, input_schema),
            "help": api_model.get('description') or api_model.get('help', '')
        }
        
        modes.append({
            "mode_id": generation_type,
            "mode_data": mode
        })
    
    return modes


def determine_generation_type(model_id: str, input_schema: Dict[str, Any]) -> str:
    """Определяет тип генерации на основе model_id и input_schema."""
    model_id_lower = model_id.lower()
    
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
        return 'text_to_music'
    
    # Проверяем по input_schema
    properties = input_schema.get('properties', {})
    
    if 'video_url' in properties:
        return 'video_to_video'
    elif 'image_urls' in properties or 'image_input' in properties or 'image_url' in properties:
        if 'prompt' in properties:
            return 'image_to_video' if 'duration' in properties or 'n_frames' in properties else 'image_to_image'
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


def determine_category(generation_type: str) -> str:
    """Определяет категорию на основе типа генерации."""
    if 'video' in generation_type:
        return 'Video'
    elif 'image' in generation_type or 'upscale' in generation_type:
        return 'Image'
    elif 'audio' in generation_type or 'speech' in generation_type or 'music' in generation_type:
        return 'Audio'
    elif 'edit' in generation_type or 'remove' in generation_type:
        return 'Tools'
    else:
        return 'Other'


def determine_pricing_unit(generation_type: str, input_schema: Dict[str, Any]) -> str:
    """Определяет единицу ценообразования."""
    if 'video' in generation_type:
        # Проверяем duration в схеме
        properties = input_schema.get('properties', {})
        duration = properties.get('duration') or properties.get('n_frames')
        if duration:
            if isinstance(duration, dict):
                default = duration.get('default', 10)
                if default and int(default) > 10:
                    return 'per_10s'
            return 'per_5s'
        return 'per_5s'
    elif 'image' in generation_type:
        return 'per_image'
    elif 'audio' in generation_type or 'speech' in generation_type or 'music' in generation_type:
        return 'per_minute'
    else:
        return 'per_use'


def normalize_input_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализует input_schema к стандартному формату."""
    if not schema:
        return {"type": "object", "properties": {}, "required": []}
    
    # Если schema уже в правильном формате
    if 'type' in schema and schema.get('type') == 'object':
        return schema
    
    # Если это старый формат (input_params)
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


def load_local_models() -> Dict[str, Any]:
    """Загружает локальные модели из kie_models_new.py."""
    try:
        sys.path.insert(0, str(root_dir))
        from kie_models_new import KIE_MODELS
        return KIE_MODELS
    except ImportError:
        logger.warning("⚠️ kie_models_new.py не найден, пробуем старую структуру")
        try:
            from kie_models import KIE_MODELS as OLD_MODELS
            # Конвертируем старую структуру
            return convert_old_structure(OLD_MODELS)
        except ImportError:
            logger.error("❌ Не удалось загрузить локальные модели")
            return {}


def convert_old_structure(old_models: List[Dict]) -> Dict[str, Any]:
    """Конвертирует старую структуру в новую (временная функция)."""
    result = {}
    for model in old_models:
        model_id = model.get('id', '')
        if not model_id:
            continue
        
        # Определяем model_key (provider/model_name)
        model_key = model_id
        if '/' in model_id:
            model_key = model_id
        else:
            # Пытаемся определить provider
            provider = determine_provider(model_id)
            model_key = f"{provider}/{model_id}"
        
        # Определяем mode
        generation_type = determine_generation_type(model_id, model.get('input_params', {}))
        
        if model_key not in result:
            result[model_key] = {
                "title": model.get('name', model_id),
                "provider": provider,
                "description": model.get('description', ''),
                "modes": {}
            }
        
        mode_data = {
            "model": model_id,
            "generation_type": generation_type,
            "category": determine_category(generation_type),
            "input_schema": normalize_input_schema(model.get('input_params', {})),
            "pricing_unit": determine_pricing_unit(generation_type, model.get('input_params', {})),
            "help": model.get('description', '')
        }
        
        result[model_key]["modes"][generation_type] = mode_data
    
    return result


def determine_provider(model_id: str) -> str:
    """Определяет provider на основе model_id."""
    if 'sora' in model_id.lower():
        return 'openai'
    elif 'kling' in model_id.lower():
        return 'kling'
    elif 'wan' in model_id.lower():
        return 'wan'
    elif 'seedream' in model_id.lower() or 'bytedance' in model_id.lower():
        return 'bytedance'
    elif 'nano' in model_id.lower() or 'banana' in model_id.lower() or 'gemini' in model_id.lower():
        return 'google'
    elif 'veo' in model_id.lower():
        return 'google'
    elif 'flux' in model_id.lower():
        return 'blackforest'
    elif 'qwen' in model_id.lower():
        return 'qwen'
    elif 'elevenlabs' in model_id.lower():
        return 'elevenlabs'
    elif 'hailuo' in model_id.lower():
        return 'hailuo'
    elif 'topaz' in model_id.lower():
        return 'topaz'
    elif 'recraft' in model_id.lower():
        return 'recraft'
    elif 'ideogram' in model_id.lower():
        return 'ideogram'
    elif 'infinitalk' in model_id.lower():
        return 'infinitalk'
    elif 'suno' in model_id.lower():
        return 'suno'
    elif 'midjourney' in model_id.lower():
        return 'midjourney'
    elif 'runway' in model_id.lower():
        return 'runway'
    elif 'grok' in model_id.lower():
        return 'xai'
    elif 'z-image' in model_id.lower():
        return 'tongyi'
    else:
        return 'unknown'


def check_models_sync(
    api_models: List[Dict[str, Any]],
    local_models: Dict[str, Any]
) -> Dict[str, Any]:
    """Проверяет синхронизацию моделей и modes."""
    report = {
        "total_api_models": len(api_models),
        "total_local_models": len(local_models),
        "total_local_modes": sum(len(m.get("modes", {})) for m in local_models.values()),
        "missing_models": [],
        "missing_modes": {},
        "schema_errors": [],
        "missing_schemas": [],
        "outdated_models": [],
        "new_models": [],
        "api_modes": {}
    }
    
    # Извлекаем modes из API моделей
    api_modes_by_model = {}
    for api_model in api_models:
        model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
        if not model_id:
            continue
        
        provider = determine_provider(model_id)
        model_key = model_id if '/' in model_id else f"{provider}/{model_id}"
        
        modes = extract_modes_from_api_model(api_model)
        api_modes_by_model[model_key] = modes
        report["api_modes"][model_key] = [m["mode_id"] for m in modes]
    
    # Проверяем локальные модели
    for model_key, model_data in local_models.items():
        local_modes = model_data.get("modes", {})
        
        if model_key not in api_modes_by_model:
            report["outdated_models"].append(model_key)
        else:
            api_modes = api_modes_by_model[model_key]
            api_mode_ids = {m["mode_id"] for m in api_modes}
            local_mode_ids = set(local_modes.keys())
            
            missing_modes = api_mode_ids - local_mode_ids
            if missing_modes:
                report["missing_modes"][model_key] = list(missing_modes)
            
            # Проверяем input_schema
            for mode_id, mode_data in local_modes.items():
                input_schema = mode_data.get("input_schema")
                if not input_schema:
                    report["missing_schemas"].append(f"{model_key}:{mode_id}")
                elif not isinstance(input_schema, dict):
                    report["schema_errors"].append(f"{model_key}:{mode_id} - input_schema не словарь")
                elif "properties" not in input_schema:
                    report["schema_errors"].append(f"{model_key}:{mode_id} - нет properties")
    
    # Проверяем новые модели из API
    for model_key, api_modes in api_modes_by_model.items():
        if model_key not in local_models:
            report["new_models"].append(model_key)
            report["missing_models"].append(model_key)
    
    return report


def print_detailed_report(report: Dict[str, Any]):
    """Выводит детальный отчёт о синхронизации."""
    print("\n" + "="*80)
    print("📊 ОТЧЁТ О СИНХРОНИЗАЦИИ МОДЕЛЕЙ KIE AI")
    print("="*80)
    
    print(f"\n📋 ОБЩАЯ СТАТИСТИКА:")
    print(f"  Всего моделей в KIE AI: 47 (ожидается)")
    print(f"  Моделей в API: {report['total_api_models']}")
    print(f"  Моделей в локальной структуре: {report['total_local_models']}")
    print(f"  Всего modes в локальной структуре: {report['total_local_modes']}")
    
    # Интегрировано
    integrated_models = report['total_local_models']
    integrated_modes = report['total_local_modes']
    print(f"\n✅ ИНТЕГРИРОВАНО:")
    print(f"  Моделей: {integrated_models}/47")
    print(f"  Modes: {integrated_modes}")
    
    # Отсутствующие модели
    if report['missing_models']:
        print(f"\n❌ ОТСУТСТВУЮЩИЕ МОДЕЛИ ({len(report['missing_models'])}):")
        for model in report['missing_models']:
            print(f"  - {model}")
            api_modes = report['api_modes'].get(model, [])
            if api_modes:
                print(f"    Нужны modes: {', '.join(api_modes)}")
    else:
        print("\n✅ Все модели присутствуют")
    
    # Отсутствующие modes
    if report['missing_modes']:
        print(f"\n⚠️ ОТСУТСТВУЮЩИЕ MODES:")
        for model_key, modes in report['missing_modes'].items():
            print(f"  {model_key}:")
            for mode in modes:
                print(f"    - {mode}")
    else:
        print("\n✅ Все modes присутствуют")
    
    # Проблемы с схемами
    if report['schema_errors']:
        print(f"\n⚠️ ПРОБЛЕМЫ С INPUT_SCHEMA ({len(report['schema_errors'])}):")
        for error in report['schema_errors'][:10]:
            print(f"  - {error}")
        if len(report['schema_errors']) > 10:
            print(f"  ... и еще {len(report['schema_errors']) - 10} ошибок")
    else:
        print("\n✅ Все input_schema корректны")
    
    # Отсутствующие схемы
    if report['missing_schemas']:
        print(f"\n❌ ОТСУТСТВУЮЩИЕ INPUT_SCHEMA:")
        for missing in report['missing_schemas']:
            print(f"  - {missing}")
            model_key, mode_id = missing.split(':')
            print(f"    НЕ ХВАТАЕТ ДАННЫХ ДЛЯ МОДЕЛИ {model_key}:{mode_id}:")
            print(f"    - Уточнить required input_schema")
            print(f"    - Уточнить available modes")
            print(f"    - Уточнить pricing")
    
    # Устаревшие модели
    if report['outdated_models']:
        print(f"\n⚠️ УСТАРЕВШИЕ МОДЕЛИ (есть локально, но нет в API):")
        for model in report['outdated_models']:
            print(f"  - {model}")
    
    # Новые модели
    if report['new_models']:
        print(f"\n🆕 НОВЫЕ МОДЕЛИ В API (нет локально):")
        for model in report['new_models']:
            print(f"  - {model}")
            api_modes = report['api_modes'].get(model, [])
            if api_modes:
                print(f"    Modes: {', '.join(api_modes)}")
    
    print("\n" + "="*80)
    
    # Итоговая оценка
    total_issues = (
        len(report['missing_models']) +
        sum(len(modes) for modes in report['missing_modes'].values()) +
        len(report['schema_errors']) +
        len(report['missing_schemas'])
    )
    
    if total_issues == 0:
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ Интеграция идеальна!")
        return 0
    else:
        print(f"⚠️ Обнаружено проблем: {total_issues}")
        print("\n❗ КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
        
        for model_key in report['missing_models']:
            api_modes = report['api_modes'].get(model_key, [])
            print(f"\n  НЕ ХВАТАЕТ ДАННЫХ ДЛЯ МОДЕЛИ {model_key}:")
            print(f"    - Уточнить required input_schema")
            print(f"    - Уточнить available modes: {', '.join(api_modes) if api_modes else 'неизвестно'}")
            print(f"    - Уточнить pricing")
        
        for model_key, modes in report['missing_modes'].items():
            print(f"\n  НЕ ХВАТАЕТ MODES ДЛЯ МОДЕЛИ {model_key}:")
            for mode in modes:
                print(f"    - {mode}")
        
        return 1


async def main():
    """Основная функция синхронизации."""
    logger.info("🚀 Начало синхронизации моделей KIE AI...")
    
    # Получаем модели из API
    api_models = await fetch_all_models_from_api()
    
    # Загружаем локальные модели
    local_models = load_local_models()
    
    # Проверяем синхронизацию
    report = check_models_sync(api_models, local_models)
    
    # Выводим отчёт
    exit_code = print_detailed_report(report)
    
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
