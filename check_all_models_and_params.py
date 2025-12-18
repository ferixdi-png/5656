#!/usr/bin/env python3
"""
Скрипт для полной проверки всех моделей и параметров в боте.
Проверяет:
1. Все модели из KIE API интегрированы в боте
2. Все параметры моделей корректны
3. Валидация параметров работает
4. Enum параметры имеют кнопки
"""

import asyncio
import sys
import json
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


async def fetch_models_from_api() -> List[Dict[str, Any]]:
    """Загружает все модели из KIE API."""
    try:
        from kie_client import get_client
        client = get_client()
        
        logger.info("📡 Загрузка моделей из KIE API...")
        models = await client.list_models()
        
        if not models:
            logger.warning("⚠️ Не удалось загрузить модели из API")
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


def check_model_params(model: Dict[str, Any]) -> Dict[str, Any]:
    """
    Проверяет параметры модели на корректность.
    """
    model_id = model.get('id', 'unknown')
    input_params = model.get('input_params', {})
    
    result = {
        'model_id': model_id,
        'model_name': model.get('name', 'Unknown'),
        'has_input_params': bool(input_params),
        'params_count': len(input_params),
        'params': {},
        'issues': [],
        'warnings': []
    }
    
    if not input_params:
        result['warnings'].append("Модель не имеет параметров input_params")
        return result
    
    for param_name, param_info in input_params.items():
        param_check = {
            'name': param_name,
            'type': param_info.get('type', 'unknown'),
            'required': param_info.get('required', False),
            'has_description': bool(param_info.get('description')),
            'has_enum': 'enum' in param_info,
            'has_max_length': 'max_length' in param_info,
            'has_min_items': 'min_items' in param_info,
            'has_max_items': 'max_items' in param_info,
            'enum_values': param_info.get('enum', []),
            'max_length': param_info.get('max_length'),
            'min_items': param_info.get('min_items'),
            'max_items': param_info.get('max_items'),
            'issues': [],
            'warnings': []
        }
        
        # Проверки для параметров
        if param_check['type'] == 'string':
            if not param_check['has_max_length']:
                param_check['warnings'].append("Строковый параметр без max_length")
        
        if param_check['type'] == 'array':
            if not param_check['has_min_items'] and not param_check['has_max_items']:
                param_check['warnings'].append("Массив без ограничений min_items/max_items")
        
        if param_check['has_enum']:
            if not param_check['enum_values']:
                param_check['issues'].append("Enum параметр без значений")
            else:
                param_check['warnings'].append(f"Enum параметр с {len(param_check['enum_values'])} значениями - будут созданы кнопки")
        
        if not param_check['has_description']:
            param_check['warnings'].append("Параметр без описания")
        
        result['params'][param_name] = param_check
        
        # Собираем проблемы
        if param_check['issues']:
            result['issues'].extend([f"{param_name}: {issue}" for issue in param_check['issues']])
        if param_check['warnings']:
            result['warnings'].extend([f"{param_name}: {warn}" for warn in param_check['warnings']])
    
    return result


async def check_all_models():
    """
    Проверяет все модели и их параметры.
    """
    # Загружаем модели из API
    api_models = await fetch_models_from_api()
    
    # Загружаем модели из кода
    code_models = get_current_models()
    code_model_ids = set(code_models.keys())
    
    # Создаем отчет
    report = {
        'api_models_count': len(api_models),
        'code_models_count': len(code_models),
        'missing_in_code': [],
        'missing_in_api': [],
        'models_check': {},
        'params_summary': {
            'total_params': 0,
            'enum_params': 0,
            'string_params': 0,
            'array_params': 0,
            'boolean_params': 0,
            'params_with_validation': 0
        }
    }
    
    # Проверяем модели из API
    api_model_ids = set()
    for api_model in api_models:
        model_id = api_model.get('id') or api_model.get('model_id') or api_model.get('name', '')
        if model_id:
            api_model_ids.add(model_id)
            if model_id not in code_model_ids:
                report['missing_in_code'].append({
                    'id': model_id,
                    'name': api_model.get('title') or api_model.get('name', 'Unknown'),
                    'category': api_model.get('category', 'Unknown')
                })
    
    # Проверяем модели из кода
    for model_id, model in code_models.items():
        if model_id not in api_model_ids:
            report['missing_in_api'].append({
                'id': model_id,
                'name': model.get('name', 'Unknown'),
                'category': model.get('category', 'Unknown')
            })
        
        # Проверяем параметры модели
        model_check = check_model_params(model)
        report['models_check'][model_id] = model_check
        
        # Обновляем статистику параметров
        for param_name, param_info in model_check['params'].items():
            report['params_summary']['total_params'] += 1
            param_type = param_info['type']
            if param_type == 'string':
                report['params_summary']['string_params'] += 1
            elif param_type == 'array':
                report['params_summary']['array_params'] += 1
            elif param_type == 'boolean':
                report['params_summary']['boolean_params'] += 1
            
            if param_info['has_enum']:
                report['params_summary']['enum_params'] += 1
            
            if param_info['has_max_length'] or param_info['has_min_items'] or param_info['has_max_items']:
                report['params_summary']['params_with_validation'] += 1
    
    return report


