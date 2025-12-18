#!/usr/bin/env python3
"""
Скрипт для проверки логирования и обработки ошибок.
"""

import os
import sys
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


def check_logging_modules():
    """Проверяет модули логирования."""
    logger.info("🔍 Проверка модулей логирования...")
    
    try:
        from logging_optimization import (
            log_optimized,
            log_error_structured,
            log_api_call_optimized,
            should_log_message
        )
        
        logger.info("✅ Модули логирования доступны")
        
        # Тестируем оптимизированное логирование
        log_optimized('INFO', 'Тестовое сообщение')
        logger.info("✅ log_optimized работает")
        
        # Тестируем структурированное логирование ошибок
        try:
            raise ValueError("Тестовая ошибка")
        except Exception as e:
            log_error_structured(e, {'test': 'data'}, user_id=1, operation='test')
        logger.info("✅ log_error_structured работает")
        
        # Тестируем логирование API вызовов
        log_api_call_optimized('test/endpoint', 'GET', 0.5, success=True)
        logger.info("✅ log_api_call_optimized работает")
        
        return True
        
    except ImportError:
        logger.warning("⚠️ Модули логирования не доступны")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке логирования: {e}", exc_info=True)
        return False


def check_error_handling():
    """Проверяет обработку ошибок в bot_kie.py."""
    logger.info("🔍 Проверка обработки ошибок...")
    
    try:
        bot_kie_path = root_dir / "bot_kie.py"
        
        if not bot_kie_path.exists():
            logger.error("❌ Файл bot_kie.py не найден")
            return False
        
        with open(bot_kie_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем наличие глобального обработчика ошибок
        if 'error_handler' in content:
            logger.info("✅ Глобальный обработчик ошибок найден")
        else:
            logger.warning("⚠️ Глобальный обработчик ошибок не найден")
        
        # Проверяем наличие try-except блоков в критических местах
        critical_functions = [
            'confirm_generation',
            'poll_task_status',
            'button_callback',
            'start_command'
        ]
        
        functions_with_error_handling = 0
        for func_name in critical_functions:
            if f'def {func_name}' in content:
                # Ищем try-except в функции
                func_start = content.find(f'def {func_name}')
                if func_start != -1:
                    # Ищем следующий def или конец файла
                    next_def = content.find('\ndef ', func_start + 1)
                    if next_def == -1:
                        func_content = content[func_start:]
                    else:
                        func_content = content[func_start:next_def]
                    
                    if 'try:' in func_content and 'except' in func_content:
                        functions_with_error_handling += 1
                        logger.debug(f"  ✅ {func_name} имеет обработку ошибок")
                    else:
                        logger.warning(f"  ⚠️ {func_name} не имеет обработки ошибок")
        
        if functions_with_error_handling == len(critical_functions):
            logger.info("✅ Все критические функции имеют обработку ошибок")
            return True
        else:
            logger.warning(f"⚠️ Только {functions_with_error_handling}/{len(critical_functions)} функций имеют обработку ошибок")
            return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке обработки ошибок: {e}", exc_info=True)
        return False


def check_logging_levels():
    """Проверяет уровни логирования."""
    logger.info("🔍 Проверка уровней логирования...")
    
    try:
        # Проверяем, что используется правильный уровень логирования
        current_level = logging.getLogger().level
        
        if current_level == logging.INFO or current_level == logging.DEBUG:
            logger.info(f"✅ Уровень логирования: {logging.getLevelName(current_level)}")
            return True
        else:
            logger.warning(f"⚠️ Необычный уровень логирования: {logging.getLevelName(current_level)}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке уровней логирования: {e}", exc_info=True)
        return False


def main():
    """Основная функция проверки."""
    logger.info("🚀 Начало проверки логирования и обработки ошибок...")
    
    results = {
        'logging_modules': False,
        'error_handling': False,
        'logging_levels': False
    }
    
    # Проверка модулей логирования
    results['logging_modules'] = check_logging_modules()
    
    # Проверка обработки ошибок
    results['error_handling'] = check_error_handling()
    
    # Проверка уровней логирования
    results['logging_levels'] = check_logging_levels()
    
    # Итоговый отчет
    logger.info("\n" + "="*60)
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ:")
    logger.info("="*60)
    
    for check_name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info(f"  {check_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✅ Все проверки пройдены успешно!")
        return 0
    else:
        logger.warning("\n⚠️ Некоторые проверки не пройдены")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

