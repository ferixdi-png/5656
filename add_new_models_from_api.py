#!/usr/bin/env python3
"""
Скрипт для добавления новых моделей из KIE API в kie_models.py.
Проверяет, какие модели есть в API, но отсутствуют в коде, и добавляет их.
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
from kie_client import get_client
from kie_models import KIE_MODELS, get_model_by_id, normalize_model_info

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_api_model_to_kie_format(api_model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализует модель из API к формату kie_models.py.
    """
    model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
    title = api_model.get('title') or api_model.get('name') or model_id
    description = api_model.get('description') or api_model.get('help') or api_model.get('instructions', '')
    category = api_model.get('category') or api_model.get('type') or 'Unknown'
    emoji = api_model.get('emoji') or '✨'
    
    # Получаем input_schema
    input_schema = api_model.get('input_schema') or api_model.get('input_params') or api_model.get('input') or {}
    
    # Определяем generation_type на основе model_id и input_schema
    generation_type = api_model.get('generation_type') or api_model.get('type') or 'unknown'
    if generation_type == 'unknown':
        if 'text-to-image' in model_id.lower() or 'text_to_image' in model_id.lower():
            generation_type = 'text-to-image'
        elif 'image-to-image' in model_id.lower() or 'image_to_image' in model_id.lower():
            generation_type = 'image-to-image'
        elif 'text-to-video' in model_id.lower() or 'text_to_video' in model_id.lower():
            generation_type = 'text-to-video'
        elif 'image-to-video' in model_id.lower() or 'image_to_video' in model_id.lower():
            generation_type = 'image-to-video'
        elif 'edit' in model_id.lower():
            generation_type = 'image-edit'
        elif 'upscale' in model_id.lower():
            generation_type = 'image-upscale'
        elif 'video' in model_id.lower():
            generation_type = 'video-processing'
    
    # Определяем pricing (примерная оценка)
    pricing = api_model.get('pricing') or "Цена уточняется"
    
    # Формируем help текст
    help_text = description
    if not help_text:
        if 'text-to-image' in generation_type:
            help_text = "Отправь текстовый промпт, выбери соотношение сторон и получи изображение."
        elif 'image-to-image' in generation_type:
            help_text = "Отправь изображение и текстовый промпт для трансформации."
        elif 'text-to-video' in generation_type:
            help_text = "Отправь текстовый промпт и получи видео."
        elif 'image-to-video' in generation_type:
            help_text = "Отправь изображение и получи видео."
        else:
            help_text = f"Используй модель {title} для генерации."
    
    # Формируем example_prompt
    example_prompt = api_model.get('example_prompt') or api_model.get('example')
    if not example_prompt:
        if 'text-to-image' in generation_type or 'image-to-image' in generation_type:
            example_prompt = "Красивый закат над океаном с летающими птицами"
        elif 'text-to-video' in generation_type or 'image-to-video' in generation_type:
            example_prompt = "Спокойное видео с волнами на пляже"
        else:
            example_prompt = "Пример запроса для генерации"
    
    # Создаем нормализованную модель
    normalized = {
        "id": model_id,
        "name": title,
        "description": description,
        "category": category,
        "emoji": emoji,
        "pricing": pricing,
        "input_params": input_schema,
        "generation_type": generation_type,
        "help": help_text,
        "example_prompt": example_prompt
    }
    
    return normalized


def format_model_for_kie_models_py(model: Dict[str, Any], indent: int = 1) -> str:
    """
    Форматирует модель для вставки в kie_models.py.
    """
    indent_str = "    " * indent
    next_indent = "    " * (indent + 1)
    
    lines = [f"{indent_str}{{"]
    
    # Обязательные поля
    lines.append(f'{next_indent}"id": "{model["id"]}",')
    lines.append(f'{next_indent}"name": "{model["name"]}",')
    lines.append(f'{next_indent}"description": "{model["description"]}",')
    lines.append(f'{next_indent}"category": "{model["category"]}",')
    lines.append(f'{next_indent}"emoji": "{model["emoji"]}",')
    lines.append(f'{next_indent}"pricing": "{model["pricing"]}",')
    
    # input_params
    lines.append(f'{next_indent}"input_params": {{')
    input_params = model.get("input_params", {})
    if input_params:
        for param_name, param_info in input_params.items():
            if isinstance(param_info, dict):
                lines.append(f'{next_indent}    "{param_name}": {{')
                for key, value in param_info.items():
                    if isinstance(value, str):
                        lines.append(f'{next_indent}        "{key}": "{value}",')
                    elif isinstance(value, bool):
                        lines.append(f'{next_indent}        "{key}": {str(value).lower()},')
                    elif isinstance(value, (int, float)):
                        lines.append(f'{next_indent}        "{key}": {value},')
                    elif isinstance(value, list):
                        items_str = ", ".join([f'"{item}"' if isinstance(item, str) else str(item) for item in value])
                        lines.append(f'{next_indent}        "{key}": [{items_str}],')
                    else:
                        lines.append(f'{next_indent}        "{key}": {json.dumps(value, ensure_ascii=False)},')
                lines.append(f'{next_indent}    }},')
            else:
                lines.append(f'{next_indent}    "{param_name}": {json.dumps(param_info, ensure_ascii=False)},')
    lines.append(f'{next_indent}}}')
    
    lines.append(f"{indent_str}}},")
    
    return "\n".join(lines)


