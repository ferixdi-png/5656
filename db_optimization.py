"""
Модуль для оптимизации работы с базой данных.
Включает оптимизированные запросы, автоматическую очистку и управление индексами.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Кеш для часто запрашиваемых данных
_balance_cache: Dict[int, Dict[str, Any]] = {}
_balance_cache_time: Dict[int, float] = {}
BALANCE_CACHE_TTL = 60  # 1 минута


def get_user_balance_optimized(user_id: int, use_cache: bool = True) -> float:
    """
    Оптимизированное получение баланса пользователя с кешированием.
    
    Args:
        user_id: ID пользователя
        use_cache: Использовать ли кеш
    
    Returns:
        Баланс пользователя
    """
    import time
    
    if use_cache:
        current_time = time.time()
        if user_id in _balance_cache:
            cache_data = _balance_cache[user_id]
            cache_time = _balance_cache_time.get(user_id, 0)
            
            if (current_time - cache_time) < BALANCE_CACHE_TTL:
                return cache_data.get('balance', 0.0)
    
    # Получаем из БД
    try:
        from database import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Оптимизированный запрос с использованием индекса
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0) as balance
                    FROM operations
                    WHERE user_id = %s
                """, (user_id,))
                
                result = cur.fetchone()
                balance = float(result[0]) if result else 0.0
                
                # Сохраняем в кеш
                if use_cache:
                    _balance_cache[user_id] = {'balance': balance}
                    _balance_cache_time[user_id] = time.time()
                
                return balance
                
    except Exception as e:
        logger.error(f"❌ Ошибка при получении баланса пользователя {user_id}: {e}", exc_info=True)
        return 0.0


def invalidate_balance_cache(user_id: int):
    """Инвалидирует кеш баланса для пользователя."""
    if user_id in _balance_cache:
        del _balance_cache[user_id]
    if user_id in _balance_cache_time:
        del _balance_cache_time[user_id]


def cleanup_old_sessions_optimized(days_to_keep: int = 7) -> int:
    """
    Оптимизированная очистка старых сессий.
    
    Args:
        days_to_keep: Количество дней для хранения
    
    Returns:
        Количество удаленных записей
    """
    try:
        from database import get_db_connection
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Используем один запрос для удаления
                cur.execute("""
                    DELETE FROM operations
                    WHERE type = 'session' 
                    AND created_at < %s
                """, (cutoff_date,))
                
                deleted_count = cur.rowcount
                conn.commit()
                
                logger.info(f"✅ Удалено {deleted_count} старых сессий")
                return deleted_count
                
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке сессий: {e}", exc_info=True)
        return 0


def cleanup_old_generations_optimized(days_to_keep: int = 90) -> int:
    """
    Оптимизированная очистка старых генераций.
    
    Args:
        days_to_keep: Количество дней для хранения
    
    Returns:
        Количество удаленных записей
    """
    try:
        from database import get_db_connection
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Используем один запрос для удаления
                cur.execute("""
                    DELETE FROM generations
                    WHERE created_at < %s
                """, (cutoff_date,))
                
                deleted_count = cur.rowcount
                conn.commit()
                
                logger.info(f"✅ Удалено {deleted_count} старых генераций")
                return deleted_count
                
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке генераций: {e}", exc_info=True)
        return 0


def get_user_generations_optimized(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Оптимизированное получение генераций пользователя.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество записей
    
    Returns:
        Список генераций
    """
    try:
        from database import get_db_connection
        import json
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Используем индекс для быстрого поиска
                cur.execute("""
                    SELECT id, model_id, model_name, params, result_urls, 
                           task_id, price, is_free, created_at
                    FROM generations
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user_id, limit))
                
                results = cur.fetchall()
                
                generations = []
                for row in results:
                    generations.append({
                        'id': row[0],
                        'model_id': row[1],
                        'model_name': row[2],
                        'params': row[3] if isinstance(row[3], dict) else json.loads(row[3]) if row[3] else {},
                        'result_urls': row[4] if isinstance(row[4], list) else json.loads(row[4]) if row[4] else [],
                        'task_id': row[5],
                        'price': float(row[6]) if row[6] else 0,
                        'is_free': row[7],
                        'created_at': row[8].isoformat() if row[8] else None
                    })
                
                return generations
                
    except Exception as e:
        logger.error(f"❌ Ошибка при получении генераций пользователя {user_id}: {e}", exc_info=True)
        return []


def batch_cleanup_old_data(days_sessions: int = 7, days_generations: int = 90) -> Dict[str, int]:
    """
    Пакетная очистка старых данных.
    
    Args:
        days_sessions: Дни для хранения сессий
        days_generations: Дни для хранения генераций
    
    Returns:
        Словарь с количеством удаленных записей
    """
    sessions_deleted = cleanup_old_sessions_optimized(days_sessions)
    generations_deleted = cleanup_old_generations_optimized(days_generations)
    
    return {
        'sessions_deleted': sessions_deleted,
        'generations_deleted': generations_deleted,
        'total_deleted': sessions_deleted + generations_deleted
    }

