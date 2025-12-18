#!/usr/bin/env python3
"""
Скрипт для проверки всех моделей через KIE API.
Сопоставляет модели из API с моделями в kie_models.py и проверяет наличие необходимых полей.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

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


def check_model_fields(model: Dict[str, Any], source: str = "API") -> Dict[str, bool]:
    """Проверяет наличие необходимых полей в модели."""
    required_fields = {
        'id': 'id' in model and bool(model.get('id')),
        'title': 'title' in model or 'name' in model,
        'input_schema': 'input_schema' in model or 'input_params' in model or 'input' in model,
        'help': 'help' in model or 'description' in model or 'instructions' in model,
    }
    
    return required_fields


def normalize_api_model(api_model: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализует модель из API к формату kie_models.py."""
    normalized = {
        'id': api_model.get('id') or api_model.get('model_id') or api_model.get('name', ''),
        'title': api_model.get('title') or api_model.get('name') or api_model.get('id', ''),
        'name': api_model.get('name') or api_model.get('title') or api_model.get('id', ''),
        'description': api_model.get('description') or api_model.get('help') or api_model.get('instructions', ''),
        'help': api_model.get('help') or api_model.get('description') or api_model.get('instructions', ''),
        'input_schema': api_model.get('input_schema') or api_model.get('input_params') or api_model.get('input') or {},
        'input_params': api_model.get('input_params') or api_model.get('input_schema') or api_model.get('input') or {},
        'category': api_model.get('category') or api_model.get('type') or 'Unknown',
        'generation_type': api_model.get('generation_type') or api_model.get('type') or 'unknown',
        'emoji': api_model.get('emoji') or '✨',
    }
    
    return normalized


async def compare_models():
    """Сопоставляет модели из API с моделями в kie_models.py."""
    # Загружаем модели из API
    api_models = await fetch_models_from_api()
    
    # Получаем модели из кода
    code_models = {model['id']: normalize_model_info(model) for model in KIE_MODELS}
    
    # Создаем словарь для отчетов
    report = {
        'api_models_count': len(api_models),
        'code_models_count': len(code_models),
        'api_models': {},
        'code_models': {},
        'missing_in_code': [],
        'missing_in_api': [],
        'missing_fields': {},
        'recommendations': []
    }
    
    # Нормализуем модели из API
    api_models_normalized = {}
    for api_model in api_models:
        normalized = normalize_api_model(api_model)
        model_id = normalized['id']
        if model_id:
            api_models_normalized[model_id] = normalized
    
    # Проверяем модели из API
    logger.info("\n📊 Проверка моделей из API...")
    for model_id, api_model in api_models_normalized.items():
        fields_check = check_model_fields(api_model, "API")
        report['api_models'][model_id] = {
            'model': api_model,
            'fields_check': fields_check,
            'missing_fields': [field for field, present in fields_check.items() if not present]
        }
        
        # Проверяем, есть ли модель в коде
        if model_id not in code_models:
            report['missing_in_code'].append(model_id)
            report['recommendations'].append(
                f"❌ Модель {model_id} есть в API, но отсутствует в kie_models.py"
            )
    
    # Проверяем модели из кода
    logger.info("\n📊 Проверка моделей из кода...")
    for model_id, code_model in code_models.items():
        fields_check = check_model_fields(code_model, "CODE")
        report['code_models'][model_id] = {
            'model': code_model,
            'fields_check': fields_check,
            'missing_fields': [field for field, present in fields_check.items() if not present]
        }
        
        # Проверяем, есть ли модель в API
        if model_id not in api_models_normalized:
            report['missing_in_api'].append(model_id)
            report['recommendations'].append(
                f"⚠️ Модель {model_id} есть в коде, но отсутствует в API (возможно, недоступна или удалена)"
            )
        
        # Проверяем отсутствующие поля
        missing_fields = report['code_models'][model_id]['missing_fields']
        if missing_fields:
            report['missing_fields'][model_id] = missing_fields
            report['recommendations'].append(
                f"⚠️ Модель {model_id} в коде не имеет полей: {', '.join(missing_fields)}"
            )
    
    return report


