"""
Модуль для системы обратной связи от пользователей.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Файл для хранения отзывов
FEEDBACK_FILE = Path("data/feedback.json")


def save_feedback(user_id: int, feedback_type: str, message: str, rating: Optional[int] = None) -> bool:
    """
    Сохраняет отзыв пользователя.
    
    Args:
        user_id: ID пользователя
        feedback_type: Тип отзыва (generation, bot, feature, bug)
        message: Текст отзыва
        rating: Оценка (1-5, опционально)
    
    Returns:
        True, если отзыв сохранен успешно
    """
    try:
        # Создаем директорию, если не существует
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем существующие отзывы
        if FEEDBACK_FILE.exists():
            with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                feedbacks = json.load(f)
        else:
            feedbacks = []
        
        # Добавляем новый отзыв
        feedback = {
            'user_id': user_id,
            'feedback_type': feedback_type,
            'message': message,
            'rating': rating,
            'timestamp': datetime.now().isoformat()
        }
        
        feedbacks.append(feedback)
        
        # Сохраняем
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(feedbacks, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Отзыв сохранен от пользователя {user_id}: {feedback_type}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении отзыва: {e}", exc_info=True)
        return False


def get_feedback_stats() -> Dict[str, Any]:
    """
    Возвращает статистику по отзывам.
    
    Returns:
        Словарь со статистикой
    """
    try:
        if not FEEDBACK_FILE.exists():
            return {
                'total': 0,
                'by_type': {},
                'average_rating': 0,
                'recent_count': 0
            }
        
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            feedbacks = json.load(f)
        
        if not feedbacks:
            return {
                'total': 0,
                'by_type': {},
                'average_rating': 0,
                'recent_count': 0
            }
        
        # Статистика по типам
        from collections import Counter
        type_counts = Counter(f['feedback_type'] for f in feedbacks)
        
        # Средняя оценка
        ratings = [f['rating'] for f in feedbacks if f.get('rating')]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        # Недавние отзывы (за последние 7 дней)
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=7)
        recent = [
            f for f in feedbacks
            if datetime.fromisoformat(f['timestamp']) >= cutoff
        ]
        
        return {
            'total': len(feedbacks),
            'by_type': dict(type_counts),
            'average_rating': round(avg_rating, 2),
            'recent_count': len(recent)
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении статистики отзывов: {e}", exc_info=True)
        return {
            'total': 0,
            'by_type': {},
            'average_rating': 0,
            'recent_count': 0
        }


def get_negative_feedback() -> List[Dict[str, Any]]:
    """
    Возвращает список негативных отзывов (оценка <= 2).
    
    Returns:
        Список негативных отзывов
    """
    try:
        if not FEEDBACK_FILE.exists():
            return []
        
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            feedbacks = json.load(f)
        
        negative = [
            f for f in feedbacks
            if f.get('rating') is not None and f.get('rating') <= 2
        ]
        
        # Сортируем по дате (новые первыми)
        negative.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return negative
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении негативных отзывов: {e}", exc_info=True)
        return []


async def send_feedback_request(bot, chat_id: int, generation_id: Optional[str] = None, lang: str = 'ru') -> Optional[Any]:
    """
    Отправляет запрос на обратную связь пользователю.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        generation_id: ID генерации (опционально)
        lang: Язык
    
    Returns:
        Сообщение бота или None
    """
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        if lang == 'ru':
            message_text = (
                "💬 <b>Обратная связь</b>\n\n"
                "Помогите нам улучшить бота! Оставьте отзыв о генерации или работе бота."
            )
            buttons = [
                [
                    InlineKeyboardButton("✅ Отлично (5)", callback_data=f"feedback:rating:5:{generation_id or ''}"),
                    InlineKeyboardButton("👍 Хорошо (4)", callback_data=f"feedback:rating:4:{generation_id or ''}")
                ],
                [
                    InlineKeyboardButton("😐 Нормально (3)", callback_data=f"feedback:rating:3:{generation_id or ''}"),
                    InlineKeyboardButton("👎 Плохо (2)", callback_data=f"feedback:rating:2:{generation_id or ''}")
                ],
                [
                    InlineKeyboardButton("❌ Очень плохо (1)", callback_data=f"feedback:rating:1:{generation_id or ''}")
                ],
                [
                    InlineKeyboardButton("💬 Текстовый отзыв", callback_data=f"feedback:text:{generation_id or ''}")
                ],
                [
                    InlineKeyboardButton("⏭️ Пропустить", callback_data="feedback:skip")
                ]
            ]
        else:
            message_text = (
                "💬 <b>Feedback</b>\n\n"
                "Help us improve the bot! Leave feedback about the generation or bot work."
            )
            buttons = [
                [
                    InlineKeyboardButton("✅ Excellent (5)", callback_data=f"feedback:rating:5:{generation_id or ''}"),
                    InlineKeyboardButton("👍 Good (4)", callback_data=f"feedback:rating:4:{generation_id or ''}")
                ],
                [
                    InlineKeyboardButton("😐 OK (3)", callback_data=f"feedback:rating:3:{generation_id or ''}"),
                    InlineKeyboardButton("👎 Bad (2)", callback_data=f"feedback:rating:2:{generation_id or ''}")
                ],
                [
                    InlineKeyboardButton("❌ Very Bad (1)", callback_data=f"feedback:rating:1:{generation_id or ''}")
                ],
                [
                    InlineKeyboardButton("💬 Text Feedback", callback_data=f"feedback:text:{generation_id or ''}")
                ],
                [
                    InlineKeyboardButton("⏭️ Skip", callback_data="feedback:skip")
                ]
            ]
        
        return await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке запроса на обратную связь: {e}", exc_info=True)
        return None

