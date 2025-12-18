#!/usr/bin/env python3
"""
Проверка переменных окружения для Render.
Убеждается, что все необходимые переменные настроены.
"""

import os
import sys
from pathlib import Path

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


def check_render_env():
    """Проверяет переменные окружения для Render."""
    print("\n" + "="*80)
    print("🔐 ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ДЛЯ RENDER")
    print("="*80)
    
    # Обязательные переменные
    required = {
        'TELEGRAM_BOT_TOKEN': 'Токен Telegram бота',
        'KIE_API_KEY': 'Ключ API KIE.ai',
        'DATABASE_URL': 'URL базы данных PostgreSQL',
        'ADMIN_ID': 'ID администратора Telegram'
    }
    
    # Опциональные переменные
    optional = {
        'KIE_API_URL': 'URL API KIE.ai',
        'PAYMENT_BANK': 'Детали банка',
        'PAYMENT_CARD_HOLDER': 'Имя держателя карты',
        'PAYMENT_PHONE': 'Номер телефона',
        'SUPPORT_TELEGRAM': 'Telegram поддержки',
        'SUPPORT_TEXT': 'Текст поддержки',
        'ALLOW_REAL_GENERATION': 'Разрешить реальные генерации',
        'TEST_MODE': 'Тестовый режим',
        'DRY_RUN': 'Режим симуляции',
        'CREDIT_TO_RUB_RATE': 'Курс кредита к рублю',
        'KIE_TIMEOUT_SECONDS': 'Таймаут запросов',
        'MAX_CONCURRENT_GENERATIONS_PER_USER': 'Максимум генераций',
        'DB_MAXCONN': 'Максимум соединений с БД'
    }
    
    print("\n📋 ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ:")
    missing_required = []
    for var_name, description in required.items():
        value = os.getenv(var_name)
        if value:
            # Маскируем секретные значения
            if 'KEY' in var_name or 'TOKEN' in var_name or 'URL' in var_name:
                masked = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
                print(f"  ✅ {var_name}: {description} (значение: {masked})")
            else:
                print(f"  ✅ {var_name}: {description} (значение: {value})")
        else:
            print(f"  ❌ {var_name}: {description} - ОТСУТСТВУЕТ")
            missing_required.append(var_name)
    
    print("\n📋 ОПЦИОНАЛЬНЫЕ ПЕРЕМЕННЫЕ:")
    for var_name, description in optional.items():
        value = os.getenv(var_name)
        if value:
            print(f"  ✅ {var_name}: {description} (значение: {value})")
        else:
            print(f"  ℹ️ {var_name}: {description} - будет использовано значение по умолчанию")
    
    print("\n" + "="*80)
    if missing_required:
        print(f"❌ ОТСУТСТВУЮТ ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ: {', '.join(missing_required)}")
        print("   Установите их в Render Dashboard → Environment Variables")
        return 1
    else:
        print("✅ ВСЕ ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ НАСТРОЕНЫ!")
        print("✅ Проект готов к деплою на Render!")
        return 0


if __name__ == "__main__":
    sys.exit(check_render_env())

