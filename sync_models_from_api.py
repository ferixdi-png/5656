#!/usr/bin/env python3
"""
Скрипт для синхронизации моделей из KIE API с kie_models.py.
Получает все модели из API, сравнивает с текущим списком и добавляет недостающие.
"""

import asyncio
import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv

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
    if not model_id:
        return None
    
    title = api_model.get('title') or api_model.get('name') or model_id
    description = api_model.get('description') or api_model.get('help') or api_model.get('instructions', '')
    if not description:
        description = f"Модель {title} для генерации контента."
    
    category = api_model.get('category') or api_model.get('type') or 'Unknown'
    emoji = api_model.get('emoji') or '✨'
    
    # Получаем input_schema
    input_schema = api_model.get('input_schema') or api_model.get('input_params') or api_model.get('input') or {}
    
    # Определяем generation_type на основе model_id и input_schema
    generation_type = api_model.get('generation_type') or api_model.get('type') or 'unknown'
    if generation_type == 'unknown':
        model_id_lower = model_id.lower()
        if 'text-to-image' in model_id_lower or 'text_to_image' in model_id_lower or 'texttoimage' in model_id_lower:
            generation_type = 'text-to-image'
        elif 'image-to-image' in model_id_lower or 'image_to_image' in model_id_lower or 'imagetoimage' in model_id_lower:
            generation_type = 'image-to-image'
        elif 'text-to-video' in model_id_lower or 'text_to_video' in model_id_lower or 'texttovideo' in model_id_lower:
            generation_type = 'text-to-video'
        elif 'image-to-video' in model_id_lower or 'image_to_video' in model_id_lower or 'imagetovideo' in model_id_lower:
            generation_type = 'image-to-video'
        elif 'edit' in model_id_lower:
            generation_type = 'image-edit'
        elif 'upscale' in model_id_lower:
            generation_type = 'image-upscale'
        elif 'video' in model_id_lower:
            generation_type = 'video-processing'
        elif 'audio' in model_id_lower or 'speech' in model_id_lower or 'sound' in model_id_lower:
            generation_type = 'audio-processing'
        else:
            generation_type = 'text-to-image'  # Default
    
    # Определяем pricing (примерная оценка)
    pricing = api_model.get('pricing') or "Цена уточняется"
    
    # Формируем help текст
    help_text = description
    if not help_text or help_text == f"Модель {title} для генерации контента.":
        if 'text-to-image' in generation_type:
            help_text = "Отправь текстовый промпт, выбери соотношение сторон и получи изображение."
        elif 'image-to-image' in generation_type:
            help_text = "Отправь изображение и текстовый промпт для трансформации."
        elif 'text-to-video' in generation_type:
            help_text = "Отправь текстовый промпт и получи видео."
        elif 'image-to-video' in generation_type:
            help_text = "Отправь изображение и получи видео."
        elif 'audio' in generation_type:
            help_text = "Обработка аудио файлов."
        else:
            help_text = f"Используй модель {title} для генерации контента."
    
    # Формируем example_prompt
    example_prompt = api_model.get('example_prompt') or api_model.get('example')
    if not example_prompt:
        if 'text-to-image' in generation_type or 'image-to-image' in generation_type:
            example_prompt = "Красивый закат над океаном с летающими птицами"
        elif 'text-to-video' in generation_type or 'image-to-video' in generation_type:
            example_prompt = "Спокойное видео с волнами на пляже"
        elif 'audio' in generation_type:
            example_prompt = "Пример аудио запроса"
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
    param_indent = "    " * (indent + 2)
    
    lines = [f"{indent_str}{{"]
    
    # Обязательные поля
    lines.append(f'{next_indent}"id": "{model["id"]}",')
    lines.append(f'{next_indent}"name": "{model["name"]}",')
    # Экранируем кавычки в description
    desc = model["description"].replace('"', '\\"').replace('\n', '\\n')
    lines.append(f'{next_indent}"description": "{desc}",')
    lines.append(f'{next_indent}"category": "{model["category"]}",')
    lines.append(f'{next_indent}"emoji": "{model["emoji"]}",')
    pricing = model["pricing"].replace('"', '\\"')
    lines.append(f'{next_indent}"pricing": "{pricing}",')
    
    # input_params
    lines.append(f'{next_indent}"input_params": {{')
    input_params = model.get("input_params", {})
    if input_params:
        for param_name, param_info in input_params.items():
            if isinstance(param_info, dict):
                lines.append(f'{param_indent}"{param_name}": {{')
                for key, value in param_info.items():
                    if key == "enum" and isinstance(value, list):
                        enum_str = ", ".join([f'"{item}"' if isinstance(item, str) else str(item) for item in value])
                        lines.append(f'{param_indent}    "{key}": [{enum_str}],')
                    elif isinstance(value, str):
                        escaped = value.replace('"', '\\"').replace('\n', '\\n')
                        lines.append(f'{param_indent}    "{key}": "{escaped}",')
                    elif isinstance(value, bool):
                        lines.append(f'{param_indent}    "{key}": {str(value).lower()},')
                    elif isinstance(value, (int, float)):
                        lines.append(f'{param_indent}    "{key}": {value},')
                    elif isinstance(value, list):
                        items_str = ", ".join([f'"{item}"' if isinstance(item, str) else str(item) for item in value])
                        lines.append(f'{param_indent}    "{key}": [{items_str}],')
                    else:
                        lines.append(f'{param_indent}    "{key}": {json.dumps(value, ensure_ascii=False)},')
                # Убираем последнюю запятую
                if lines[-1].endswith(','):
                    lines[-1] = lines[-1][:-1]
                lines.append(f'{param_indent}}},')
            else:
                lines.append(f'{param_indent}"{param_name}": {json.dumps(param_info, ensure_ascii=False)},')
    else:
        # Если нет параметров, добавляем минимальный prompt
        lines.append(f'{param_indent}"prompt": {{')
        lines.append(f'{param_indent}    "type": "string",')
        lines.append(f'{param_indent}    "description": "Текстовое описание для генерации",')
        lines.append(f'{param_indent}    "required": True')
        lines.append(f'{param_indent}}}')
    
    lines.append(f'{next_indent}}}')
    lines.append(f"{indent_str}}},")
    
    return "\n".join(lines)


