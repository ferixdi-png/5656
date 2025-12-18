#!/usr/bin/env python3
"""
Очистка базы данных перед деплоем на Render.
Удаляет старые сессии, генерации и операции.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

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


def cleanup_before_deploy():
    """Очищает базу данных перед деплоем."""
    logger.info("🧹 Начало очистки БД перед деплоем...")
    
    try:
        from cleanup_database import cleanup_database
        from automatic_cleanup import run_automatic_cleanup
        
        # Очищаем старые данные
        # Сессии старше 7 дней
        # Генерации старше 90 дней
        # Операции старше 30 дней
        
        logger.info("📋 Очистка через automatic_cleanup...")
        cleanup_stats = run_automatic_cleanup(
            days_sessions=7,
            days_generations=90,
            days_operations=30
        )
        
        if not cleanup_stats.get('ok'):
            logger.warning(f"⚠️ Ошибка при автоматической очистке: {cleanup_stats.get('error')}")
        
        logger.info("📋 Очистка через cleanup_database...")
        db_stats = cleanup_database(
            days_to_keep=30,
            remove_dry_run=True
        )
        
        total_deleted = (
            cleanup_stats.get('sessions_deleted', 0) +
            cleanup_stats.get('generations_deleted', 0) +
            cleanup_stats.get('operations_deleted', 0) +
            db_stats.get('total_deleted', 0)
        )
        
        logger.info(f"✅ Очистка завершена: удалено {total_deleted} записей")
        
        # Проверяем размер БД
        try:
            from database import get_db_connection
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database()));
                """)
                db_size = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                
                logger.info(f"📊 Текущий размер БД: {db_size}")
                
                # Предупреждаем если БД слишком большая
                if "MB" in db_size:
                    size_mb = float(db_size.replace(" MB", ""))
                    if size_mb > 500:
                        logger.warning(f"⚠️ БД слишком большая: {db_size}. Рекомендуется дополнительная очистка.")
                elif "GB" in db_size:
                    logger.warning(f"⚠️ БД превышает 1GB: {db_size}. Требуется срочная очистка.")
        
        except Exception as e:
            logger.warning(f"Не удалось проверить размер БД: {e}")
        
        return {
            'ok': True,
            'total_deleted': total_deleted,
            'cleanup_stats': cleanup_stats,
            'db_stats': db_stats
        }
    
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке БД: {e}", exc_info=True)
        return {'ok': False, 'error': str(e)}


def main():
    """Основная функция."""
    print("🧹 Очистка базы данных перед деплоем на Render...")
    
    result = cleanup_before_deploy()
    
    if result.get('ok'):
        print(f"✅ Очистка завершена успешно!")
        print(f"   Удалено записей: {result.get('total_deleted', 0)}")
        return 0
    else:
        print(f"❌ Ошибка при очистке: {result.get('error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

