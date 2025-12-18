"""
Модуль для работы с историей генераций пользователя.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_user_generation_history(user_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Получает историю генераций пользователя.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество записей
        offset: Смещение для пагинации
    
    Returns:
        Список генераций
    """
    try:
        from database import get_db_connection
        import json
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, model_id, model_name, params, result_urls, 
                           task_id, price, is_free, created_at
                    FROM generations
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, limit, offset))
                
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
        logger.error(f"❌ Ошибка при получении истории генераций для пользователя {user_id}: {e}", exc_info=True)
        return []


def get_generation_by_id(generation_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает генерацию по ID.
    
    Args:
        generation_id: ID генерации
        user_id: ID пользователя
    
    Returns:
        Данные генерации или None
    """
    try:
        from database import get_db_connection
        import json
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, model_id, model_name, params, result_urls, 
                           task_id, price, is_free, created_at
                    FROM generations
                    WHERE id = %s AND user_id = %s
                """, (generation_id, user_id))
                
                row = cur.fetchone()
                
                if not row:
                    return None
                
                return {
                    'id': row[0],
                    'model_id': row[1],
                    'model_name': row[2],
                    'params': row[3] if isinstance(row[3], dict) else json.loads(row[3]) if row[3] else {},
                    'result_urls': row[4] if isinstance(row[4], list) else json.loads(row[4]) if row[4] else [],
                    'task_id': row[5],
                    'price': float(row[6]) if row[6] else 0,
                    'is_free': row[7],
                    'created_at': row[8].isoformat() if row[8] else None
                }
                
    except Exception as e:
        logger.error(f"❌ Ошибка при получении генерации {generation_id}: {e}", exc_info=True)
        return None


def regenerate_from_history(generation_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Пересоздает генерацию из истории.
    
    Args:
        generation_id: ID генерации из истории
        user_id: ID пользователя
    
    Returns:
        Данные новой задачи генерации или None
    """
    generation = get_generation_by_id(generation_id, user_id)
    
    if not generation:
        return None
    
    # Возвращаем параметры для повторной генерации
    return {
        'model_id': generation['model_id'],
        'params': generation['params'],
        'original_generation_id': generation_id
    }