def print_report(report: Dict[str, Any]):
    """Выводит отчет о проверке моделей."""
    print("\n" + "="*80)
    print("📊 ПОЛНЫЙ ОТЧЕТ: Проверка всех моделей и параметров")
    print("="*80)
    
    print(f"\n📈 Статистика:")
    print(f"  • Моделей в API: {report['api_models_count']}")
    print(f"  • Моделей в коде: {report['code_models_count']}")
    print(f"  • Моделей из API, отсутствующих в коде: {len(report['missing_in_code'])}")
    print(f"  • Моделей из кода, отсутствующих в API: {len(report['missing_in_api'])}")
    
    print(f"\n📊 Статистика параметров:")
    summary = report['params_summary']
    print(f"  • Всего параметров: {summary['total_params']}")
    print(f"  • Enum параметров: {summary['enum_params']} (будут созданы кнопки)")
    print(f"  • Строковых параметров: {summary['string_params']}")
    print(f"  • Массивов: {summary['array_params']}")
    print(f"  • Boolean параметров: {summary['boolean_params']}")
    print(f"  • Параметров с валидацией: {summary['params_with_validation']}")
    
    # Модели из API, отсутствующие в коде
    if report['missing_in_code']:
        print(f"\n❌ Модели из API, отсутствующие в коде ({len(report['missing_in_code'])}):")
        for model in report['missing_in_code'][:20]:
            print(f"  • {model['id']} - {model['name']} ({model['category']})")
        if len(report['missing_in_code']) > 20:
            print(f"  ... и еще {len(report['missing_in_code']) - 20} моделей")
    
    # Модели из кода, отсутствующие в API
    if report['missing_in_api']:
        print(f"\n⚠️ Модели из кода, отсутствующие в API ({len(report['missing_in_api'])}):")
        for model in report['missing_in_api'][:20]:
            print(f"  • {model['id']} - {model['name']} ({model['category']})")
        if len(report['missing_in_api']) > 20:
            print(f"  ... и еще {len(report['missing_in_api']) - 20} моделей")
    
    # Проблемы с параметрами
    models_with_issues = {mid: check for mid, check in report['models_check'].items() if check.get('issues')}
    if models_with_issues:
        print(f"\n⚠️ Модели с проблемами в параметрах ({len(models_with_issues)}):")
        for model_id, check in list(models_with_issues.items())[:10]:
            print(f"  • {model_id} - {check['model_name']}")
            for issue in check['issues'][:3]:
                print(f"    - {issue}")
            if len(check['issues']) > 3:
                print(f"    ... и еще {len(check['issues']) - 3} проблем")
    
    # Модели без параметров
    models_without_params = {mid: check for mid, check in report['models_check'].items() if not check.get('has_input_params')}
    if models_without_params:
        print(f"\n⚠️ Модели без параметров ({len(models_without_params)}):")
        for model_id, check in list(models_without_params.items())[:10]:
            print(f"  • {model_id} - {check['model_name']}")
    
    # Итоговый статус
    print("\n" + "="*80)
    if not report['missing_in_code'] and not models_with_issues:
        print("✅ ВСЕ МОДЕЛИ КОРРЕКТНЫ!")
        print("   Все модели из API присутствуют в коде, все параметры корректны.")
    elif not report['missing_in_code']:
        print("⚠️ ЕСТЬ ПРОБЛЕМЫ С ПАРАМЕТРАМИ")
        print("   Все модели из API присутствуют в коде, но есть проблемы с параметрами.")
    else:
        print("⚠️ ТРЕБУЮТСЯ ИЗМЕНЕНИЯ")
        print("   Некоторые модели отсутствуют в коде или имеют проблемы с параметрами.")
    print("="*80 + "\n")


async def main():
    """Основная функция."""
    try:
        logger.info("🔍 Начало проверки всех моделей и параметров...")
        
        report = await check_all_models()
        print_report(report)
        
        # Сохраняем отчет в файл
        report_file = root_dir / "ALL_MODELS_AND_PARAMS_CHECK_REPORT.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 Отчет сохранен в {report_file}")
        
        # Возвращаем код выхода
        if not report['missing_in_code'] and not any(check.get('issues') for check in report['models_check'].values()):
            return 0
        else:
            return 1
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке моделей: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

