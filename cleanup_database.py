#!/usr/bin/env python3
"""
Скрипт для очистки базы данных перед новым деплоем на Render.
Удаляет старые записи, чтобы база данных не превышала 1ГБ.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
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


def cleanup_old_generations(days_to_keep: int = 30):
    """
    Удаляет старые генерации из таблицы generations.
    Оставляет только генерации за последние N дней.
    """
    try:
        from database import get_db_connection
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Удаляем старые генерации
                cur.execute(
                    "DELETE FROM generations WHERE created_at < %s",
                    (cutoff_date,)
                )
                deleted_count = cur.rowcount
                logger.info(f"✅ Удалено {deleted_count} старых генераций (старше {days_to_keep} дней)")
                return deleted_count
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке генераций: {e}", exc_info=True)
        return 0


def cleanup_old_operations(days_to_keep: int = 30):
    """
    Удаляет старые операции из таблицы operations.
    Оставляет только операции за последние N дней.
    """
    try:
        from database import get_db_connection
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Удаляем старые операции
                cur.execute(
                    "DELETE FROM operations WHERE created_at < %s",
                    (cutoff_date,)
                )
                deleted_count = cur.rowcount
                logger.info(f"✅ Удалено {deleted_count} старых операций (старше {days_to_keep} дней)")
                return deleted_count
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке операций: {e}", exc_info=True)
        return 0


def cleanup_dry_run_operations():
    """
    Удаляет все DRY_RUN операции (они не нужны в продакшене).
    """
    try:
        from database import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Удаляем все DRY_RUN операции
                cur.execute(
                    "DELETE FROM operations WHERE operation_type = 'dry_run_generation'"
                )
                deleted_count = cur.rowcount
                logger.info(f"✅ Удалено {deleted_count} DRY_RUN операций")
                return deleted_count
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке DRY_RUN операций: {e}", exc_info=True)
        return 0


def get_database_size():
    """
    Получает размер базы данных в байтах.
    """
    try:
        from database import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Получаем размер БД
                cur.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                           pg_database_size(current_database()) as size_bytes
                """)
                result = cur.fetchone()
                if result:
                    return {
                        'size_pretty': result[0],
                        'size_bytes': result[1]
                    }
                return None
    except Exception as e:
        logger.error(f"❌ Ошибка при получении размера БД: {e}", exc_info=True)
        return None


def cleanup_database(days_to_keep: int = 30, remove_dry_run: bool = True):
    """
    Полная очистка базы данных.
    
    Args:
        days_to_keep: Количество дней для хранения данных (по умолчанию 30)
        remove_dry_run: Удалять ли DRY_RUN операции (по умолчанию True)
    """
    logger.info("🧹 Начало очистки базы данных...")
    
    # Получаем размер БД до очистки
    size_before = get_database_size()
    if size_before:
        logger.info(f"📊 Размер БД до очистки: {size_before['size_pretty']}")
    
    # Очищаем старые генерации
    deleted_generations = cleanup_old_generations(days_to_keep)
    
    # Очищаем старые операции
    deleted_operations = cleanup_old_operations(days_to_keep)
    
    # Удаляем DRY_RUN операции
    deleted_dry_run = 0
    if remove_dry_run:
        deleted_dry_run = cleanup_dry_run_operations()
    
    # Получаем размер БД после очистки
    size_after = get_database_size()
    if size_after:
        logger.info(f"📊 Размер БД после очистки: {size_after['size_pretty']}")
        
        # Проверяем, что размер не превышает 1ГБ
        size_gb = size_after['size_bytes'] / (1024 ** 3)
        if size_gb > 1.0:
            logger.warning(f"⚠️ Размер БД превышает 1ГБ: {size_gb:.2f} ГБ")
            logger.warning("⚠️ Рекомендуется уменьшить days_to_keep или выполнить дополнительную очистку")
        else:
            logger.info(f"✅ Размер БД в пределах нормы: {size_gb:.2f} ГБ")
    
    # Итоговая статистика
    total_deleted = deleted_generations + deleted_operations + deleted_dry_run
    logger.info(f"\n📊 Итоговая статистика очистки:")
    logger.info(f"  • Удалено генераций: {deleted_generations}")
    logger.info(f"  • Удалено операций: {deleted_operations}")
    logger.info(f"  • Удалено DRY_RUN операций: {deleted_dry_run}")
    logger.info(f"  • Всего удалено записей: {total_deleted}")
    
    return {
        'deleted_generations': deleted_generations,
        'deleted_operations': deleted_operations,
        'deleted_dry_run': deleted_dry_run,
        'total_deleted': total_deleted,
        'size_before': size_before,
        'size_after': size_after
    }


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Очистка базы данных перед деплоем')
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Количество дней для хранения данных (по умолчанию 30)'
    )
    parser.add_argument(
        '--keep-dry-run',
        action='store_true',
        help='Не удалять DRY_RUN операции'
    )
    parser.add_argument(
        '--check-size-only',
        action='store_true',
        help='Только проверить размер БД, не очищать'
    )
    
    args = parser.parse_args()
    
    if args.check_size_only:
        # Только проверяем размер
        size = get_database_size()
        if size:
            size_gb = size['size_bytes'] / (1024 ** 3)
            logger.info(f"📊 Размер БД: {size['size_pretty']} ({size_gb:.2f} ГБ)")
            if size_gb > 1.0:
                logger.warning(f"⚠️ Размер БД превышает 1ГБ!")
                return 1
            else:
                logger.info("✅ Размер БД в пределах нормы")
                return 0
        else:
            logger.error("❌ Не удалось получить размер БД")
            return 1
    
    # Выполняем очистку
    try:
        result = cleanup_database(
            days_to_keep=args.days,
            remove_dry_run=not args.keep_dry_run
        )
        
        logger.info("\n✅ Очистка базы данных завершена успешно!")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке БД: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
