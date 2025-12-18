"""
Модуль для автоматической очистки базы данных.
Запускается периодически для удаления старых данных.
"""

import logging
import asyncio
from typing import Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def run_automatic_cleanup(
    days_sessions: int = 7,
    days_generations: int = 90,
    days_operations: int = 30
) -> Dict[str, Any]:
    """
    Запускает автоматическую очистку базы данных.
    
    Args:
        days_sessions: Дни для хранения сессий
        days_generations: Дни для хранения генераций
        days_operations: Дни для хранения операций
    
    Returns:
        Словарь со статистикой очистки
    """
    try:
        from db_optimization import batch_cleanup_old_data
        from cleanup_database import cleanup_database
        
        logger.info("🧹 Начало автоматической очистки БД...")
        
        # Очистка через оптимизированные функции
        cleanup_stats = batch_cleanup_old_data(days_sessions, days_generations)
        
        # Очистка операций
        operations_stats = cleanup_database(days_to_keep=days_operations, remove_dry_run=True)
        
        total_deleted = (
            cleanup_stats.get('sessions_deleted', 0) +
            cleanup_stats.get('generations_deleted', 0) +
            operations_stats.get('total_deleted', 0)
        )
        
        logger.info(f"✅ Автоматическая очистка завершена: удалено {total_deleted} записей")
        
        return {
            'sessions_deleted': cleanup_stats.get('sessions_deleted', 0),
            'generations_deleted': cleanup_stats.get('generations_deleted', 0),
            'operations_deleted': operations_stats.get('total_deleted', 0),
            'total_deleted': total_deleted,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при автоматической очистке: {e}", exc_info=True)
        return {
            'sessions_deleted': 0,
            'generations_deleted': 0,
            'operations_deleted': 0,
            'total_deleted': 0,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


async def start_periodic_cleanup(
    interval_hours: int = 24,
    days_sessions: int = 7,
    days_generations: int = 90
):
    """
    Запускает периодическую очистку в фоновом режиме.
    
    Args:
        interval_hours: Интервал между очистками в часах
        days_sessions: Дни для хранения сессий
        days_generations: Дни для хранения генераций
    """
    while True:
        try:
            await asyncio.sleep(interval_hours * 3600)
            await run_automatic_cleanup(days_sessions, days_generations)
        except asyncio.CancelledError:
            logger.info("🛑 Периодическая очистка остановлена")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в периодической очистке: {e}", exc_info=True)
            # Продолжаем работу даже при ошибке
            await asyncio.sleep(3600)  # Ждем час перед следующей попыткой

