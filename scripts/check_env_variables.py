#!/usr/bin/env python3
"""
Проверка переменных окружения для деплоя на Render.
Проверяет наличие всех необходимых переменных и их корректность.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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


class EnvVariablesChecker:
    """Класс для проверки переменных окружения."""
    
    def __init__(self):
        self.required_vars = {
            'TELEGRAM_BOT_TOKEN': 'Токен Telegram бота',
            'KIE_API_KEY': 'Ключ API KIE.ai',
            'DATABASE_URL': 'URL базы данных PostgreSQL',
            'ADMIN_ID': 'ID администратора Telegram'
        }
        
        self.optional_vars = {
            'KIE_API_URL': 'URL API KIE.ai (по умолчанию: https://api.kie.ai)',
            'PAYMENT_BANK': 'Детали банка для платежей',
            'PAYMENT_CARD_HOLDER': 'Имя держателя карты',
            'PAYMENT_PHONE': 'Номер телефона для платежей',
            'SUPPORT_TELEGRAM': 'Telegram контакт поддержки',
            'SUPPORT_TEXT': 'Текст поддержки',
            'ALLOW_REAL_GENERATION': 'Разрешить реальные генерации (0/1)',
            'TEST_MODE': 'Тестовый режим (0/1)',
            'DRY_RUN': 'Режим симуляции (0/1)',
            'CREDIT_TO_RUB_RATE': 'Курс кредита к рублю',
            'KIE_TIMEOUT_SECONDS': 'Таймаут запросов к KIE API (секунды)',
            'MAX_CONCURRENT_GENERATIONS_PER_USER': 'Максимум одновременных генераций на пользователя',
            'DB_MAXCONN': 'Максимум соединений с БД'
        }
    
    def check_required_variables(self) -> Tuple[bool, List[str], List[str]]:
        """Проверяет обязательные переменные окружения."""
        missing = []
        present = []
        
        for var_name, description in self.required_vars.items():
            value = os.getenv(var_name)
            if not value:
                missing.append(f"{var_name} - {description}")
            else:
                # Маскируем секретные значения
                if 'KEY' in var_name or 'TOKEN' in var_name or 'URL' in var_name:
                    masked_value = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
                    present.append(f"{var_name} - {description} (значение: {masked_value})")
                else:
                    present.append(f"{var_name} - {description} (значение: {value})")
        
        return len(missing) == 0, missing, present
    
    def check_optional_variables(self) -> Tuple[List[str], List[str]]:
        """Проверяет опциональные переменные окружения."""
        present = []
        missing = []
        
        for var_name, description in self.optional_vars.items():
            value = os.getenv(var_name)
            if value:
                present.append(f"{var_name} - {description}")
            else:
                missing.append(f"{var_name} - {description}")
        
        return present, missing
    
    def check_variable_formats(self) -> List[str]:
        """Проверяет формат переменных окружения."""
        issues = []
        
        # Проверка ADMIN_ID
        admin_id = os.getenv('ADMIN_ID')
        if admin_id:
            try:
                int(admin_id)
            except ValueError:
                issues.append(f"ADMIN_ID должен быть числом, получено: {admin_id}")
        
        # Проверка ALLOW_REAL_GENERATION, TEST_MODE, DRY_RUN
        for var_name in ['ALLOW_REAL_GENERATION', 'TEST_MODE', 'DRY_RUN']:
            value = os.getenv(var_name)
            if value and value not in ['0', '1']:
                issues.append(f"{var_name} должен быть '0' или '1', получено: {value}")
        
        # Проверка CREDIT_TO_RUB_RATE
        credit_rate = os.getenv('CREDIT_TO_RUB_RATE')
        if credit_rate:
            try:
                float(credit_rate)
            except ValueError:
                issues.append(f"CREDIT_TO_RUB_RATE должен быть числом, получено: {credit_rate}")
        
        # Проверка KIE_TIMEOUT_SECONDS
        timeout = os.getenv('KIE_TIMEOUT_SECONDS')
        if timeout:
            try:
                int(timeout)
            except ValueError:
                issues.append(f"KIE_TIMEOUT_SECONDS должен быть числом, получено: {timeout}")
        
        return issues
    
    def print_report(self):
        """Выводит отчёт о переменных окружения."""
        print("\n" + "="*80)
        print("🔐 ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ДЛЯ RENDER")
        print("="*80)
        
        # Проверка обязательных переменных
        print("\n📋 ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ:")
        required_ok, missing, present = self.check_required_variables()
        
        if present:
            print("  ✅ Присутствуют:")
            for var in present:
                print(f"    - {var}")
        
        if missing:
            print("  ❌ Отсутствуют:")
            for var in missing:
                print(f"    - {var}")
        
        # Проверка опциональных переменных
        print("\n📋 ОПЦИОНАЛЬНЫЕ ПЕРЕМЕННЫЕ:")
        optional_present, optional_missing = self.check_optional_variables()
        
        if optional_present:
            print("  ✅ Присутствуют:")
            for var in optional_present:
                print(f"    - {var}")
        
        if optional_missing:
            print("  ℹ️ Отсутствуют (будут использованы значения по умолчанию):")
            for var in optional_missing[:10]:  # Показываем первые 10
                print(f"    - {var}")
            if len(optional_missing) > 10:
                print(f"    ... и ещё {len(optional_missing) - 10}")
        
        # Проверка форматов
        print("\n📋 ПРОВЕРКА ФОРМАТОВ:")
        format_issues = self.check_variable_formats()
        
        if format_issues:
            print("  ❌ Проблемы с форматом:")
            for issue in format_issues:
                print(f"    - {issue}")
        else:
            print("  ✅ Все форматы корректны")
        
        # Итоговый статус
        print("\n" + "="*80)
        if required_ok and not format_issues:
            print("✅ ВСЕ ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ НАСТРОЕНЫ КОРРЕКТНО!")
            print("✅ Проект готов к деплою на Render!")
            return 0
        else:
            print("❌ ЕСТЬ ПРОБЛЕМЫ С ПЕРЕМЕННЫМИ ОКРУЖЕНИЯ!")
            if missing:
                print(f"   Отсутствуют обязательные переменные: {len(missing)}")
            if format_issues:
                print(f"   Проблемы с форматом: {len(format_issues)}")
            return 1


def main():
    """Основная функция."""
    checker = EnvVariablesChecker()
    exit_code = checker.print_report()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

