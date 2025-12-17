"""
Скрипт для инициализации базы данных
Создает все необходимые таблицы и функции
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

from database import init_database, get_database_size

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция инициализации."""
    try:
        logger.info("Инициализация базы данных...")
        
        # Инициализируем БД
        init_database()
        
        logger.info("✅ База данных инициализирована успешно!")
        
        # Показываем размер БД
        db_info = get_database_size()
        if db_info.get('database_size'):
            logger.info(f"📊 Размер БД: {db_info['database_size'].get('db_size', 'N/A')}")
        
        # Показываем таблицы
        if db_info.get('tables'):
            logger.info("📋 Таблицы в БД:")
            for table in db_info['tables']:
                logger.info(f"   - {table['tablename']}: {table['size']}")
        
        return 0
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())


