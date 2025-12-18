#!/usr/bin/env python3
"""
Полная синхронизация с KIE.ai Market.
Получает все модели, сравнивает с текущими, автоматически добавляет новые.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
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
            logger.warning("⚠️ API не вернул модели")
            return []
        
        logger.info(f"✅ Получено {len(models)} моделей из API")
        
        # Получаем детали для каждой модели
        detailed_models = []
        for model in models:
            model_id = model.get('id') or model.get('model_id') or model.get('name', '')
            if not model_id:
                continue
            
            model_details = await client.get_model(model_id)
            if model_details:
                detailed_models.append({**model, **model_details})
            else:
                detailed_models.append(model)
        
        return detailed_models
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении моделей: {e}", exc_info=True)
        return []


def load_current_models() -> Dict[str, Any]:
    """Загружает текущие модели из kie_models.py."""
    try:
        from kie_models import KIE_MODELS
        return KIE_MODELS
    except ImportError:
        try:
            from kie_models_new import KIE_MODELS
            return KIE_MODELS
        except ImportError:
            logger.warning("⚠️ Не удалось загрузить текущие модели")
            return []


def extract_modes_from_api_model(api_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Извлекает все modes из модели API."""
    modes = []
    
    model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
    model_types = api_model.get('model_types', [])
    input_schema = api_model.get('input_schema') or api_model.get('inputSchema') or {}
    
    if model_types:
        for model_type in model_types:
            type_id = model_type.get('id') or model_type.get('type_id') or model_type.get('name', '')
            type_schema = model_type.get('input_schema') or model_type.get('inputSchema') or input_schema
            
            generation_type = determine_generation_type(type_id, type_schema)
            
            mode = {
                "model": model_id,
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
    """Определяет тип генерации."""
    model_id_lower = model_id.lower()
    
    if 'text-to-video' in model_id_lower:
        return 'text_to_video'
    elif 'image-to-video' in model_id_lower:
        return 'image_to_video'
    elif 'video-to-video' in model_id_lower:
        return 'video_to_video'
    elif 'text-to-image' in model_id_lower:
        return 'text_to_image'
    elif 'image-to-image' in model_id_lower:
        return 'image_to_image'
    elif 'edit' in model_id_lower:
        return 'image_edit'
    elif 'upscale' in model_id_lower:
        return 'image_upscale'
    elif 'watermark' in model_id_lower:
        return 'video_edit'
    elif 'music' in model_id_lower:
        return 'music_generation'
    
    properties = input_schema.get('properties', {})
    
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


def determine_category(generation_type: str) -> str:
    """Определяет категорию."""
    if 'video' in generation_type:
        return 'Video'
    elif 'image' in generation_type:
        return 'Image'
    elif 'audio' in generation_type or 'music' in generation_type:
        return 'Audio'
    else:
        return 'Tools'


def determine_pricing_unit(generation_type: str, input_schema: Dict[str, Any]) -> str:
    """Определяет единицу ценообразования."""
    if 'video' in generation_type:
        return 'per_5s'
    elif 'image' in generation_type:
        return 'per_image'
    else:
        return 'per_use'


def normalize_input_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализует input_schema."""
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
            
            properties[param_name] = prop
            
            if param_data.get('required', False):
                required.append(param_name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    return schema


def compare_and_find_new_models(
    api_models: List[Dict[str, Any]],
    current_models: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Сравнивает API модели с текущими и находит новые."""
    current_model_ids = {m.get('id', '') for m in current_models if m.get('id')}
    
    new_models = []
    new_modes = {}
    new_parameters = {}
    
    for api_model in api_models:
        model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
        if not model_id:
            continue
        
        if model_id not in current_model_ids:
            # Новая модель
            new_models.append(api_model)
            
            # Извлекаем modes
            modes = extract_modes_from_api_model(api_model)
            new_modes[model_id] = modes
        else:
            # Модель существует, проверяем modes
            current_model = next((m for m in current_models if m.get('id') == model_id), None)
            if current_model:
                api_modes = extract_modes_from_api_model(api_model)
                current_mode_ids = set()
                
                # Собираем текущие mode IDs
                if 'modes' in current_model:
                    current_mode_ids = set(current_model['modes'].keys())
                elif 'generation_type' in current_model:
                    current_mode_ids = {current_model['generation_type']}
                
                # Проверяем новые modes
                for mode_info in api_modes:
                    mode_id = mode_info['mode_id']
                    if mode_id not in current_mode_ids:
                        if model_id not in new_modes:
                            new_modes[model_id] = []
                        new_modes[model_id].append(mode_info)
    
    return {
        "new_models": new_models,
        "new_modes": new_modes,
        "new_parameters": new_parameters
    }


def auto_add_new_models_to_kie_models(
    new_data: Dict[str, Any],
    kie_models_file: Path
) -> bool:
    """Автоматически добавляет новые модели в kie_models.py."""
    try:
        # Читаем текущий файл
        with open(kie_models_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Создаём резервную копию
        backup_file = kie_models_file.with_suffix('.py.backup')
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"✅ Создана резервная копия: {backup_file}")
        
        # Добавляем новые модели
        new_models_code = []
        
        for api_model in new_data['new_models']:
            model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
            modes = extract_modes_from_api_model(api_model)
            
            # Формируем код для новой модели
            model_code = f"""
    {{
        "id": "{model_id}",
        "name": "{api_model.get('title', api_model.get('name', model_id))}",
        "description": "{api_model.get('description', '')}",
        "category": "{determine_category(modes[0]['mode_data']['generation_type']) if modes else 'Other'}",
        "modes": {{
"""
            
            for mode_info in modes:
                mode_id = mode_info['mode_id']
                mode_data = mode_info['mode_data']
                
                model_code += f"""
            "{mode_id}": {{
                "model": "{mode_data['model']}",
                "generation_type": "{mode_data['generation_type']}",
                "category": "{mode_data['category']}",
                "input_schema": {json.dumps(mode_data['input_schema'], ensure_ascii=False, indent=16)},
                "pricing_unit": "{mode_data['pricing_unit']}",
                "help": "{mode_data['help']}"
            }},
"""
            
            model_code += """
        }
    },
"""
            new_models_code.append(model_code)
        
        # Добавляем в конец файла перед закрывающей скобкой
        if ']' in content:
            content = content.rstrip()
            if content.endswith(']'):
                content = content[:-1]
                content += ',\n'.join(new_models_code)
                content += '\n]'
        
        # Записываем обновлённый файл
        with open(kie_models_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"✅ Добавлено {len(new_data['new_models'])} новых моделей в {kie_models_file}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении моделей: {e}", exc_info=True)
        return False


async def main():
    """Основная функция полной синхронизации."""
    logger.info("🚀 Начало полной синхронизации с KIE.ai Market...")
    
    # 1. Получаем модели из API
    api_models = await fetch_all_models_from_api()
    
    if not api_models:
        logger.error("❌ Не удалось получить модели из API")
        return 1
    
    # 2. Загружаем текущие модели
    current_models = load_current_models()
    
    # 3. Сравниваем и находим новые
    new_data = compare_and_find_new_models(api_models, current_models)
    
    # 4. Выводим отчёт
    print("\n" + "="*80)
    print("📊 ОТЧЁТ ПОЛНОЙ СИНХРОНИЗАЦИИ")
    print("="*80)
    
    print(f"\n📋 СТАТИСТИКА:")
    print(f"  Моделей в API: {len(api_models)}")
    print(f"  Моделей локально: {len(current_models)}")
    print(f"  Новых моделей: {len(new_data['new_models'])}")
    
    total_new_modes = sum(len(modes) for modes in new_data['new_modes'].values())
    print(f"  Новых modes: {total_new_modes}")
    
    if new_data['new_models']:
        print(f"\n🆕 НОВЫЕ МОДЕЛИ:")
        for model in new_data['new_models']:
            model_id = model.get('id') or model.get('model_id') or model.get('name', '')
            print(f"  - {model_id}")
    
    if new_data['new_modes']:
        print(f"\n🆕 НОВЫЕ MODES:")
        for model_id, modes in new_data['new_modes'].items():
            print(f"  {model_id}:")
            for mode_info in modes:
                print(f"    - {mode_info['mode_id']}")
    
    # 5. Автоматически добавляем новые модели
    if new_data['new_models']:
        kie_models_file = root_dir / "kie_models.py"
        if kie_models_file.exists():
            print(f"\n💾 Автоматическое добавление новых моделей...")
            success = auto_add_new_models_to_kie_models(new_data, kie_models_file)
            if success:
                print("✅ Новые модели успешно добавлены!")
            else:
                print("❌ Ошибка при добавлении моделей")
        else:
            print(f"\n⚠️ Файл {kie_models_file} не найден")
    
    print("\n" + "="*80)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

