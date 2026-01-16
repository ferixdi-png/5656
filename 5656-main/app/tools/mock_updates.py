"""Mock Telegram update and button handlers testing."""

import json
from datetime import datetime
from typing import Dict, Any, Callable
from dataclasses import dataclass


@dataclass
class MockUser:
    """Mock Telegram user."""
    id: int
    is_bot: bool = False
    first_name: str = "Test"
    last_name: str = "User"
    username: str = "testuser"
    language_code: str = "en"


@dataclass
class MockChat:
    """Mock Telegram chat."""
    id: int
    type: str = "private"
    title: str = None
    first_name: str = "Test"
    last_name: str = "User"
    username: str = "testuser"


@dataclass
class MockMessage:
    """Mock Telegram message."""
    message_id: int
    date: int
    chat: MockChat
    from_user: MockUser = None
    text: str = None
    reply_to_message: Any = None
    
    def __post_init__(self):
        if self.from_user is None:
            self.from_user = MockUser(id=self.chat.id)


@dataclass
class MockCallbackQuery:
    """Mock Telegram callback query."""
    id: str
    from_user: MockUser
    chat_instance: int
    data: str
    message: MockMessage = None
    
    def to_dict(self) -> Dict:
        """Convert to dict."""
        return {
            'id': self.id,
            'from': {
                'id': self.from_user.id,
                'is_bot': self.from_user.is_bot,
                'first_name': self.from_user.first_name,
            },
            'chat_instance': self.chat_instance,
            'data': self.data,
        }


@dataclass
class MockUpdate:
    """Mock Telegram update."""
    update_id: int
    message: MockMessage = None
    callback_query: MockCallbackQuery = None
    
    def to_dict(self) -> Dict:
        """Convert to dict."""
        d = {'update_id': self.update_id}
        if self.message:
            d['message'] = {
                'message_id': self.message.message_id,
                'date': self.message.date,
                'chat': {
                    'id': self.message.chat.id,
                    'type': self.message.chat.type,
                },
                'from': {
                    'id': self.message.from_user.id,
                    'is_bot': self.message.from_user.is_bot,
                    'first_name': self.message.from_user.first_name,
                },
                'text': self.message.text,
            }
        if self.callback_query:
            d['callback_query'] = self.callback_query.to_dict()
        return d


class MockUpdateBuilder:
    """Builder for creating mock updates."""
    
    @staticmethod
    def text_message(user_id: int, text: str, update_id: int = 1) -> MockUpdate:
        """Create text message update."""
        chat = MockChat(id=user_id)
        user = MockUser(id=user_id)
        message = MockMessage(
            message_id=1,
            date=int(datetime.now().timestamp()),
            chat=chat,
            from_user=user,
            text=text,
        )
        return MockUpdate(update_id=update_id, message=message)
    
    @staticmethod
    def callback_query(user_id: int, callback_data: str, update_id: int = 1) -> MockUpdate:
        """Create callback query update."""
        chat = MockChat(id=user_id)
        user = MockUser(id=user_id)
        message = MockMessage(
            message_id=1,
            date=int(datetime.now().timestamp()),
            chat=chat,
            from_user=user,
        )
        callback_query = MockCallbackQuery(
            id=f"query_{update_id}",
            from_user=user,
            chat_instance=user_id,
            data=callback_data,
            message=message,
        )
        return MockUpdate(update_id=update_id, callback_query=callback_query)
    
    @staticmethod
    def command(user_id: int, command: str, update_id: int = 1) -> MockUpdate:
        """Create command update."""
        return MockUpdateBuilder.text_message(user_id, f"/{command}", update_id)


class ButtonTestCase:
    """A test case for button handler."""
    
    def __init__(self, name: str, update: MockUpdate, expected_text: str = None, 
                 expected_handler: str = None, should_succeed: bool = True):
        self.name = name
        self.update = update
        self.expected_text = expected_text  # Text that should appear in response
        self.expected_handler = expected_handler  # Handler name that should process
        self.should_succeed = should_succeed
        self.result = None
        self.error = None
    
    def __repr__(self) -> str:
        status = "✅" if self.result else "❌" if self.result is False else "⏳"
        return f"{status} {self.name}"


# Standard button test scenarios
BUTTON_TEST_CASES = [
    ButtonTestCase(
        name="Command: /start",
        update=MockUpdateBuilder.command(12345, "start"),
        expected_text="🚀",  # Main menu should have emoji
        expected_handler="start",
    ),
    ButtonTestCase(
        name="Callback: back_to_menu",
        update=MockUpdateBuilder.callback_query(12345, "back_to_menu"),
        expected_text="🎨",
        expected_handler="back_to_menu",
    ),
    ButtonTestCase(
        name="Callback: show_all_models",
        update=MockUpdateBuilder.callback_query(12345, "show_all_models"),
        expected_text="text",
        expected_handler="show_models",
    ),
    ButtonTestCase(
        name="Callback: generate",
        update=MockUpdateBuilder.callback_query(12345, "generate:stable-diffusion"),
        expected_text="prompt",
        expected_handler="generate",
    ),
    ButtonTestCase(
        name="Callback: profile",
        update=MockUpdateBuilder.callback_query(12345, "profile"),
        expected_text="balance",
        expected_handler="profile",
    ),
]
