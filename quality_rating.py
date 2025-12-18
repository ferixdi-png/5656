"""
Модуль для оценки качества генераций.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Файл для хранения оценок
RATINGS_FILE = Path("data/generation_ratings.json")


def save_generation_rating(
    user_id: int,
    generation_id: int,
    rating: int,
    comment: Optional[str] = None
) -> bool:
    """
    Сохраняет оценку качества генерации.
    
    Args:
        user_id: ID пользователя
        generation_id: ID генерации
        rating: Оценка (1-5)
        comment: Комментарий (опционально)
    
    Returns:
        True, если оценка сохранена успешно
    """
    try:
        # Создаем директорию, если не существует
        RATINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем существующие оценки
        if RATINGS_FILE.exists():
            with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
                ratings = json.load(f)
        else:
            ratings = []
        
        # Добавляем новую оценку
        rating_data = {
            'user_id': user_id,
            'generation_id': generation_id,
            'rating': rating,
            'comment': comment,
            'timestamp': datetime.now().isoformat()
        }
        
        ratings.append(rating_data)
        
        # Сохраняем
        with open(RATINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(ratings, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Оценка сохранена для генерации {generation_id} от пользователя {user_id}: {rating}/5")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении оценки: {e}", exc_info=True)
        return False


def get_generation_rating(generation_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает оценку генерации.
    
    Args:
        generation_id: ID генерации
    
    Returns:
        Данные оценки или None
    """
    try:
        if not RATINGS_FILE.exists():
            return None
        
        with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
            ratings = json.load(f)
        
        # Ищем оценку для этой генерации
        for rating in ratings:
            if rating.get('generation_id') == generation_id:
                return rating
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении оценки генерации {generation_id}: {e}", exc_info=True)
        return None


def get_model_average_rating(model_id: str) -> Optional[float]:
    """
    Получает среднюю оценку для модели.
    
    Args:
        model_id: ID модели
    
    Returns:
        Средняя оценка или None
    """
    try:
        if not RATINGS_FILE.exists():
            return None
        
        with open(RATINGS_FILE, 'r', encoding='utf-8') as f:
            ratings = json.load(f)
        
        # Получаем генерации для модели
        from generation_history import get_user_generation_history
        
        model_ratings = []
        for rating in ratings:
            generation_id = rating.get('generation_id')
            if generation_id:
                # Получаем информацию о генерации
                # В реальной реализации здесь будет запрос к БД
                # Пока используем упрощенный подход
                model_ratings.append(rating.get('rating'))
        
        if not model_ratings:
            return None
        
        return sum(model_ratings) / len(model_ratings)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении средней оценки модели {model_id}: {e}", exc_info=True)
        return None

