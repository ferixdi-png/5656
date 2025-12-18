"""
Модуль для улучшенных уведомлений о процессе генерации и балансе.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


async def send_generation_progress(
    bot,
    chat_id: int,
    task_id: str,
    progress: int,
    total: int,
    status: str = "processing",
    user_lang: str = 'ru'
) -> Optional[Any]:
    """
    Отправляет уведомление о прогрессе генерации.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        task_id: ID задачи
        progress: Текущий прогресс
        total: Общее количество шагов
        status: Статус генерации (queued, processing, completed, error)
        user_lang: Язык пользователя
    """
    try:
        percentage = int((progress / total) * 100) if total > 0 else 0
        
        # Определяем текст статуса
        if status == "queued":
            status_text = "⏳ В очереди" if user_lang == 'ru' else "⏳ Queued"
        elif status == "processing":
            status_text = "🔄 В процессе" if user_lang == 'ru' else "🔄 Processing"
        elif status == "completed":
            status_text = "✅ Завершено" if user_lang == 'ru' else "✅ Completed"
        elif status == "error":
            status_text = "❌ Ошибка" if user_lang == 'ru' else "❌ Error"
        else:
            status_text = "⏳ Ожидание" if user_lang == 'ru' else "⏳ Waiting"
        
        # Создаем индикатор прогресса
        bar_length = 10
        filled = int((percentage / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        message_text = (
            f"📊 <b>Прогресс генерации</b>\n\n"
            f"Task ID: <code>{task_id}</code>\n"
            f"Статус: {status_text}\n\n"
            f"Прогресс: {progress}/{total} ({percentage}%)\n"
            f"{bar}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        ) if user_lang == 'ru' else (
            f"📊 <b>Generation Progress</b>\n\n"
            f"Task ID: <code>{task_id}</code>\n"
            f"Status: {status_text}\n\n"
            f"Progress: {progress}/{total} ({percentage}%)\n"
            f"{bar}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        
        return await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления о прогрессе: {e}", exc_info=True)
        return None


async def send_balance_notification(
    bot,
    chat_id: int,
    user_balance: float,
    required_balance: float,
    user_lang: str = 'ru'
) -> Optional[Any]:
    """
    Отправляет уведомление о балансе пользователя.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        user_balance: Текущий баланс пользователя
        required_balance: Требуемый баланс
        user_lang: Язык пользователя
    """
    try:
        if user_balance >= required_balance:
            message_text = (
                f"💰 <b>Ваш баланс</b>\n\n"
                f"💳 Доступно: <b>{user_balance:.2f}</b> ₽\n"
                f"💵 Требуется: <b>{required_balance:.2f}</b> ₽\n"
                f"✅ Достаточно для генерации"
            ) if user_lang == 'ru' else (
                f"💰 <b>Your Balance</b>\n\n"
                f"💳 Available: <b>{user_balance:.2f}</b> ₽\n"
                f"💵 Required: <b>{required_balance:.2f}</b> ₽\n"
                f"✅ Sufficient for generation"
            )
        else:
            needed = required_balance - user_balance
            message_text = (
                f"⚠️ <b>Недостаточно средств</b>\n\n"
                f"💳 Ваш баланс: <b>{user_balance:.2f}</b> ₽\n"
                f"💵 Требуется: <b>{required_balance:.2f}</b> ₽\n"
                f"❌ Не хватает: <b>{needed:.2f}</b> ₽\n\n"
                f"Пополните баланс для продолжения."
            ) if user_lang == 'ru' else (
                f"⚠️ <b>Insufficient Funds</b>\n\n"
                f"💳 Your balance: <b>{user_balance:.2f}</b> ₽\n"
                f"💵 Required: <b>{required_balance:.2f}</b> ₽\n"
                f"❌ Need: <b>{needed:.2f}</b> ₽\n\n"
                f"Please top up your balance to continue."
            )
        
        return await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления о балансе: {e}", exc_info=True)
        return None


async def send_generation_status_update(
    bot,
    chat_id: int,
    task_id: str,
    status: str,
    message: Optional[str] = None,
    user_lang: str = 'ru'
) -> Optional[Any]:
    """
    Отправляет обновление статуса генерации.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        task_id: ID задачи
        status: Статус (queued, processing, completed, error)
        message: Дополнительное сообщение
        user_lang: Язык пользователя
    """
    try:
        status_icons = {
            'queued': '⏳',
            'processing': '🔄',
            'completed': '✅',
            'error': '❌'
        }
        
        status_texts = {
            'queued': ('В очереди', 'Queued'),
            'processing': ('В процессе', 'Processing'),
            'completed': ('Завершено', 'Completed'),
            'error': ('Ошибка', 'Error')
        }
        
        icon = status_icons.get(status, '⏳')
        status_text = status_texts.get(status, ('Неизвестно', 'Unknown'))[0 if user_lang == 'ru' else 1]
        
        message_text = (
            f"{icon} <b>Статус генерации</b>\n\n"
            f"Task ID: <code>{task_id}</code>\n"
            f"Статус: <b>{status_text}</b>"
        ) if user_lang == 'ru' else (
            f"{icon} <b>Generation Status</b>\n\n"
            f"Task ID: <code>{task_id}</code>\n"
            f"Status: <b>{status_text}</b>"
        )
        
        if message:
            message_text += f"\n\n{message}"
        
        return await bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке обновления статуса: {e}", exc_info=True)
        return None

