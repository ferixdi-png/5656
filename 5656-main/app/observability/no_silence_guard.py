#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NO-SILENCE GUARD - Критический инвариант
Гарантирует ответ на каждый входящий update

Для каждого апдейта (text/callback/media):
- считает outgoing_actions (send/edit/media)
- после обработки:
  если outgoing_actions == 0 → ОБЯЗАТЕЛЬНО отправляет fallback:
  "Я не смог обработать ввод. Вернитесь в меню."
  + кнопки [Главное меню] [Повторить]

Любой return/except без ответа пользователю = критический баг.
"""

import logging
from typing import Dict, Set, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class NoSilenceGuard:
    """Middleware для гарантии ответа на каждый апдейт"""
    
    def __init__(self):
        self.outgoing_actions: Dict[int, int] = {}  # update_id -> count
        self.processed_updates: Set[int] = set()
    
    def track_outgoing_action(self, update_id: int):
        """Отслеживает исходящее действие (send/edit/media)"""
        if update_id not in self.outgoing_actions:
            self.outgoing_actions[update_id] = 0
        self.outgoing_actions[update_id] += 1
        logger.debug(f"📤 Tracked outgoing action for update {update_id}, total: {self.outgoing_actions[update_id]}")
    
    def mark_update_processed(self, update_id: int):
        """Отмечает апдейт как обработанный"""
        self.processed_updates.add(update_id)
    
    async def check_and_ensure_response(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        handler_result: Optional[any] = None
    ) -> bool:
        """
        Проверяет что был ответ на апдейт, если нет - отправляет fallback
        
        Returns:
            True если был ответ, False если отправлен fallback
        """
        update_id = update.update_id
        
        # Проверяем количество исходящих действий
        outgoing_count = self.outgoing_actions.get(update_id, 0)
        
        # Если был хотя бы один ответ - всё ОК
        if outgoing_count > 0:
            logger.debug(f"✅ Update {update_id} has {outgoing_count} responses, OK")
            self.mark_update_processed(update_id)
            return True
        
        # НЕТ ОТВЕТА - критический баг!
        logger.warning(f"⚠️⚠️⚠️ NO-SILENCE VIOLATION: Update {update_id} has NO responses!")
        
        # Определяем тип апдейта и получаем chat_id
        chat_id = None
        user_id = None
        
        if update.message:
            chat_id = update.message.chat_id
            user_id = update.message.from_user.id if update.message.from_user else None
        elif update.callback_query:
            chat_id = update.callback_query.message.chat_id if update.callback_query.message else None
            user_id = update.callback_query.from_user.id if update.callback_query.from_user else None
        elif update.edited_message:
            chat_id = update.edited_message.chat_id
            user_id = update.edited_message.from_user.id if update.edited_message.from_user else None
        
        if not chat_id:
            logger.error(f"❌ Cannot determine chat_id for update {update_id}, cannot send fallback")
            return False
        
        # Отправляем fallback сообщение
        try:
            # Определяем язык пользователя (если доступно)
            user_lang = 'ru'  # Default
            try:
                from app.state.user_state import get_user_language
                if user_id:
                    user_lang = get_user_language(user_id)
            except:
                pass
            
            # Текст сообщения
            if user_lang == 'en':
                fallback_text = (
                    "⚠️ <b>I couldn't process your input.</b>\n\n"
                    "Please return to the main menu and try again."
                )
                btn_home_text = "🏠 Main Menu"
                btn_retry_text = "🔄 Try Again"
            else:
                fallback_text = (
                    "💡 <b>Выберите действие из меню</b>\n\n"
                    "Чтобы продолжить:\n"
                    "• Нажмите кнопку в главном меню\n"
                    "• Или выберите модель для генерации\n\n"
                    "Я помогу вам на каждом шаге ✨"
                )
                btn_home_text = "🏠 Главное меню"
                btn_retry_text = "🔄 Повторить"
            
            keyboard = [
                [InlineKeyboardButton(btn_home_text, callback_data="back_to_menu")],
                [InlineKeyboardButton(btn_retry_text, callback_data="back_to_menu")]
            ]
            
            # Отправляем fallback
            if update.callback_query:
                # Для callback - отвечаем на query и отправляем сообщение
                try:
                    await update.callback_query.answer()
                except:
                    pass
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=fallback_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            else:
                # Для message - отправляем reply
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=fallback_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            
            # Отслеживаем это действие
            self.track_outgoing_action(update_id)
            self.mark_update_processed(update_id)
            
            logger.info(f"✅ NO-SILENCE GUARD: Sent fallback response for update {update_id}")
            return False  # Был отправлен fallback, не был естественный ответ
            
        except Exception as e:
            logger.error(f"❌ Failed to send NO-SILENCE fallback for update {update_id}: {e}", exc_info=True)
            return False
    
    def cleanup(self, update_id: int):
        """Очищает данные для апдейта после обработки"""
        if update_id in self.outgoing_actions:
            del self.outgoing_actions[update_id]
        if update_id in self.processed_updates:
            self.processed_updates.remove(update_id)


# Глобальный экземпляр
_no_silence_guard = None


def get_no_silence_guard() -> NoSilenceGuard:
    """Получает глобальный экземпляр NO-SILENCE GUARD"""
    global _no_silence_guard
    if _no_silence_guard is None:
        _no_silence_guard = NoSilenceGuard()
    return _no_silence_guard


def track_outgoing_action(update_id: int):
    """Удобная функция для отслеживания исходящего действия"""
    guard = get_no_silence_guard()
    guard.track_outgoing_action(update_id)






