#!/usr/bin/env python3
"""
Синхронизация kie_models.py из data/kie_market_catalog.json.
Генерирует правильную структуру KIE_MODELS с modes.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def load_catalog() -> Dict[str, Any]:
    """Загружает каталог из JSON."""
    catalog_file = root_dir / "data" / "kie_market_catalog.json"
    
    if not catalog_file.exists():
        raise FileNotFoundError(f"Каталог не найден: {catalog_file}")
    
    with open(catalog_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_kie_models_py(catalog: Dict[str, Any]) -> str:
    """Генерирует код для kie_models.py."""
    
    catalog_data = catalog.get("catalog", {})
    
    lines = [
        '"""',
        'Модели KIE.ai Market.',
        'Автоматически сгенерировано из data/kie_market_catalog.json',
        f'Дата генерации: {datetime.now(timezone.utc).astimezone().isoformat()}',
        '"""',
        '',
        'KIE_MODELS = {'
    ]
    
    for model_id, model_data in sorted(catalog_data.items()):
        title = model_data.get("title", model_id)
        provider = model_data.get("provider", "")
        category = model_data.get("category", "Unknown")
        description = model_data.get("description", "")
        modes = model_data.get("modes", {})
        
        lines.append(f'    "{model_id}": {{')
        lines.append(f'        "title": {json.dumps(title)},')
        lines.append(f'        "provider": {json.dumps(provider)},')
        lines.append(f'        "description": {json.dumps(description)},')
        lines.append(f'        "category": {json.dumps(category)},')
        lines.append('        "modes": {')
        
        for mode_id, mode_data in sorted(modes.items()):
            api_model = mode_data.get("api_model", "")
            generation_type = mode_data.get("generation_type", "")
            mode_title = mode_data.get("title", mode_id)
            input_schema = mode_data.get("input_schema", {})
            help_text = mode_data.get("help", "")
            pricing = mode_data.get("pricing", {})
            
            lines.append(f'            "{mode_id}": {{')
            lines.append(f'                "api_model": {json.dumps(api_model)},')
            lines.append(f'                "generation_type": {json.dumps(generation_type)},')
            lines.append(f'                "title": {json.dumps(mode_title)},')
            lines.append(f'                "input_schema": {json.dumps(input_schema, ensure_ascii=False, indent=20)},')
            lines.append(f'                "help": {json.dumps(help_text)},')
            lines.append(f'                "pricing": {json.dumps(pricing, ensure_ascii=False, indent=20)}')
            lines.append('            },')
        
        lines.append('        }')
        lines.append('    },')
    
    lines.append('}')
    lines.append('')
    
    return '\n'.join(lines)


def main():
    """Основная функция."""
    print("🔄 Синхронизация kie_models.py из каталога...")
    
    try:
        catalog = load_catalog()
        code = generate_kie_models_py(catalog)
        
        # Сохраняем в kie_models.py
        kie_models_file = root_dir / "kie_models.py"
        
        # Делаем backup
        if kie_models_file.exists():
            backup_file = root_dir / "kie_models.py.backup"
            kie_models_file.rename(backup_file)
            print(f"✅ Создан backup: {backup_file}")
        
        kie_models_file.write_text(code, encoding='utf-8')
        print(f"✅ Обновлён {kie_models_file}")
        
        # Статистика
        catalog_data = catalog.get("catalog", {})
        total_models = len(catalog_data)
        total_modes = sum(len(m.get("modes", {})) for m in catalog_data.values())
        
        print(f"\n📊 Статистика:")
        print(f"  Моделей: {total_models}")
        print(f"  Modes: {total_modes}")
        
        return 0
    
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