async def fetch_models_from_api() -> List[Dict[str, Any]]:
    """Загружает все модели из KIE API."""
    try:
        from kie_client import get_client
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
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке моделей из API: {e}", exc_info=True)
        return []


def get_current_models() -> Dict[str, Dict[str, Any]]:
    """Получает текущий список моделей из kie_models.py."""
    try:
        from kie_models import KIE_MODELS
        return {model['id']: model for model in KIE_MODELS}
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке моделей из kie_models.py: {e}", exc_info=True)
        return {}


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
    code_models = get_current_models()
    code_model_ids = set(code_models.keys())
    
    # Находим недостающие модели
    missing_models = []
    for api_model in api_models:
        normalized = normalize_api_model_to_kie_format(api_model)
        if not normalized:
            continue
        
        model_id = normalized['id']
        
        if model_id and model_id not in code_model_ids:
            missing_models.append(normalized)
            logger.info(f"➕ Найдена новая модель: {model_id} ({normalized['name']})")
    
    return missing_models


def add_models_to_kie_models_py(new_models: List[Dict[str, Any]], kie_models_file: Path) -> bool:
    """
    Добавляет новые модели в kie_models.py.
    Возвращает True, если модели были добавлены.
    """
    if not new_models:
        return False
    
    # Читаем текущий файл
    try:
        with open(kie_models_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"❌ Ошибка при чтении {kie_models_file}: {e}")
        return False
    
    # Находим место для вставки (перед закрывающей скобкой списка KIE_MODELS)
    # Ищем последнюю модель в списке
    pattern = r'(\s+)\]\s*$'
    match = re.search(pattern, content, re.MULTILINE)
    
    if not match:
        # Пробуем найти просто ]
        pattern = r'\]\s*$'
        match = re.search(pattern, content, re.MULTILINE)
        if not match:
            logger.error("❌ Не удалось найти место для вставки новых моделей")
            return False
    
    # Генерируем код для новых моделей
    new_code_lines = []
    new_code_lines.append("\n    # Новые модели, добавленные из KIE API")
    new_code_lines.append("    # Автоматически сгенерировано скриптом sync_models_from_api.py")
    new_code_lines.append("")
    
    for model in new_models:
        model_code = format_model_for_kie_models_py(model, indent=1)
        new_code_lines.append(model_code)
        new_code_lines.append("")
    
    new_code = "\n".join(new_code_lines)
    
    # Вставляем перед закрывающей скобкой
    insert_pos = match.start()
    new_content = content[:insert_pos] + new_code + "\n" + content[insert_pos:]
    
    # Сохраняем файл
    try:
        # Создаем backup
        backup_file = kie_models_file.with_suffix('.py.backup')
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"💾 Создан backup: {backup_file}")
        
        # Сохраняем новый файл
        with open(kie_models_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        logger.info(f"✅ Добавлено {len(new_models)} новых моделей в {kie_models_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении {kie_models_file}: {e}")
        return False


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
            logger.info(f"    Тип: {model.get('generation_type', 'unknown')}")
            logger.info(f"    Параметров: {len(model.get('input_params', {}))}")
        
        # Добавляем модели в kie_models.py
        kie_models_file = root_dir / "kie_models.py"
        if add_models_to_kie_models_py(missing_models, kie_models_file):
            logger.info(f"\n✅ Модели успешно добавлены в {kie_models_file}")
        else:
            logger.error("❌ Не удалось добавить модели в файл")
            # Сохраняем код для ручного добавления
            new_code = "\n".join([format_model_for_kie_models_py(m, indent=1) for m in missing_models])
            output_file = root_dir / "NEW_MODELS_TO_ADD_MANUAL.py"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# Скопируйте этот код в kie_models.py перед закрывающей скобкой ]\n\n")
                f.write(new_code)
            logger.info(f"📝 Код для ручного добавления сохранен в {output_file}")
            return 1
        
        # Создаем отчет
        report = {
            'total_missing': len(missing_models),
            'added_models': [
                {
                    'id': m['id'],
                    'name': m['name'],
                    'category': m['category'],
                    'generation_type': m.get('generation_type', 'unknown'),
                    'has_input_schema': bool(m.get('input_params')),
                    'input_params_count': len(m.get('input_params', {})),
                    'input_params': list(m.get('input_params', {}).keys())
                }
                for m in missing_models
            ]
        }
        
        report_file = root_dir / "MODELS_SYNC_REPORT.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 Отчет сохранен в {report_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при синхронизации моделей: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