def print_report(report: Dict[str, Any]):
    """Выводит отчет о проверке моделей."""
    print("\n" + "="*80)
    print("📊 ОТЧЕТ: Проверка моделей через KIE API")
    print("="*80)
    
    print(f"\n📈 Статистика:")
    print(f"  • Моделей в API: {report['api_models_count']}")
    print(f"  • Моделей в коде: {report['code_models_count']}")
    print(f"  • Моделей из API, отсутствующих в коде: {len(report['missing_in_code'])}")
    print(f"  • Моделей из кода, отсутствующих в API: {len(report['missing_in_api'])}")
    print(f"  • Моделей с отсутствующими полями: {len(report['missing_fields'])}")
    
    # Модели из API, отсутствующие в коде
    if report['missing_in_code']:
        print(f"\n❌ Модели из API, отсутствующие в kie_models.py ({len(report['missing_in_code'])}):")
        for model_id in sorted(report['missing_in_code'])[:20]:  # Показываем первые 20
            api_model = report['api_models'][model_id]['model']
            print(f"  • {model_id}")
            print(f"    - Title: {api_model.get('title') or api_model.get('name', 'N/A')}")
            print(f"    - Category: {api_model.get('category', 'N/A')}")
            if report['api_models'][model_id]['missing_fields']:
                print(f"    - Отсутствующие поля: {', '.join(report['api_models'][model_id]['missing_fields'])}")
        if len(report['missing_in_code']) > 20:
            print(f"  ... и еще {len(report['missing_in_code']) - 20} моделей")
    
    # Модели из кода, отсутствующие в API
    if report['missing_in_api']:
        print(f"\n⚠️ Модели из кода, отсутствующие в API ({len(report['missing_in_api'])}):")
        for model_id in sorted(report['missing_in_api'])[:20]:  # Показываем первые 20
            code_model = report['code_models'][model_id]['model']
            print(f"  • {model_id}")
            print(f"    - Title: {code_model.get('title') or code_model.get('name', 'N/A')}")
            print(f"    - Category: {code_model.get('category', 'N/A')}")
        if len(report['missing_in_api']) > 20:
            print(f"  ... и еще {len(report['missing_in_api']) - 20} моделей")
    
    # Модели с отсутствующими полями
    if report['missing_fields']:
        print(f"\n⚠️ Модели с отсутствующими полями ({len(report['missing_fields'])}):")
        for model_id, missing_fields in sorted(report['missing_fields'].items())[:20]:  # Показываем первые 20
            code_model = report['code_models'][model_id]['model']
            print(f"  • {model_id}")
            print(f"    - Title: {code_model.get('title') or code_model.get('name', 'N/A')}")
            print(f"    - Отсутствующие поля: {', '.join(missing_fields)}")
            
            # Рекомендации по заполнению
            if 'title' in missing_fields:
                print(f"      → Добавить поле 'title' (можно использовать 'name': '{code_model.get('name', 'N/A')}')")
            if 'input_schema' in missing_fields:
                print(f"      → Добавить поле 'input_schema' или 'input_params'")
            if 'help' in missing_fields:
                print(f"      → Добавить поле 'help' (можно использовать 'description': '{code_model.get('description', 'N/A')[:50]}...')")
        if len(report['missing_fields']) > 20:
            print(f"  ... и еще {len(report['missing_fields']) - 20} моделей")
    
    # Рекомендации
    if report['recommendations']:
        print(f"\n💡 Рекомендации ({len(report['recommendations'])}):")
        for i, rec in enumerate(report['recommendations'][:30], 1):  # Показываем первые 30
            print(f"  {i}. {rec}")
        if len(report['recommendations']) > 30:
            print(f"  ... и еще {len(report['recommendations']) - 30} рекомендаций")
    
    # Итоговый статус
    print("\n" + "="*80)
    if not report['missing_in_code'] and not report['missing_fields']:
        print("✅ ВСЕ МОДЕЛИ КОРРЕКТНЫ!")
        print("   Все модели из API присутствуют в коде, все необходимые поля заполнены.")
    elif not report['missing_fields']:
        print("⚠️ ЕСТЬ МОДЕЛИ, ОТСУТСТВУЮЩИЕ В КОДЕ")
        print("   Необходимо добавить модели из API в kie_models.py")
    else:
        print("⚠️ ТРЕБУЮТСЯ ИЗМЕНЕНИЯ")
        print("   Некоторые модели не имеют необходимых полей или отсутствуют в коде.")
    print("="*80 + "\n")


async def main():
    """Основная функция."""
    try:
        report = await compare_models()
        print_report(report)
        
        # Сохраняем отчет в файл
        report_file = root_dir / "MODELS_CHECK_REPORT.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'api_models_count': report['api_models_count'],
                'code_models_count': report['code_models_count'],
                'missing_in_code': report['missing_in_code'],
                'missing_in_api': report['missing_in_api'],
                'missing_fields': report['missing_fields'],
                'recommendations': report['recommendations']
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 Отчет сохранен в {report_file}")
        
        # Возвращаем код выхода
        if not report['missing_in_code'] and not report['missing_fields']:
            return 0
        else:
            return 1
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке моделей: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

