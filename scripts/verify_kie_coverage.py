#!/usr/bin/env python3
"""
Жёсткая проверка покрытия всех 47 моделей KIE.ai Market.
Проверяет, что ничего не пропущено.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Any

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def load_catalog() -> Dict[str, Any]:
    """Загружает каталог из JSON."""
    catalog_file = root_dir / "data" / "kie_market_catalog.json"
    
    if not catalog_file.exists():
        print(f"❌ Каталог не найден: {catalog_file}")
        print("💡 Запустите сначала: python scripts/kie_market_crawler.py")
        return None
    
    with open(catalog_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_kie_models() -> Dict[str, Any]:
    """Загружает KIE_MODELS из kie_models.py."""
    try:
        import kie_models
        return kie_models.KIE_MODELS
    except Exception as e:
        print(f"❌ Ошибка загрузки kie_models.py: {e}")
        return {}


def verify_coverage(catalog: Dict[str, Any], kie_models: Dict[str, Any]) -> Dict[str, Any]:
    """Проверяет покрытие моделей и modes."""
    
    catalog_data = catalog.get("catalog", {})
    expected_models = set(catalog_data.keys())
    actual_models = set(kie_models.keys())
    
    missing_models = expected_models - actual_models
    extra_models = actual_models - expected_models
    
    # Проверяем modes для каждой модели
    missing_modes = {}
    models_without_schema = {}
    
    for model_id in expected_models:
        if model_id not in kie_models:
            continue
        
        catalog_modes = set(catalog_data[model_id].get("modes", {}).keys())
        actual_modes = set(kie_models[model_id].get("modes", {}).keys())
        
        missing = catalog_modes - actual_modes
        if missing:
            missing_modes[model_id] = list(missing)
        
        # Проверяем input_schema для каждого mode
        for mode_id in actual_modes:
            mode_data = kie_models[model_id]["modes"].get(mode_id, {})
            input_schema = mode_data.get("input_schema", {})
            
            if not input_schema or not isinstance(input_schema, dict):
                if model_id not in models_without_schema:
                    models_without_schema[model_id] = []
                models_without_schema[model_id].append(mode_id)
    
    return {
        "expected_models_count": len(expected_models),
        "actual_models_count": len(actual_models),
        "missing_models": list(missing_models),
        "extra_models": list(extra_models),
        "missing_modes": missing_modes,
        "models_without_schema": models_without_schema,
        "total_expected_modes": sum(len(m.get("modes", {})) for m in catalog_data.values()),
        "total_actual_modes": sum(len(m.get("modes", {})) for m in kie_models.values())
    }


def print_report(report: Dict[str, Any]):
    """Выводит отчёт о покрытии."""
    print("\n" + "="*80)
    print("📊 ПРОВЕРКА ПОКРЫТИЯ KIE.AI MARKET")
    print("="*80)
    
    print(f"\n📋 СТАТИСТИКА:")
    print(f"  Ожидается моделей: {report['expected_models_count']}")
    print(f"  Интегрировано моделей: {report['actual_models_count']}")
    print(f"  Ожидается modes: {report['total_expected_modes']}")
    print(f"  Интегрировано modes: {report['total_actual_modes']}")
    
    if report['missing_models']:
        print(f"\n❌ ОТСУТСТВУЮЩИЕ МОДЕЛИ ({len(report['missing_models'])}):")
        for model_id in report['missing_models']:
            print(f"  - {model_id}")
    
    if report['missing_modes']:
        print(f"\n❌ ОТСУТСТВУЮЩИЕ MODES:")
        for model_id, modes in report['missing_modes'].items():
            print(f"  {model_id}:")
            for mode in modes:
                print(f"    - {mode}")
    
    if report['models_without_schema']:
        print(f"\n⚠️ МОДЕЛИ БЕЗ INPUT_SCHEMA:")
        for model_id, modes in report['models_without_schema'].items():
            print(f"  {model_id}:")
            for mode in modes:
                print(f"    - {mode}")
    
    if report['extra_models']:
        print(f"\n⚠️ ДОПОЛНИТЕЛЬНЫЕ МОДЕЛИ (не в каталоге):")
        for model_id in report['extra_models']:
            print(f"  - {model_id}")
    
    print("\n" + "="*80)
    
    # Итоговый статус
    is_complete = (
        report['expected_models_count'] == report['actual_models_count'] and
        len(report['missing_models']) == 0 and
        len(report['missing_modes']) == 0 and
        len(report['models_without_schema']) == 0
    )
    
    if is_complete:
        print("✅ ВСЕ МОДЕЛИ И MODES ИНТЕГРИРОВАНЫ!")
        return 0
    else:
        print("❌ ЕСТЬ ПРОПУЩЕННЫЕ МОДЕЛИ ИЛИ MODES!")
        return 1


def main():
    """Основная функция."""
    print("🔍 Проверка покрытия KIE.ai Market...")
    
    catalog = load_catalog()
    if not catalog:
        return 1
    
    kie_models = load_kie_models()
    if not kie_models:
        return 1
    
    report = verify_coverage(catalog, kie_models)
    exit_code = print_report(report)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

