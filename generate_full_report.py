#!/usr/bin/env python3
"""
Генерация полного отчёта о состоянии интеграции KIE.ai.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from datetime import datetime, timezone

root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def generate_full_report() -> Dict[str, Any]:
    """Генерирует полный отчёт о состоянии интеграции."""
    
    report = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "total_models_found": 0,
        "total_modes_processed": 0,
        "missing_models": [],
        "missing_modes": {},
        "invalid_input_schemas": [],
        "pricing_issues_found": [],
        "test_results_summary": "PENDING",
        "api_errors_summary": []
    }
    
    # 1. Анализ моделей
    try:
        from scripts.deep_analyze_kie_models import analyze_all_models, generate_master_catalogue
        
        logger.info("🔍 Анализ моделей...")
        analyzed_data = await analyze_all_models()
        catalogue = generate_master_catalogue(analyzed_data)
        
        report["total_models_found"] = len(catalogue)
        report["total_modes_processed"] = sum(len(m.get("modes", {})) for m in catalogue.values())
        
        # Проверяем отсутствующие модели (ожидается 47)
        expected_models = 47
        if report["total_models_found"] < expected_models:
            report["missing_models"] = [f"Ожидается {expected_models}, найдено {report['total_models_found']}"]
        
        # Проверяем отсутствующие modes
        for model_id, model_data in catalogue.items():
            modes = model_data.get("modes", {})
            if not modes:
                if model_id not in report["missing_modes"]:
                    report["missing_modes"][model_id] = []
                report["missing_modes"][model_id].append("Нет modes")
        
        # Проверяем input_schema
        for model_id, model_data in catalogue.items():
            for mode_key, mode_data_item in model_data.get("modes", {}).items():
                input_schema = mode_data_item.get("input_schema", {})
                
                if not input_schema:
                    report["invalid_input_schemas"].append(f"{model_id}:{mode_key} - отсутствует")
                elif not isinstance(input_schema, dict):
                    report["invalid_input_schemas"].append(f"{model_id}:{mode_key} - не словарь")
                elif "properties" not in input_schema:
                    report["invalid_input_schemas"].append(f"{model_id}:{mode_key} - нет properties")
        
        # Проверяем pricing
        for model_id, model_data in catalogue.items():
            for mode_key, mode_data_item in model_data.get("modes", {}).items():
                pricing = mode_data_item.get("pricing", {})
                
                if not pricing:
                    report["pricing_issues_found"].append(f"{model_id}:{mode_key} - нет pricing")
                elif "credits" not in pricing:
                    report["pricing_issues_found"].append(f"{model_id}:{mode_key} - нет credits")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при анализе моделей: {e}", exc_info=True)
        report["api_errors_summary"].append(f"Ошибка анализа: {str(e)}")
    
    # 2. Проверка тестов
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-v', '--tb=short'],
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ, 'TEST_MODE': '1', 'DRY_RUN': '1', 'ALLOW_REAL_GENERATION': '0'}
        )
        
        if result.returncode == 0:
            report["test_results_summary"] = "PASS"
        else:
            report["test_results_summary"] = f"FAIL (код: {result.returncode})"
            
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить тесты: {e}")
        report["test_results_summary"] = "SKIPPED"
    
    # 3. Аналитика
    try:
        from analytics_monitoring import get_analytics_report
        analytics = get_analytics_report()
        report["analytics"] = analytics
    except Exception as e:
        logger.warning(f"⚠️ Не удалось получить аналитику: {e}")
    
    report["timestamp"] = datetime.now(timezone.utc).astimezone().isoformat()
    
    return report


def print_full_report(report: Dict[str, Any]):
    """Выводит полный отчёт."""
    print("\n" + "="*80)
    print("📊 ПОЛНЫЙ ОТЧЁТ О СОСТОЯНИИ ИНТЕГРАЦИИ KIE.AI")
    print("="*80)
    
    print(f"\n📋 ОСНОВНАЯ СТАТИСТИКА:")
    print(f"  Total models found: {report['total_models_found']}")
    print(f"  Total modes processed: {report['total_modes_processed']}")
    
    print(f"\n❌ ОТСУТСТВУЮЩИЕ МОДЕЛИ:")
    if report['missing_models']:
        for missing in report['missing_models']:
            print(f"  - {missing}")
    else:
        print("  ✅ Все модели присутствуют")
    
    print(f"\n⚠️ ОТСУТСТВУЮЩИЕ MODES:")
    if report['missing_modes']:
        for model_id, modes in report['missing_modes'].items():
            print(f"  {model_id}:")
            for mode in modes:
                print(f"    - {mode}")
    else:
        print("  ✅ Все modes присутствуют")
    
    print(f"\n⚠️ НЕКОРРЕКТНЫЕ INPUT_SCHEMA:")
    if report['invalid_input_schemas']:
        for invalid in report['invalid_input_schemas'][:20]:
            print(f"  - {invalid}")
        if len(report['invalid_input_schemas']) > 20:
            print(f"  ... и еще {len(report['invalid_input_schemas']) - 20}")
    else:
        print("  ✅ Все input_schema корректны")
    
    print(f"\n💰 ПРОБЛЕМЫ С PRICING:")
    if report['pricing_issues_found']:
        for issue in report['pricing_issues_found'][:20]:
            print(f"  - {issue}")
        if len(report['pricing_issues_found']) > 20:
            print(f"  ... и еще {len(report['pricing_issues_found']) - 20}")
    else:
        print("  ✅ Все pricing корректны")
    
    print(f"\n🧪 РЕЗУЛЬТАТЫ ТЕСТОВ:")
    print(f"  {report['test_results_summary']}")
    
    print(f"\n❌ ОШИБКИ API:")
    if report['api_errors_summary']:
        for error in report['api_errors_summary']:
            print(f"  - {error}")
    else:
        print("  ✅ Ошибок API не обнаружено")
    
    print("\n" + "="*80)
    
    # Итоговая оценка
    total_issues = (
        len(report['missing_models']) +
        sum(len(modes) for modes in report['missing_modes'].values()) +
        len(report['invalid_input_schemas']) +
        len(report['pricing_issues_found'])
    )
    
    if total_issues == 0 and report['test_results_summary'] == 'PASS':
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        print("✅ Интеграция идеальна!")
        return 0
    else:
        print(f"⚠️ Обнаружено проблем: {total_issues}")
        return 1


async def main():
    """Основная функция."""
    logger.info("🚀 Генерация полного отчёта...")
    
    report = await generate_full_report()
    exit_code = print_full_report(report)
    
    # Сохраняем отчёт в файл
    report_path = root_dir / "FULL_INTEGRATION_REPORT.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Отчёт сохранен в {report_path}")
    
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

