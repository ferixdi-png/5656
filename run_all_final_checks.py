#!/usr/bin/env python3
"""
Скрипт для запуска всех финальных проверок.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_check(script_name: str, description: str) -> bool:
    """Запускает скрипт проверки."""
    logger.info(f"\n{'='*60}")
    logger.info(f"🔍 {description}")
    logger.info(f"{'='*60}")
    
    script_path = root_dir / script_name
    
    if not script_path.exists():
        logger.error(f"❌ Скрипт {script_name} не найден")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 минут таймаут
        )
        
        # Выводим результат
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        if result.returncode == 0:
            logger.info(f"✅ {description} - ПРОЙДЕН")
            return True
        else:
            logger.warning(f"⚠️ {description} - ПРОВАЛЕН (код: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {description} - ТАЙМАУТ")
        return False
    except Exception as e:
        logger.error(f"❌ {description} - ОШИБКА: {e}")
        return False


def run_tests():
    """Запускает все тесты."""
    logger.info(f"\n{'='*60}")
    logger.info("🧪 Запуск тестов")
    logger.info(f"{'='*60}")
    
    try:
        # Проверяем наличие pytest
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', '--version'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.warning("⚠️ pytest не установлен, пропускаем тесты")
            return True
        
        # Запускаем тесты
        test_env = os.environ.copy()
        test_env['TEST_MODE'] = '1'
        test_env['DRY_RUN'] = '1'
        test_env['ALLOW_REAL_GENERATION'] = '0'
        test_env['TELEGRAM_BOT_TOKEN'] = 'test_token_12345'
        test_env['KIE_API_KEY'] = 'test_api_key'
        test_env['ADMIN_ID'] = '12345'
        
        tests_dir = root_dir / 'tests'
        if not tests_dir.exists():
            logger.warning("⚠️ Директория tests не найдена, пропускаем тесты")
            return True
        
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(tests_dir), '-v', '--tb=short'],
            env=test_env,
            capture_output=True,
            text=True,
            timeout=600  # 10 минут таймаут
        )
        
        # Выводим результат
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        if result.returncode == 0:
            logger.info("✅ Все тесты пройдены")
            return True
        else:
            logger.warning(f"⚠️ Некоторые тесты не пройдены (код: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Тесты - ТАЙМАУТ")
        return False
    except Exception as e:
        logger.error(f"❌ Тесты - ОШИБКА: {e}")
        return False


def main():
    """Основная функция запуска всех проверок."""
    logger.info("🚀 Начало финальной проверки системы...")
    
    checks = [
        ('final_integration_check.py', 'Проверка интеграции с KIE API'),
        ('final_buttons_check.py', 'Проверка кнопок и callback'),
        ('final_database_check.py', 'Проверка базы данных'),
        ('final_balance_check.py', 'Проверка баланса и уведомлений'),
        ('final_logging_check.py', 'Проверка логирования и обработки ошибок'),
    ]
    
    results = {}
    
    # Запускаем все проверки
    for script_name, description in checks:
        results[description] = run_check(script_name, description)
    
    # Запускаем тесты
    results['Тесты'] = run_tests()
    
    # Итоговый отчет
    logger.info(f"\n{'='*60}")
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ:")
    logger.info(f"{'='*60}")
    
    passed = 0
    failed = 0
    
    for check_name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info(f"  {check_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info(f"\n📊 Статистика:")
    logger.info(f"  ✅ Пройдено: {passed}")
    logger.info(f"  ❌ Провалено: {failed}")
    logger.info(f"  📋 Всего: {len(results)}")
    
    if failed == 0:
        logger.info("\n🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
        logger.info("✅ Система готова к тестированию!")
        return 0
    else:
        logger.warning(f"\n⚠️ {failed} проверок не пройдено")
        logger.warning("⚠️ Рекомендуется исправить проблемы перед тестированием")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

