"""
Модуль для анализа частоты запросов и популярных параметров.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)


def analyze_model_popularity(days: int = 30) -> Dict[str, int]:
    """
    Анализирует популярность моделей за указанный период.
    
    Args:
        days: Количество дней для анализа
    
    Returns:
        Словарь {model_id: count}
    """
    try:
        from database import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cutoff_date = datetime.now() - timedelta(days=days)
                cur.execute("""
                    SELECT model_id, COUNT(*) as count
                    FROM generations
                    WHERE created_at >= %s
                    GROUP BY model_id
                    ORDER BY count DESC
                """, (cutoff_date,))
                
                results = cur.fetchall()
                return {row[0]: row[1] for row in results}
                
    except Exception as e:
        logger.error(f"❌ Ошибка при анализе популярности моделей: {e}", exc_info=True)
        return {}


def analyze_parameter_popularity(model_id: str, days: int = 30) -> Dict[str, Dict[str, int]]:
    """
    Анализирует популярность параметров для указанной модели.
    
    Args:
        model_id: ID модели
        days: Количество дней для анализа
    
    Returns:
        Словарь {param_name: {value: count}}
    """
    try:
        from database import get_db_connection
        import json
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cutoff_date = datetime.now() - timedelta(days=days)
                cur.execute("""
                    SELECT params
                    FROM generations
                    WHERE model_id = %s AND created_at >= %s
                """, (model_id, cutoff_date))
                
                results = cur.fetchall()
                
                # Собираем все параметры
                param_values = {}
                
                for row in results:
                    params = row[0]
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except:
                            continue
                    
                    if not isinstance(params, dict):
                        continue
                    
                    for param_name, param_value in params.items():
                        if param_name not in param_values:
                            param_values[param_name] = Counter()
                        param_values[param_name][str(param_value)] += 1
                
                # Преобразуем Counter в обычные словари
                return {
                    param_name: dict(counts)
                    for param_name, counts in param_values.items()
                }
                
    except Exception as e:
        logger.error(f"❌ Ошибка при анализе популярности параметров: {e}", exc_info=True)
        return {}


def get_popular_parameters(model_id: str, limit: int = 3) -> Dict[str, Any]:
    """
    Возвращает самые популярные параметры для модели.
    
    Args:
        model_id: ID модели
        limit: Максимальное количество значений для каждого параметра
    
    Returns:
        Словарь {param_name: [most_popular_values]}
    """
    param_popularity = analyze_parameter_popularity(model_id)
    
    popular_params = {}
    for param_name, value_counts in param_popularity.items():
        # Сортируем по популярности и берем топ значений
        sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
        popular_params[param_name] = [value for value, _ in sorted_values[:limit]]
    
    return popular_params


def get_recommended_parameters(model_id: str) -> Dict[str, Any]:
    """
    Возвращает рекомендуемые параметры для модели на основе популярности.
    
    Args:
        model_id: ID модели
    
    Returns:
        Словарь с рекомендуемыми параметрами
    """
    popular_params = get_popular_parameters(model_id, limit=1)
    
    # Берем самые популярные значения для каждого параметра
    recommended = {}
    for param_name, values in popular_params.items():
        if values:
            recommended[param_name] = values[0]
    
    return recommended


def get_model_usage_stats(model_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Возвращает статистику использования модели.
    
    Args:
        model_id: ID модели
        days: Количество дней для анализа
    
    Returns:
        Словарь со статистикой
    """
    try:
        from database import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cutoff_date = datetime.now() - timedelta(days=days)
                
                # Общее количество использований
                cur.execute("""
                    SELECT COUNT(*) as total
                    FROM generations
                    WHERE model_id = %s AND created_at >= %s
                """, (model_id, cutoff_date))
                total = cur.fetchone()[0]
                
                # Уникальные пользователи
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as unique_users
                    FROM generations
                    WHERE model_id = %s AND created_at >= %s
                """, (model_id, cutoff_date))
                unique_users = cur.fetchone()[0]
                
                # Средняя стоимость
                cur.execute("""
                    SELECT AVG(price) as avg_price
                    FROM generations
                    WHERE model_id = %s AND created_at >= %s AND price > 0
                """, (model_id, cutoff_date))
                avg_price = cur.fetchone()[0] or 0
                
                return {
                    'total_uses': total,
                    'unique_users': unique_users,
                    'average_price': float(avg_price) if avg_price else 0,
                    'period_days': days
                }
                
    except Exception as e:
        logger.error(f"❌ Ошибка при получении статистики использования модели: {e}", exc_info=True)
        return {
            'total_uses': 0,
            'unique_users': 0,
            'average_price': 0,
            'period_days': days
        }