async def fetch_models_from_api() -> List[Dict[str, Any]]:
    """Загружает все модели из KIE API."""
    client = get_client()
    
    logger.info("📡 Загрузка моделей из KIE API...")
    models = await client.list_models()
    
    if not models:
        logger.warning("⚠️ Не удалось загрузить модели из API. Возможные причины:")
        logger.warning("  - KIE_API_KEY не установлен")
        logger.warning("  - API недоступен")
        logger.warning("  - Неверный endpoint")
        return []
    
    logger.info(f"✅ Загружено {len(models)} моделей из API")
    return models


async def find_missing_models() -> List[Dict[str, Any]]:
    """
    Находит модели из API, которые отсутствуют в kie_models.py.
    """
    # Загружаем модели из API
    api_models = await fetch_models_from_api()
    
    if not api_models:
        logger.warning("⚠️ Не удалось загрузить модели из API. Продолжаем с пустым списком.")
        return []
    
    # Получаем модели из кода
    code_model_ids = {model['id'] for model in KIE_MODELS}
    
    # Находим недостающие модели
    missing_models = []
    for api_model in api_models:
        normalized = normalize_api_model_to_kie_format(api_model)
        model_id = normalized['id']
        
        if model_id and model_id not in code_model_ids:
            missing_models.append(normalized)
            logger.info(f"➕ Найдена новая модель: {model_id} ({normalized['name']})")
    
    return missing_models


def add_models_to_kie_models_py(new_models: List[Dict[str, Any]], output_file: str = None) -> str:
    """
    Добавляет новые модели в kie_models.py.
    Возвращает строку с кодом для вставки.
    """
    if not new_models:
        return ""
    
    lines = []
    lines.append("\n# Новые модели, добавленные из KIE API")
    lines.append("# Автоматически сгенерировано скриптом add_new_models_from_api.py")
    lines.append("")
    
    for model in new_models:
        model_code = format_model_for_kie_models_py(model, indent=1)
        lines.append(model_code)
        lines.append("")
    
    return "\n".join(lines)


async def main():
    """Основная функция."""
    try:
        logger.info("🔍 Поиск новых моделей из KIE API...")
        
        missing_models = await find_missing_models()
        
        if not missing_models:
            logger.info("✅ Все модели из API уже присутствуют в коде!")
            return 0
        
        logger.info(f"\n📊 Найдено {len(missing_models)} новых моделей:")
        for model in missing_models:
            logger.info(f"  • {model['id']} - {model['name']} ({model['category']})")
        
        # Генерируем код для добавления
        new_code = add_models_to_kie_models_py(missing_models)
        
        # Сохраняем в файл
        output_file = root_dir / "NEW_MODELS_TO_ADD.py"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(new_code)
        
        logger.info(f"\n✅ Код для добавления новых моделей сохранен в {output_file}")
        logger.info(f"📝 Добавьте содержимое файла в конец списка KIE_MODELS в kie_models.py")
        
        # Создаем отчет
        report = {
            'total_missing': len(missing_models),
            'models': [
                {
                    'id': m['id'],
                    'name': m['name'],
                    'category': m['category'],
                    'generation_type': m.get('generation_type', 'unknown'),
                    'has_input_schema': bool(m.get('input_params')),
                    'input_params_count': len(m.get('input_params', {}))
                }
                for m in missing_models
            ]
        }
        
        report_file = root_dir / "NEW_MODELS_REPORT.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 Отчет сохранен в {report_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при поиске новых моделей: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

