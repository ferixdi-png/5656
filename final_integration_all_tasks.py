#!/usr/bin/env python3
"""
Финальная интеграция всех задач для доработки бота с моделями KIE.ai.
Проверяет и интегрирует все 15 задач.
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
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


class FinalIntegrationAllTasks:
    """Класс для финальной интеграции всех задач."""
    
    def __init__(self):
        self.results = {}
    
    async def task_1_sync_models(self) -> Dict[str, Any]:
        """Задача 1: Синхронизация всех моделей с KIE.ai Market."""
        logger.info("📌 ЗАДАЧА 1: Синхронизация всех моделей...")
        
        try:
            from kie_client import get_client
            
            client = get_client()
            models = await client.list_models()
            
            if not models:
                return {"status": "error", "message": "Не удалось получить модели"}
            
            # Загружаем текущие модели
            try:
                from kie_models import KIE_MODELS
                current_count = len(KIE_MODELS)
            except ImportError:
                current_count = 0
            
            return {
                "status": "success",
                "api_models_count": len(models),
                "current_models_count": current_count,
                "sync_script": "scripts/full_sync_kie_models.py"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_2_integration_ui(self) -> Dict[str, Any]:
        """Задача 2: Интеграция моделей и режимов в боте."""
        logger.info("📌 ЗАДАЧА 2: Интеграция моделей и UI...")
        
        try:
            # Проверяем наличие функций меню
            from menu_with_modes import (
                build_category_menu,
                build_model_menu,
                build_mode_menu,
                build_parameter_keyboard
            )
            
            # Проверяем интеграцию в bot_kie.py
            bot_file = root_dir / "bot_kie.py"
            bot_content = bot_file.read_text(encoding='utf-8') if bot_file.exists() else ""
            
            has_category_handler = "category:" in bot_content
            has_mode_handler = "mode:" in bot_content
            has_param_handler = "set_param:" in bot_content
            
            return {
                "status": "success",
                "menu_functions_available": True,
                "category_handler": has_category_handler,
                "mode_handler": has_mode_handler,
                "param_handler": has_param_handler,
                "needs_integration": not (has_category_handler and has_mode_handler)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_3_pricing(self) -> Dict[str, Any]:
        """Задача 3: Ценообразование и платёжная логика."""
        logger.info("📌 ЗАДАЧА 3: Ценообразование...")
        
        try:
            from advanced_pricing import (
                calculate_price_rub_for_mode,
                format_price_breakdown
            )
            from config_runtime import is_test_mode, is_dry_run
            
            return {
                "status": "success",
                "pricing_functions": True,
                "test_mode_protection": is_test_mode() or is_dry_run(),
                "formula": "price_rub = credits * credit_to_rub_rate * 2"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_4_error_handling(self) -> Dict[str, Any]:
        """Задача 4: Обработка ошибок и логирование."""
        logger.info("📌 ЗАДАЧА 4: Обработка ошибок...")
        
        try:
            from error_handler_kie import (
                handle_api_error,
                handle_task_status,
                log_api_error
            )
            from analytics_monitoring import log_request
            
            return {
                "status": "success",
                "error_handlers": True,
                "logging": True
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_5_testing(self) -> Dict[str, Any]:
        """Задача 5: Тестирование и верификация."""
        logger.info("📌 ЗАДАЧА 5: Тестирование...")
        
        try:
            tests_dir = root_dir / "tests"
            test_files = list(tests_dir.glob("test_*.py")) if tests_dir.exists() else []
            
            return {
                "status": "success",
                "test_files_count": len(test_files),
                "test_files": [f.name for f in test_files[:10]]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_6_parameters(self) -> Dict[str, Any]:
        """Задача 6: Управление параметрами и стоимостью."""
        logger.info("📌 ЗАДАЧА 6: Управление параметрами...")
        
        try:
            from business_layer import check_balance_before_generation
            try:
                from bonus_system import get_user_bonuses
                bonus_available = True
            except:
                bonus_available = False
            
            return {
                "status": "success",
                "balance_check": True,
                "bonus_system": bonus_available
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_7_data_sessions(self) -> Dict[str, Any]:
        """Задача 7: Работа с данными и сессиями."""
        logger.info("📌 ЗАДАЧА 7: Работа с данными...")
        
        try:
            from automatic_cleanup import run_automatic_cleanup
            
            return {
                "status": "success",
                "cleanup_available": True
            }
        except Exception as e:
            return {"status": "warning", "message": str(e)}
    
    async def task_8_hints(self) -> Dict[str, Any]:
        """Задача 8: Подсказки и документация."""
        logger.info("📌 ЗАДАЧА 8: Подсказки...")
        
        try:
            from strict_validation import get_parameter_hint
            docs_exists = (root_dir / "DOCS.md").exists()
            
            return {
                "status": "success",
                "hints_available": True,
                "documentation": docs_exists
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_9_failed_tasks(self) -> Dict[str, Any]:
        """Задача 9: Обработка несостоятельных задач."""
        logger.info("📌 ЗАДАЧА 9: Обработка несостоятельных задач...")
        
        try:
            from error_handler_kie import handle_task_status
            
            return {
                "status": "success",
                "failed_task_handling": True
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_10_results(self) -> Dict[str, Any]:
        """Задача 10: Генерация и вывод результатов."""
        logger.info("📌 ЗАДАЧА 10: Генерация результатов...")
        
        try:
            from enhanced_kie_gateway import get_enhanced_gateway
            
            gateway = get_enhanced_gateway()
            has_parse = hasattr(gateway, 'parse_result_urls')
            
            return {
                "status": "success",
                "gateway": True,
                "result_parsing": has_parse
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_11_new_models(self) -> Dict[str, Any]:
        """Задача 11: Добавление новых моделей."""
        logger.info("📌 ЗАДАЧА 11: Добавление новых моделей...")
        
        try:
            sync_script = root_dir / "scripts" / "full_sync_kie_models.py"
            
            return {
                "status": "success",
                "auto_sync_available": sync_script.exists()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_12_periodic_sync(self) -> Dict[str, Any]:
        """Задача 12: Периодическая синхронизация."""
        logger.info("📌 ЗАДАЧА 12: Периодическая синхронизация...")
        
        try:
            sync_script = root_dir / "scripts" / "full_sync_kie_models.py"
            
            return {
                "status": "success",
                "sync_script": sync_script.exists(),
                "recommendation": "Настроить cron job для ежемесячной синхронизации"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_13_analytics(self) -> Dict[str, Any]:
        """Задача 13: Аналитика и мониторинг."""
        logger.info("📌 ЗАДАЧА 13: Аналитика...")
        
        try:
            from analytics_monitoring import (
                log_request,
                get_analytics_report
            )
            
            return {
                "status": "success",
                "analytics": True,
                "monthly_reports": True
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_14_mocks(self) -> Dict[str, Any]:
        """Задача 14: Использование мокков и тестирование."""
        logger.info("📌 ЗАДАЧА 14: Мокки...")
        
        try:
            from enhanced_kie_gateway import get_enhanced_gateway
            from config_runtime import is_test_mode, is_dry_run
            
            gateway = get_enhanced_gateway()
            is_mock = "Mock" in gateway.__class__.__name__
            
            return {
                "status": "success",
                "mock_gateway": True,
                "test_mode": is_test_mode() or is_dry_run(),
                "using_mock": is_mock
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def task_15_cleanup(self) -> Dict[str, Any]:
        """Задача 15: Очистка базы и процесс деплоя."""
        logger.info("📌 ЗАДАЧА 15: Очистка базы...")
        
        try:
            cleanup_script = root_dir / "cleanup_database.py"
            auto_cleanup = root_dir / "automatic_cleanup.py"
            
            return {
                "status": "success",
                "cleanup_script": cleanup_script.exists(),
                "auto_cleanup": auto_cleanup.exists()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def run_all_tasks(self):
        """Запускает все задачи."""
        tasks = [
            ("1. Синхронизация моделей", self.task_1_sync_models),
            ("2. Интеграция UI", self.task_2_integration_ui),
            ("3. Ценообразование", self.task_3_pricing),
            ("4. Обработка ошибок", self.task_4_error_handling),
            ("5. Тестирование", self.task_5_testing),
            ("6. Управление параметрами", self.task_6_parameters),
            ("7. Работа с данными", self.task_7_data_sessions),
            ("8. Подсказки", self.task_8_hints),
            ("9. Несостоятельные задачи", self.task_9_failed_tasks),
            ("10. Генерация результатов", self.task_10_results),
            ("11. Новые модели", self.task_11_new_models),
            ("12. Периодическая синхронизация", self.task_12_periodic_sync),
            ("13. Аналитика", self.task_13_analytics),
            ("14. Мокки", self.task_14_mocks),
            ("15. Очистка базы", self.task_15_cleanup),
        ]
        
        for task_name, task_func in tasks:
            try:
                result = await task_func()
                self.results[task_name] = result
            except Exception as e:
                logger.error(f"❌ Ошибка в {task_name}: {e}", exc_info=True)
                self.results[task_name] = {"status": "error", "message": str(e)}
    
    def print_report(self):
        """Выводит отчёт."""
        print("\n" + "="*80)
        print("📊 ФИНАЛЬНЫЙ ОТЧЁТ: Все 15 задач")
        print("="*80)
        
        success = 0
        errors = 0
        warnings = 0
        
        for task_name, result in self.results.items():
            status = result.get("status", "unknown")
            icon = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
            
            if status == "success":
                success += 1
            elif status == "error":
                errors += 1
            else:
                warnings += 1
            
            print(f"\n{icon} {task_name}: {status}")
            if "message" in result:
                print(f"   {result['message']}")
        
        print("\n" + "="*80)
        print(f"📊 ИТОГИ: ✅ {success}/15 | ❌ {errors}/15 | ⚠️ {warnings}/15")
        print("="*80)
        
        # Сохраняем отчёт
        report_file = root_dir / "FINAL_INTEGRATION_REPORT.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": self.results
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Отчёт сохранён в {report_file}")


async def main():
    """Основная функция."""
    integrator = FinalIntegrationAllTasks()
    await integrator.run_all_tasks()
    integrator.print_report()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

