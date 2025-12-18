#!/usr/bin/env python3
"""
Скрипт для периодической очистки базы данных и кеша.
Можно запускать через cron или как фоновую задачу.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

load_dotenv()

# Настройка логирования
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def periodic_cleanup():
    """Выполняет периодическую очистку БД и кеша."""
    try:
        logger.info("🧹 Начало периодической очистки...")
        
        # 1. Очистка БД
        try:
            from cleanup_database import cleanup_database
            result = cleanup_database(days_to_keep=30, remove_dry_run=True)
            logger.info(f"✅ Очистка БД завершена: удалено {result.get('total_deleted', 0)} записей")
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке БД: {e}", exc_info=True)
        
        # 2. Очистка кеша результатов
        try:
            from optimization_results_cache import clear_old_results
            cleared = clear_old_results()
            logger.info(f"✅ Очистка кеша результатов: удалено {cleared} записей")
        except ImportError:
            logger.warning("⚠️ Модуль optimization_results_cache не доступен")
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке кеша результатов: {e}", exc_info=True)
        
        # 3. Очистка кеша моделей
        try:
            from optimization_cache import clear_old_cache
            clear_old_cache()
            logger.info("✅ Очистка кеша моделей завершена")
        except ImportError:
            logger.warning("⚠️ Модуль optimization_cache не доступен")
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке кеша моделей: {e}", exc_info=True)
        
        # 4. Очистка старых сессий
        try:
            from optimization_helpers import cleanup_old_sessions
            from bot_kie import user_sessions
            cleared = cleanup_old_sessions(user_sessions, max_age_hours=24)
            logger.info(f"✅ Очистка сессий: удалено {cleared} сессий")
        except ImportError:
            logger.warning("⚠️ Модуль optimization_helpers не доступен")
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке сессий: {e}", exc_info=True)
        
        logger.info("✅ Периодическая очистка завершена успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при периодической очистке: {e}", exc_info=True)
        return False


async def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Периодическая очистка БД и кеша')
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Количество дней для хранения данных в БД (по умолчанию 30)'
    )
    
    args = parser.parse_args()
    
    try:
        success = await periodic_cleanup()
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

