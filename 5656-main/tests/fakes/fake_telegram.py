"""
Fake Telegram для тестов
НИКОГДА не делает реальных HTTP запросов
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FakeMessage:
    """Fake Telegram Message"""
    message_id: int
    text: Optional[str] = None
    photo: Optional[List] = None
    audio: Optional[Dict] = None
    document: Optional[Dict] = None
    from_user: Optional['FakeUser'] = None
    chat: Optional['FakeChat'] = None
    
    async def reply_text(self, text: str, **kwargs):
        """Fake reply_text"""
        return FakeMessage(message_id=self.message_id + 1, text=text)
    
    async def edit_text(self, text: str, **kwargs):
        """Fake edit_text"""
        self.text = text
        return True


@dataclass
class FakeUser:
    """Fake Telegram User"""
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None


@dataclass
class FakeChat:
    """Fake Telegram Chat"""
    id: int
    type: str = "private"


@dataclass
class FakeCallbackQuery:
    """Fake Telegram CallbackQuery"""
    id: str
    data: str
    from_user: FakeUser
    message: FakeMessage
    
    async def answer(self, text: str = None, show_alert: bool = False):
        """Fake answer"""
        return True


@dataclass
class FakeUpdate:
    """Fake Telegram Update"""
    update_id: int
    message: Optional[FakeMessage] = None
    callback_query: Optional[FakeCallbackQuery] = None
    
    @property
    def effective_user(self) -> Optional[FakeUser]:
        if self.message and self.message.from_user:
            return self.message.from_user
        if self.callback_query:
            return self.callback_query.from_user
        return None
    
    @property
    def effective_chat(self) -> Optional[FakeChat]:
        if self.message and self.message.chat:
            return self.message.chat
        return None


class FakeTelegramBot:
    """Fake Telegram Bot для тестов"""
    
    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.edited_messages: List[Dict[str, Any]] = []
        self.callbacks_answered: List[str] = []
    
    async def send_message(self, chat_id: int, text: str, **kwargs):
        """Fake send_message"""
        msg = {
            "chat_id": chat_id,
            "text": text,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.sent_messages.append(msg)
        return FakeMessage(message_id=len(self.sent_messages), text=text)
    
    async def edit_message_text(self, text: str, chat_id: int = None, message_id: int = None, **kwargs):
        """Fake edit_message_text"""
        msg = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.edited_messages.append(msg)
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """Возвращает статистику"""
        return {
            "sent_messages": len(self.sent_messages),
            "edited_messages": len(self.edited_messages),
            "callbacks_answered": len(self.callbacks_answered)
        }







