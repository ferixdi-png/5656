#!/usr/bin/env python3
"""
Финальная проверка перед деплоем на Render.
Проверяет все компоненты системы и готовит проект к деплою.
"""

import os
import sys
import asyncio
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FinalPreDeployCheck:
    """Класс для финальной проверки перед деплоем."""
    
    def __init__(self):
        self.results = {}
        self.errors = []
        self.warnings = []
    
    async def step_1_sync_models(self) -> Tuple[bool, str]:
        """ШАГ 1: Синхронизация моделей с Kie.ai Market."""
        logger.info("📌 ШАГ 1: Синхронизация моделей...")
        
        try:
            # Запускаем crawler для получения всех моделей
            logger.info("📡 Получение моделей из KIE API...")
            crawler_result = subprocess.run(
                [sys.executable, "scripts/kie_market_crawler.py"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if crawler_result.returncode != 0:
                return False, f"Crawler failed: {crawler_result.stderr}"
            
            # Проверяем наличие каталога
            catalog_file = root_dir / "data" / "kie_market_catalog.json"
            if not catalog_file.exists():
                return False, "Каталог не создан"
            
            with open(catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            
            total_models = catalog.get("total_models", 0)
            total_modes = catalog.get("total_modes", 0)
            
            if total_models != 47:
                self.warnings.append(f"Ожидалось 47 моделей, получено {total_models}")
            
            # Синхронизируем kie_models.py
            logger.info("🔄 Синхронизация kie_models.py...")
            sync_result = subprocess.run(
                [sys.executable, "scripts/sync_kie_models_from_catalog.py"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if sync_result.returncode != 0:
                return False, f"Sync failed: {sync_result.stderr}"
            
            # Проверяем покрытие
            logger.info("🔍 Проверка покрытия...")
            coverage_result = subprocess.run(
                [sys.executable, "-m", "scripts.verify_kie_coverage"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if coverage_result.returncode != 0:
                self.warnings.append(f"Покрытие не полное: {coverage_result.stdout}")
            
            return True, f"Моделей: {total_models}, Modes: {total_modes}"
        
        except Exception as e:
            return False, str(e)
    
    def step_2_error_handling(self) -> Tuple[bool, str]:
        """ШАГ 2: Проверка обработки ошибок."""
        logger.info("📌 ШАГ 2: Проверка обработки ошибок...")
        
        try:
            # Проверяем наличие модуля обработки ошибок
            error_handler_file = root_dir / "error_handler_providers.py"
            if not error_handler_file.exists():
                return False, "error_handler_providers.py не найден"
            
            # Проверяем импорт
            try:
                from error_handler_providers import get_error_handler, ErrorSource, ErrorType
                handler = get_error_handler()
                
                # Тестируем обработку ошибок
                user_msg, details = handler.handle_api_error(
                    status_code=500,
                    response_data={"error": "test"},
                    request_details={"test": True}
                )
                
                if not user_msg:
                    return False, "Обработчик ошибок не возвращает сообщение"
                
                return True, "Обработка ошибок работает корректно"
            
            except ImportError as e:
                return False, f"Ошибка импорта: {e}"
        
        except Exception as e:
            return False, str(e)
    
    def step_3_tests(self) -> Tuple[bool, str]:
        """ШАГ 3: Тесты и валидация."""
        logger.info("📌 ШАГ 3: Запуск тестов...")
        
        try:
            # Запускаем тесты
            test_result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=600,
                env={**os.environ, 'TEST_MODE': '1', 'DRY_RUN': '1', 'ALLOW_REAL_GENERATION': '0'}
            )
            
            if test_result.returncode != 0:
                return False, f"Тесты не прошли: {test_result.stdout[-1000:]}"
            
            # Проверяем DRY_RUN
            try:
                from config_runtime import is_dry_run, should_use_mock_gateway
                from kie_gateway import get_kie_gateway
                
                # Устанавливаем DRY_RUN
                os.environ['DRY_RUN'] = '1'
                os.environ['TEST_MODE'] = '1'
                os.environ['ALLOW_REAL_GENERATION'] = '0'
                
                if not should_use_mock_gateway():
                    return False, "DRY_RUN не активирует mock gateway"
                
                gateway = get_kie_gateway()
                if "Mock" not in gateway.__class__.__name__:
                    return False, "Используется не MockKieGateway в DRY_RUN"
                
                return True, f"Тесты прошли успешно. DRY_RUN работает корректно."
            
            except Exception as e:
                return False, f"Ошибка проверки DRY_RUN: {e}"
        
        except Exception as e:
            return False, str(e)
    
    def step_4_logs_reports(self) -> Tuple[bool, str]:
        """ШАГ 4: Обновление логов и отчётов."""
        logger.info("📌 ШАГ 4: Проверка логов и отчётов...")
        
        try:
            # Проверяем наличие скрипта генерации отчёта об ошибках
            error_report_script = root_dir / "scripts" / "generate_error_report.py"
            if not error_report_script.exists():
                return False, "generate_error_report.py не найден"
            
            # Проверяем обработчик ошибок
            try:
                from error_handler_providers import get_error_handler
                handler = get_error_handler()
                report = handler.get_error_report(limit=10)
                
                if "timestamp" not in report:
                    return False, "Отчёт об ошибках не содержит timestamp"
                
                return True, "Логи и отчёты работают корректно"
            
            except ImportError:
                return False, "Обработчик ошибок не импортируется"
        
        except Exception as e:
            return False, str(e)
    
    def step_5_prepare_deploy(self) -> Tuple[bool, str]:
        """ШАГ 5: Приготовление к деплою на Render."""
        logger.info("📌 ШАГ 5: Подготовка к деплою...")
        
        try:
            # Проверяем наличие скрипта очистки БД
            cleanup_script = root_dir / "cleanup_database.py"
            if not cleanup_script.exists():
                self.warnings.append("cleanup_database.py не найден")
            else:
                # Запускаем очистку (в тестовом режиме)
                logger.info("🧹 Очистка старых данных...")
                cleanup_result = subprocess.run(
                    [sys.executable, "cleanup_database.py"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env={**os.environ, 'DRY_RUN': '1'}
                )
                
                if cleanup_result.returncode != 0:
                    self.warnings.append(f"Очистка БД завершилась с ошибкой: {cleanup_result.stderr}")
            
            # Проверяем размер БД (если есть доступ)
            try:
                from database import get_db_connection
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT pg_size_pretty(pg_database_size(current_database()));
                    """)
                    db_size = cursor.fetchone()[0]
                    cursor.close()
                    conn.close()
                    
                    logger.info(f"📊 Размер БД: {db_size}")
                    
                    # Если БД больше 500MB, предупреждаем
                    if "MB" in db_size:
                        size_mb = float(db_size.replace(" MB", ""))
                        if size_mb > 500:
                            self.warnings.append(f"БД слишком большая: {db_size}. Рекомендуется очистка.")
            except Exception as e:
                logger.warning(f"Не удалось проверить размер БД: {e}")
            
            return True, "Подготовка к деплою завершена"
        
        except Exception as e:
            return False, str(e)
    
    def step_6_deploy_files(self) -> Tuple[bool, str]:
        """ШАГ 6: Приготовление файлов для деплоя."""
        logger.info("📌 ШАГ 6: Проверка файлов для деплоя...")
        
        required_files = [
            "config_runtime.py",
            "requirements.txt",
            "bot_kie.py",
            "database.py",
            "kie_gateway.py",
            "kie_client.py",
            "error_handler_providers.py"
        ]
        
        missing_files = []
        for file_name in required_files:
            file_path = root_dir / file_name
            if not file_path.exists():
                missing_files.append(file_name)
        
        if missing_files:
            return False, f"Отсутствуют файлы: {', '.join(missing_files)}"
        
        # Проверяем requirements.txt
        requirements_file = root_dir / "requirements.txt"
        if requirements_file.exists():
            with open(requirements_file, 'r', encoding='utf-8') as f:
                requirements = f.read()
                if 'python-telegram-bot' not in requirements.lower():
                    self.warnings.append("requirements.txt может не содержать все зависимости")
        
        # Проверяем наличие .env.example или README с инструкциями
        readme_file = root_dir / "README.md"
        if not readme_file.exists():
            self.warnings.append("README.md не найден. Рекомендуется создать инструкцию по деплою.")
        
        return True, "Все необходимые файлы присутствуют"
    
    async def run_all_checks(self):
        """Запускает все проверки."""
        checks = [
            ("1. Синхронизация моделей", self.step_1_sync_models),
            ("2. Обработка ошибок", self.step_2_error_handling),
            ("3. Тесты и валидация", self.step_3_tests),
            ("4. Логи и отчёты", self.step_4_logs_reports),
            ("5. Подготовка к деплою", self.step_5_prepare_deploy),
            ("6. Файлы для деплоя", self.step_6_deploy_files),
        ]
        
        for check_name, check_func in checks:
            try:
                if asyncio.iscoroutinefunction(check_func):
                    success, message = await check_func()
                else:
                    success, message = check_func()
                
                self.results[check_name] = {
                    "success": success,
                    "message": message
                }
                
                if not success:
                    self.errors.append(f"{check_name}: {message}")
                elif self.warnings:
                    logger.warning(f"⚠️ {check_name}: {message} (есть предупреждения)")
                else:
                    logger.info(f"✅ {check_name}: {message}")
            
            except Exception as e:
                logger.error(f"❌ Ошибка в {check_name}: {e}", exc_info=True)
                self.results[check_name] = {
                    "success": False,
                    "message": str(e)
                }
                self.errors.append(f"{check_name}: {str(e)}")
    
    def print_report(self):
        """Выводит финальный отчёт."""
        print("\n" + "="*80)
        print("📊 ФИНАЛЬНАЯ ПРОВЕРКА ПЕРЕД ДЕПЛОЕМ НА RENDER")
        print("="*80)
        
        success_count = sum(1 for r in self.results.values() if r.get("success"))
        total_count = len(self.results)
        
        for check_name, result in self.results.items():
            status = result.get("success", False)
            message = result.get("message", "")
            icon = "✅" if status else "❌"
            
            print(f"\n{icon} {check_name}:")
            print(f"   {message}")
        
        if self.warnings:
            print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        if self.errors:
            print(f"\n❌ ОШИБКИ ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
        
        print("\n" + "="*80)
        print(f"📊 ИТОГИ: ✅ {success_count}/{total_count} проверок пройдено")
        
        if len(self.errors) == 0:
            print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Проект готов к деплою.")
            return 0
        else:
            print("❌ ЕСТЬ ОШИБКИ! Исправьте их перед деплоем.")
            return 1


async def main():
    """Основная функция."""
    print("🚀 Начало финальной проверки перед деплоем на Render...")
    
    checker = FinalPreDeployCheck()
    await checker.run_all_checks()
    exit_code = checker.print_report()
    
    # Сохраняем отчёт
    report_file = root_dir / "FINAL_PRE_DEPLOY_REPORT.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "results": checker.results,
            "errors": checker.errors,
            "warnings": checker.warnings
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Отчёт сохранён в {report_file}")
    
    return exit_code


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

