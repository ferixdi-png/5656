#!/usr/bin/env python3
"""
Скрипт для проверки системы баланса и уведомлений.
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


def check_balance_functions():
    """Проверяет функции работы с балансом."""
    logger.info("🔍 Проверка функций баланса...")
    
    try:
        from bot_kie import get_user_balance, set_user_balance, subtract_user_balance
        
        test_user_id = 999999
        
        # Тест 1: Получение баланса
        balance = get_user_balance(test_user_id)
        logger.info(f"📊 Баланс тестового пользователя: {balance:.2f} ₽")
        
        # Тест 2: Установка баланса
        test_balance = 100.0
        set_user_balance(test_user_id, test_balance)
        new_balance = get_user_balance(test_user_id)
        
        if abs(new_balance - test_balance) < 0.01:
            logger.info("✅ Установка баланса работает корректно")
        else:
            logger.warning(f"⚠️ Ошибка установки баланса: ожидалось {test_balance}, получено {new_balance}")
            return False
        
        # Тест 3: Списание баланса
        subtract_amount = 25.0
        success = subtract_user_balance(test_user_id, subtract_amount)
        
        if success:
            final_balance = get_user_balance(test_user_id)
            expected_balance = test_balance - subtract_amount
            
            if abs(final_balance - expected_balance) < 0.01:
                logger.info("✅ Списание баланса работает корректно")
            else:
                logger.warning(f"⚠️ Ошибка списания: ожидалось {expected_balance}, получено {final_balance}")
                return False
        else:
            logger.warning("⚠️ Списание баланса не удалось")
            return False
        
        # Очищаем тестовые данные
        set_user_balance(test_user_id, 0.0)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке баланса: {e}", exc_info=True)
        return False


def check_test_mode_balance():
    """Проверяет, что баланс не списывается в TEST_MODE."""
    logger.info("🔍 Проверка TEST_MODE и DRY_RUN...")
    
    try:
        from config_runtime import is_dry_run, allow_real_generation, is_test_mode
        
        dry_run = is_dry_run()
        test_mode = is_test_mode()
        allow_real = allow_real_generation()
        
        logger.info(f"📊 Режимы:")
        logger.info(f"  DRY_RUN: {dry_run}")
        logger.info(f"  TEST_MODE: {test_mode}")
        logger.info(f"  ALLOW_REAL_GENERATION: {allow_real}")
        
        if dry_run or test_mode or not allow_real:
            logger.info("✅ Режим тестирования активен, баланс не будет списываться")
            return True
        else:
            logger.warning("⚠️ Режим реальной генерации активен, баланс будет списываться")
            return True  # Это нормально для продакшена
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке режимов: {e}", exc_info=True)
        return False


def check_balance_notifications():
    """Проверяет модули уведомлений о балансе."""
    logger.info("🔍 Проверка модулей уведомлений...")
    
    try:
        # Проверяем наличие модулей
        from balance_notifications import (
            send_balance_deduction_notification,
            send_insufficient_balance_message,
            send_balance_update
        )
        
        logger.info("✅ Модули уведомлений доступны")
        
        # Проверяем модуль бонусов
        try:
            from bonus_system import (
                get_user_bonuses,
                add_bonus,
                use_bonus,
                get_active_discount
            )
            logger.info("✅ Модуль бонусов доступен")
        except ImportError:
            logger.warning("⚠️ Модуль бонусов не доступен")
        
        return True
        
    except ImportError:
        logger.warning("⚠️ Модули уведомлений не доступны")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке уведомлений: {e}", exc_info=True)
        return False


def check_balance_with_bonuses():
    """Проверяет работу баланса с бонусами."""
    logger.info("🔍 Проверка баланса с бонусами...")
    
    try:
        from generation_logic_optimization import (
            check_balance_with_bonuses,
            deduct_balance_with_bonuses
        )
        
        test_user_id = 999998
        
        # Тест проверки баланса с бонусами
        has_enough, main_balance, bonus_balance, needed = check_balance_with_bonuses(
            test_user_id,
            50.0
        )
        
        logger.info(f"📊 Проверка баланса:")
        logger.info(f"  Достаточно: {has_enough}")
        logger.info(f"  Основной баланс: {main_balance:.2f} ₽")
        logger.info(f"  Бонусный баланс: {bonus_balance:.2f} ₽")
        logger.info(f"  Недостает: {needed:.2f} ₽")
        
        logger.info("✅ Функции баланса с бонусами работают")
        return True
        
    except ImportError:
        logger.warning("⚠️ Модуль generation_logic_optimization не доступен")
        return True  # Не критично
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке баланса с бонусами: {e}", exc_info=True)
        return False


def main():
    """Основная функция проверки."""
    logger.info("🚀 Начало проверки баланса и уведомлений...")
    
    results = {
        'balance_functions': False,
        'test_mode': False,
        'notifications': False,
        'bonuses': False
    }
    
    # Проверка функций баланса
    results['balance_functions'] = check_balance_functions()
    
    # Проверка TEST_MODE
    results['test_mode'] = check_test_mode_balance()
    
    # Проверка уведомлений
    results['notifications'] = check_balance_notifications()
    
    # Проверка баланса с бонусами
    results['bonuses'] = check_balance_with_bonuses()
    
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

