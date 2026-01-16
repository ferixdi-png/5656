"""
Test harness для python-telegram-bot.
Позволяет тестировать handlers без реальных запросов к Telegram API.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message, User, Chat, CallbackQuery, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes
from telegram.constants import ChatType

logger = logging.getLogger(__name__)


class MessageOutbox:
    """Хранилище отправленных сообщений для проверки в тестах."""
    
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.edited_messages: List[Dict[str, Any]] = []
        self.callback_answers: List[Dict[str, Any]] = []
    
    def clear(self):
        """Очищает outbox."""
        self.messages.clear()
        self.edited_messages.clear()
        self.callback_answers.clear()
    
    def get_last_message(self) -> Optional[Dict[str, Any]]:
        """Возвращает последнее отправленное сообщение."""
        return self.messages[-1] if self.messages else None
    
    def get_last_edited_message(self) -> Optional[Dict[str, Any]]:
        """Возвращает последнее отредактированное сообщение."""
        return self.edited_messages[-1] if self.edited_messages else None


class PTBHarness:
    """
    Test harness для python-telegram-bot.
    Создает Application как в bot_kie.py, но перехватывает все отправки.
    """
    
    def __init__(self, bot_token: str = "test_token_12345"):
        self.bot_token = bot_token
        self.application: Optional[Application] = None
        self.outbox = MessageOutbox()
        self._patches: List[Any] = []
    
    async def setup(self):
        """Инициализирует Application и настраивает моки."""
        # Создаем Application
        self.application = Application.builder().token(self.bot_token).build()
        
        # Мокаем bot.send_message
        async def mock_send_message(chat_id, text, **kwargs):
            self.outbox.messages.append({
                'chat_id': chat_id,
                'text': text,
                'parse_mode': kwargs.get('parse_mode'),
                'reply_markup': kwargs.get('reply_markup'),
                **kwargs
            })
            # Возвращаем моковое сообщение
            mock_msg = MagicMock(spec=Message)
            mock_msg.chat_id = chat_id
            mock_msg.text = text
            mock_msg.reply_markup = kwargs.get('reply_markup')
            return mock_msg
        
        # Мокаем bot.edit_message_text
        async def mock_edit_message_text(chat_id=None, message_id=None, text=None, **kwargs):
            self.outbox.edited_messages.append({
                'chat_id': chat_id,
                'message_id': message_id,
                'text': text,
                'parse_mode': kwargs.get('parse_mode'),
                'reply_markup': kwargs.get('reply_markup'),
                **kwargs
            })
            # Возвращаем моковое сообщение
            mock_msg = MagicMock(spec=Message)
            mock_msg.chat_id = chat_id
            mock_msg.text = text
            mock_msg.reply_markup = kwargs.get('reply_markup')
            return mock_msg
        
        # Мокаем bot.answer_callback_query
        async def mock_answer_callback_query(callback_query_id, text=None, show_alert=False, **kwargs):
            self.outbox.callback_answers.append({
                'callback_query_id': callback_query_id,
                'text': text,
                'show_alert': show_alert,
                **kwargs
            })
            return True
        
        # Применяем моки
        self.application.bot.send_message = AsyncMock(side_effect=mock_send_message)
        self.application.bot.edit_message_text = AsyncMock(side_effect=mock_edit_message_text)
        self.application.bot.answer_callback_query = AsyncMock(side_effect=mock_answer_callback_query)
    
    async def teardown(self):
        """Очищает ресурсы."""
        if self.application:
            await self.application.shutdown()
        self.outbox.clear()
        for patch_obj in self._patches:
            patch_obj.stop()
        self._patches.clear()
    
    def create_mock_user(self, user_id: int = 12345, username: str = "test_user") -> User:
        """Создает мокового пользователя."""
        return User(
            id=user_id,
            is_bot=False,
            first_name="Test",
            username=username
        )
    
    def create_mock_chat(self, chat_id: int = 12345, chat_type: str = ChatType.PRIVATE) -> Chat:
        """Создает моковый чат."""
        return Chat(
            id=chat_id,
            type=chat_type
        )
    
    def create_mock_message(self, text: str = "/start", user_id: int = 12345, chat_id: int = 12345) -> Message:
        """Создает моковое сообщение."""
        user = self.create_mock_user(user_id)
        chat = self.create_mock_chat(chat_id)
        return Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user,
            text=text
        )
    
    def create_mock_callback_query(
        self,
        data: str,
        user_id: int = 12345,
        chat_id: int = 12345,
        message_id: int = 1
    ) -> CallbackQuery:
        """Создает моковый callback query."""
        user = self.create_mock_user(user_id)
        chat = self.create_mock_chat(chat_id)
        message = Message(
            message_id=message_id,
            date=None,
            chat=chat,
            from_user=user
        )
        return CallbackQuery(
            id="test_callback_id",
            from_user=user,
            chat_instance="test_instance",
            data=data,
            message=message
        )
    
    def create_mock_update_command(self, command: str = "/start", user_id: int = 12345) -> Update:
        """Создает моковый Update для команды."""
        message = self.create_mock_message(text=command, user_id=user_id)
        return Update(update_id=1, message=message)
    
    def create_mock_update_callback(self, callback_data: str, user_id: int = 12345) -> Update:
        """Создает моковый Update для callback."""
        callback_query = self.create_mock_callback_query(callback_data, user_id=user_id)
        return Update(update_id=1, callback_query=callback_query)
    
    async def process_command(self, command: str, user_id: int = 12345) -> Dict[str, Any]:
        """
        Обрабатывает команду и возвращает результат.
        """
        if not self.application:
            await self.setup()
        
        self.outbox.clear()
        
        update = self.create_mock_update_command(command, user_id)
        context = self.application.create_context(update, None)
        
        try:
            # Обрабатываем update
            await self.application.process_update(update)
            
            return {
                'success': True,
                'outbox': {
                    'messages': self.outbox.messages.copy(),
                    'edited_messages': self.outbox.edited_messages.copy(),
                    'callback_answers': self.outbox.callback_answers.copy()
                }
            }
        except Exception as e:
            logger.error(f"Error processing command: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'outbox': {
                    'messages': self.outbox.messages.copy(),
                    'edited_messages': self.outbox.edited_messages.copy(),
                    'callback_answers': self.outbox.callback_answers.copy()
                }
            }
    
    async def process_callback(self, callback_data: str, user_id: int = 12345) -> Dict[str, Any]:
        """
        Обрабатывает callback и возвращает результат.
        """
        if not self.application:
            await self.setup()
        
        self.outbox.clear()
        
        update = self.create_mock_update_callback(callback_data, user_id)
        context = self.application.create_context(update, None)
        
        try:
            # Обрабатываем update
            await self.application.process_update(update)
            
            return {
                'success': True,
                'outbox': {
                    'messages': self.outbox.messages.copy(),
                    'edited_messages': self.outbox.edited_messages.copy(),
                    'callback_answers': self.outbox.callback_answers.copy()
                }
            }
        except Exception as e:
            logger.error(f"Error processing callback: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'outbox': {
                    'messages': self.outbox.messages.copy(),
                    'edited_messages': self.outbox.edited_messages.copy(),
                    'callback_answers': self.outbox.callback_answers.copy()
                }
            }
    
    def add_handler(self, handler):
        """Добавляет handler в application."""
        if not self.application:
            raise RuntimeError("Application not initialized. Call setup() first.")
        self.application.add_handler(handler)

