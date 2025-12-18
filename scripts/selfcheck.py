#!/usr/bin/env python3
"""
Self-check скрипт для проверки конфигурации бота перед деплоем.
Проверяет наличие обязательных env переменных и доступность БД.
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv

load_dotenv()

def mask_secret(value: str, show_first: int = 4, show_last: int = 4) -> str:
    """Маскирует секретное значение."""
    if not value:
        return "not set"
    if len(value) <= show_first + show_last:
        return "***"
    return f"{value[:show_first]}...{value[-show_last:]}"


def check_env_variable(name: str, required: bool = True) -> tuple[bool, str]:
    """Проверяет наличие env переменной."""
    value = os.getenv(name)
    if not value:
        if required:
            return False, f"❌ {name}: не установлен (обязательно)"
        else:
            return True, f"ℹ️  {name}: не установлен (опционально)"
    else:
        masked = mask_secret(value)
        return True, f"✅ {name}: {masked}"


def check_database() -> tuple[bool, str]:
    """Проверяет доступность БД."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return True, "ℹ️  DATABASE_URL: не установлен (будет использоваться JSON fallback)"
    
    try:
        from database import init_database, get_connection_pool
        # Пробуем создать пул
        try:
            pool = get_connection_pool()
            if pool:
                # Пробуем инициализировать схему
                init_database()
                return True, "✅ DATABASE_URL: доступен, схема инициализирована"
            else:
                return False, "❌ DATABASE_URL: пул не создан"
        except Exception as e:
            return False, f"❌ DATABASE_URL: ошибка подключения - {e}"
    except ImportError:
        return True, "ℹ️  database.py: модуль не доступен (будет использоваться JSON fallback)"
    except Exception as e:
        return False, f"❌ DATABASE_URL: ошибка - {e}"


def main():
    """Основная функция проверки."""
    print("🔍 Self-check: проверка конфигурации бота...\n")
    
    errors = []
    warnings = []
    
    # Проверяем обязательные env переменные
    print("📋 Проверка переменных окружения:")
    required_vars = [
        ('TELEGRAM_BOT_TOKEN', True),
        ('KIE_API_KEY', True),
        ('ADMIN_ID', True),
    ]
    
    for var_name, required in required_vars:
        ok, message = check_env_variable(var_name, required)
        print(f"  {message}")
        if not ok:
            errors.append(f"{var_name} не установлен")
    
    # Проверяем DATABASE_URL (опционально, но рекомендуется)
    print("\n🗄️  Проверка базы данных:")
    db_ok, db_message = check_database()
    print(f"  {db_message}")
    if not db_ok:
        warnings.append("База данных недоступна, будет использоваться JSON fallback")
    
    # Итоговый отчет
    print("\n" + "="*50)
    if errors:
        print("❌ Обнаружены ошибки:")
        for error in errors:
            print(f"  - {error}")
        print("\n⚠️  Бот не может быть запущен без исправления этих ошибок.")
        return 1
    elif warnings:
        print("⚠️  Обнаружены предупреждения:")
        for warning in warnings:
            print(f"  - {warning}")
        print("\n✅ Бот может быть запущен, но с ограниченной функциональностью.")
        return 0
    else:
        print("✅ Все проверки пройдены успешно!")
        print("✅ Бот готов к запуску.")
        return 0


if __name__ == '__main__':
    sys.exit(main())

