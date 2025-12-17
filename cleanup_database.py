"""
Скрипт для очистки старых данных из БД
Запускается через cron или вручную
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

from database import cleanup_old_logs, get_database_size, init_database

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция очистки."""
    try:
        # Инициализируем БД (создаем таблицы если нужно)
        init_database()
        
        # Получаем количество дней для хранения (по умолчанию 30)
        days_to_keep = int(os.getenv('LOG_RETENTION_DAYS', '30'))
        
        logger.info(f"Начинаем очистку логов старше {days_to_keep} дней...")
        
        # Очищаем старые логи
        result = cleanup_old_logs(days_to_keep)
        
        logger.info(f"✅ Очистка завершена:")
        logger.info(f"   - Удалено KIE логов: {result['deleted_kie_logs']}")
        logger.info(f"   - Удалено debug логов: {result['deleted_debug_logs']}")
        
        # Показываем размер БД
        db_info = get_database_size()
        if db_info.get('database_size'):
            logger.info(f"📊 Размер БД: {db_info['database_size'].get('db_size', 'N/A')}")
        
        return 0
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())


