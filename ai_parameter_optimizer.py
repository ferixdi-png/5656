"""
Модуль для использования AI для оптимизации параметров генерации.
Анализирует прошлые генерации и предлагает оптимальные параметры.
"""

import logging
from typing import Dict, Any, Optional, List
from collections import Counter
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def analyze_user_preferences(user_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Анализирует предпочтения пользователя на основе истории генераций.
    
    Args:
        user_id: ID пользователя
        days: Количество дней для анализа
    
    Returns:
        Словарь с предпочтениями пользователя
    """
    try:
        from database import get_db_connection
        import json
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cutoff_date = datetime.now() - timedelta(days=days)
                cur.execute("""
                    SELECT model_id, params, price
                    FROM generations
                    WHERE user_id = %s AND created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT 100
                """, (user_id, cutoff_date))
                
                results = cur.fetchall()
                
                if not results:
                    return {
                        'preferred_resolution': None,
                        'preferred_aspect_ratio': None,
                        'preferred_quality': 'medium',
                        'average_price': 0,
                        'most_used_models': []
                    }
                
                # Анализируем параметры
                resolutions = []
                aspect_ratios = []
                prices = []
                models = []
                
                for row in results:
                    model_id, params, price = row
                    models.append(model_id)
                    
                    if price:
                        prices.append(float(price))
                    
                    if params:
                        if isinstance(params, str):
                            try:
                                params = json.loads(params)
                            except:
                                continue
                        
                        if isinstance(params, dict):
                            if 'resolution' in params:
                                resolutions.append(str(params['resolution']))
                            if 'aspect_ratio' in params:
                                aspect_ratios.append(str(params['aspect_ratio']))
                
                # Определяем предпочтения
                preferred_resolution = None
                if resolutions:
                    resolution_counts = Counter(resolutions)
                    preferred_resolution = resolution_counts.most_common(1)[0][0]
                
                preferred_aspect_ratio = None
                if aspect_ratios:
                    aspect_ratio_counts = Counter(aspect_ratios)
                    preferred_aspect_ratio = aspect_ratio_counts.most_common(1)[0][0]
                
                # Определяем предпочтение качества на основе разрешения
                preferred_quality = 'medium'
                if preferred_resolution:
                    if '1080' in preferred_resolution or '4k' in preferred_resolution.lower():
                        preferred_quality = 'high'
                    elif '720' in preferred_resolution:
                        preferred_quality = 'medium'
                    else:
                        preferred_quality = 'low'
                
                # Средняя цена
                average_price = sum(prices) / len(prices) if prices else 0
                
                # Популярные модели
                model_counts = Counter(models)
                most_used_models = [model for model, _ in model_counts.most_common(5)]
                
                return {
                    'preferred_resolution': preferred_resolution,
                    'preferred_aspect_ratio': preferred_aspect_ratio,
                    'preferred_quality': preferred_quality,
                    'average_price': average_price,
                    'most_used_models': most_used_models
                }
                
    except Exception as e:
        logger.error(f"❌ Ошибка при анализе предпочтений пользователя {user_id}: {e}", exc_info=True)
        return {
            'preferred_resolution': None,
            'preferred_aspect_ratio': None,
            'preferred_quality': 'medium',
            'average_price': 0,
            'most_used_models': []
        }


def suggest_optimal_parameters(user_id: int, model_id: str, prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Предлагает оптимальные параметры для генерации на основе AI анализа.
    
    Args:
        user_id: ID пользователя
        model_id: ID модели
        prompt: Текстовый промпт (опционально)
    
    Returns:
        Словарь с рекомендуемыми параметрами
    """
    # Получаем предпочтения пользователя
    preferences = analyze_user_preferences(user_id)
    
    # Базовые рекомендации
    suggested_params = {}
    
    # Применяем предпочтения пользователя
    if preferences.get('preferred_resolution'):
        suggested_params['resolution'] = preferences['preferred_resolution']
    
    if preferences.get('preferred_aspect_ratio'):
        suggested_params['aspect_ratio'] = preferences['preferred_aspect_ratio']
    
    # Определяем качество на основе предпочтений
    quality = preferences.get('preferred_quality', 'medium')
    
    # Анализируем промпт для дополнительных рекомендаций
    if prompt:
        prompt_lower = prompt.lower()
        
        # Если в промпте упоминается качество
        if any(word in prompt_lower for word in ['высокое качество', 'high quality', 'hd', '4k', 'ultra']):
            quality = 'high'
            if 'resolution' not in suggested_params:
                suggested_params['resolution'] = '1080p' if '1080' in prompt_lower else '4k'
        
        # Если упоминается скорость
        if any(word in prompt_lower for word in ['быстро', 'fast', 'quick', 'speed']):
            quality = 'low'
            if 'resolution' not in suggested_params:
                suggested_params['resolution'] = '720p'
    
    # Применяем качество
    if quality == 'high' and 'resolution' not in suggested_params:
        suggested_params['resolution'] = '1080p'
    elif quality == 'medium' and 'resolution' not in suggested_params:
        suggested_params['resolution'] = '720p'
    elif quality == 'low' and 'resolution' not in suggested_params:
        suggested_params['resolution'] = '480p'
    
    # Получаем популярные параметры для модели
    try:
        from request_analytics import get_recommended_parameters
        model_recommended = get_recommended_parameters(model_id)
        
        # Объединяем рекомендации
        for param_name, param_value in model_recommended.items():
            if param_name not in suggested_params:
                suggested_params[param_name] = param_value
    except ImportError:
        pass
    
    return suggested_params


def optimize_parameters_for_model(user_id: int, model_id: str, current_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Оптимизирует параметры для модели на основе предпочтений пользователя.
    
    Args:
        user_id: ID пользователя
        model_id: ID модели
        current_params: Текущие параметры
    
    Returns:
        Оптимизированные параметры
    """
    # Получаем рекомендуемые параметры
    suggested = suggest_optimal_parameters(user_id, model_id)
    
    # Объединяем с текущими параметрами (приоритет у текущих)
    optimized = suggested.copy()
    optimized.update(current_params)
    
    return optimized

