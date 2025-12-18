"""
Модуль для персонализации интерфейса на основе истории взаимодействия пользователя.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)


def get_user_generation_history(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """
    Получает историю генераций пользователя за указанный период.
    
    Args:
        user_id: ID пользователя
        days: Количество дней для анализа
    
    Returns:
        Список генераций
    """
    try:
        from database import get_db_connection
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cutoff_date = datetime.now() - timedelta(days=days)
                cur.execute("""
                    SELECT model_id, params, created_at
                    FROM generations
                    WHERE user_id = %s AND created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT 100
                """, (user_id, cutoff_date))
                
                results = cur.fetchall()
                return [
                    {
                        'model_id': row[0],
                        'params': row[1] if isinstance(row[1], dict) else json.loads(row[1]) if row[1] else {},
                        'created_at': row[2]
                    }
                    for row in results
                ]
    except Exception as e:
        logger.error(f"❌ Ошибка при получении истории генераций для пользователя {user_id}: {e}", exc_info=True)
        return []


def get_user_favorite_models(user_id: int, limit: int = 5) -> List[str]:
    """
    Возвращает список любимых моделей пользователя на основе истории.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество моделей
    
    Returns:
        Список ID моделей
    """
    history = get_user_generation_history(user_id)
    
    if not history:
        return []
    
    # Подсчитываем частоту использования моделей
    model_counts = Counter(item['model_id'] for item in history if item.get('model_id'))
    
    # Возвращаем топ моделей
    return [model_id for model_id, _ in model_counts.most_common(limit)]


def get_user_favorite_parameters(user_id: int, model_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Возвращает любимые параметры пользователя для указанной модели.
    
    Args:
        user_id: ID пользователя
        model_id: ID модели (если None, возвращаются параметры для всех моделей)
    
    Returns:
        Словарь с популярными параметрами
    """
    history = get_user_generation_history(user_id)
    
    if not history:
        return {}
    
    # Фильтруем по модели, если указана
    if model_id:
        history = [item for item in history if item.get('model_id') == model_id]
    
    if not history:
        return {}
    
    # Собираем все параметры
    all_params = {}
    param_counts = {}
    
    for item in history:
        params = item.get('params', {})
        for param_name, param_value in params.items():
            if param_name not in all_params:
                all_params[param_name] = []
                param_counts[param_name] = Counter()
            
            all_params[param_name].append(param_value)
            param_counts[param_name][param_value] += 1
    
    # Возвращаем самые популярные значения для каждого параметра
    favorite_params = {}
    for param_name, counts in param_counts.items():
        most_common = counts.most_common(1)
        if most_common:
            favorite_params[param_name] = most_common[0][0]
    
    return favorite_params


def get_personalized_suggestions(user_id: int, model_id: str) -> Dict[str, Any]:
    """
    Возвращает персонализированные предложения для пользователя.
    
    Args:
        user_id: ID пользователя
        model_id: ID модели
    
    Returns:
        Словарь с предложениями
    """
    suggestions = {
        'favorite_parameters': get_user_favorite_parameters(user_id, model_id),
        'recent_models': get_user_favorite_models(user_id, 3),
        'suggested_parameters': {}
    }
    
    # Получаем популярные параметры для модели
    favorite_params = suggestions['favorite_parameters']
    
    # Если есть любимые параметры, предлагаем их
    if favorite_params:
        suggestions['suggested_parameters'] = favorite_params
    
    return suggestions


def get_recent_generations_reminder(user_id: int, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Возвращает напоминание о недавних генерациях пользователя.
    
    Args:
        user_id: ID пользователя
        limit: Максимальное количество генераций
    
    Returns:
        Список недавних генераций
    """
    history = get_user_generation_history(user_id, days=7)
    
    if not history:
        return []
    
    # Возвращаем последние генерации
    return history[:limit]


def format_personalized_message(user_id: int, model_id: str, lang: str = 'ru') -> str:
    """
    Форматирует персонализированное сообщение для пользователя.
    
    Args:
        user_id: ID пользователя
        model_id: ID модели
        lang: Язык
    
    Returns:
        Персонализированное сообщение
    """
    suggestions = get_personalized_suggestions(user_id, model_id)
    favorite_params = suggestions.get('favorite_parameters', {})
    
    if not favorite_params:
        return ""
    
    if lang == 'ru':
        message = "💡 <b>Ваши любимые параметры:</b>\n\n"
        for param_name, param_value in favorite_params.items():
            message += f"  • {param_name}: <b>{param_value}</b>\n"
        message += "\nМожете использовать их снова или выбрать другие."
    else:
        message = "💡 <b>Your favorite parameters:</b>\n\n"
        for param_name, param_value in favorite_params.items():
            message += f"  • {param_name}: <b>{param_value}</b>\n"
        message += "\nYou can use them again or choose different ones."
    
    return message

