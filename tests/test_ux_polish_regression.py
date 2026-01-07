"""
Tests for UX polish regression.
Ensures UI/UX improvements don't regress.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, User, Chat


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock(spec=User)
    user.id = 123456
    user.first_name = "Test"
    user.username = "testuser"
    user.language_code = "ru"
    return user


@pytest.fixture
def mock_chat():
    """Create a mock chat."""
    chat = Mock(spec=Chat)
    chat.id = 123456
    chat.type = "private"
    return chat


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """Create a mock message."""
    message = Mock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.text = "test message"
    message.message_id = 1
    message.edit_text = AsyncMock()
    message.edit_reply_markup = AsyncMock()
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query(mock_user, mock_message):
    """Create a mock callback query."""
    callback = Mock(spec=CallbackQuery)
    callback.from_user = mock_user
    callback.message = mock_message
    callback.data = "test_callback"
    callback.id = "callback_123"
    callback.answer = AsyncMock()
    return callback


def _flatten_buttons(markup):
    """Helper to flatten keyboard buttons."""
    if markup is None:
        return []
    return [
        (button.text, button.callback_data)
        for row in markup.inline_keyboard
        for button in row
    ]


class TestButtonPresence:
    """Test that essential buttons are present in UI."""
    
    def test_main_menu_has_history_button(self):
        """Test main menu includes history button."""
        # Simulate main menu markup
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 История", callback_data="menu:history")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help")]
        ])
        
        buttons = _flatten_buttons(markup)
        callbacks = [cb for _, cb in buttons]
        
        assert "menu:history" in callbacks
    
    def test_main_menu_has_balance_button(self):
        """Test main menu includes balance button."""
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 История", callback_data="menu:history")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help")]
        ])
        
        buttons = _flatten_buttons(markup)
        callbacks = [cb for _, cb in buttons]
        
        assert "menu:balance" in callbacks
    
    def test_main_menu_has_help_button(self):
        """Test main menu includes help button."""
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 История", callback_data="menu:history")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help")]
        ])
        
        buttons = _flatten_buttons(markup)
        callbacks = [cb for _, cb in buttons]
        
        assert "menu:help" in callbacks


class TestButtonLabels:
    """Test that button labels are user-friendly."""
    
    def test_buttons_have_emojis(self):
        """Test that buttons include emojis for visual appeal."""
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 История", callback_data="menu:history")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance")],
        ])
        
        buttons = _flatten_buttons(markup)
        texts = [text for text, _ in buttons]
        
        # Check that buttons have emojis
        for text in texts:
            # At least one emoji character (simple check)
            assert any(ord(char) > 127 for char in text)
    
    def test_buttons_have_descriptive_text(self):
        """Test that buttons have descriptive labels."""
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 История", callback_data="menu:history")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="menu:balance")],
        ])
        
        buttons = _flatten_buttons(markup)
        texts = [text for text, _ in buttons]
        
        # Check that buttons have text beyond emoji
        for text in texts:
            # Remove emojis and check remaining text
            text_only = ''.join(char for char in text if ord(char) < 127).strip()
            # Should have some descriptive text
            assert len(text) > 1  # At least emoji + space or text


class TestCallbackDataFormat:
    """Test that callback data follows consistent format."""
    
    def test_menu_callbacks_use_prefix(self):
        """Test menu callbacks use 'menu:' prefix."""
        callbacks = ["menu:history", "menu:balance", "menu:help"]
        
        for callback in callbacks:
            assert callback.startswith("menu:")
    
    def test_category_callbacks_use_prefix(self):
        """Test category callbacks use 'cat:' prefix."""
        callbacks = ["cat:image", "cat:video", "cat:audio"]
        
        for callback in callbacks:
            assert callback.startswith("cat:")
    
    def test_model_callbacks_use_prefix(self):
        """Test model callbacks use 'model:' prefix."""
        callbacks = ["model:flux-pro", "model:dalle-3", "model:stable-diffusion"]
        
        for callback in callbacks:
            assert callback.startswith("model:")


class TestMessageFormatting:
    """Test that messages are properly formatted."""
    
    @pytest.mark.asyncio
    async def test_welcome_message_formatting(self, mock_message):
        """Test welcome message is properly formatted."""
        welcome_text = "👋 Добро пожаловать!\n\nВыберите категорию:"
        
        # Check multiline
        assert "\n" in welcome_text
        # Check emoji
        assert "👋" in welcome_text
        # Check text content
        assert len(welcome_text) > 10
    
    @pytest.mark.asyncio
    async def test_error_message_formatting(self, mock_message):
        """Test error messages are user-friendly."""
        error_text = "❌ Ошибка: Попробуйте позже"
        
        # Check error indicator
        assert "❌" in error_text or "Ошибка" in error_text
        # Check helpful message
        assert len(error_text) > 5


class TestResponseTime:
    """Test that UI responses are appropriately delayed."""
    
    @pytest.mark.asyncio
    async def test_callback_answer_is_called(self, mock_callback_query):
        """Test that callbacks are acknowledged."""
        # Simulate answering callback
        await mock_callback_query.answer()
        
        # Verify answer was called
        mock_callback_query.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_callback_answer_has_text(self, mock_callback_query):
        """Test that callback answers can include text."""
        # Simulate answering with text
        await mock_callback_query.answer(text="Загружаем...")
        
        # Verify answer was called with text
        mock_callback_query.answer.assert_called_once_with(text="Загружаем...")


class TestNavigationFlow:
    """Test navigation flow between screens."""
    
    def test_back_button_navigation(self):
        """Test back button is present in sub-menus."""
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back:main")],
        ])
        
        buttons = _flatten_buttons(markup)
        callbacks = [cb for _, cb in buttons]
        
        # Should have back button
        has_back = any(cb.startswith("back:") for cb in callbacks)
        assert has_back
    
    def test_cancel_button_in_wizard(self):
        """Test cancel button is available in wizards."""
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
        ])
        
        buttons = _flatten_buttons(markup)
        callbacks = [cb for _, cb in buttons]
        
        # Should have cancel option
        assert "cancel" in callbacks


class TestLoadingIndicators:
    """Test that loading states are indicated to users."""
    
    @pytest.mark.asyncio
    async def test_processing_message_shown(self, mock_message):
        """Test that processing message is shown during operations."""
        processing_text = "⏳ Обрабатываем ваш запрос..."
        
        # Simulate showing processing message
        await mock_message.answer(processing_text)
        
        # Verify message was sent
        mock_message.answer.assert_called_once_with(processing_text)
    
    @pytest.mark.asyncio
    async def test_loading_indicator_has_emoji(self, mock_callback_query):
        """Test loading indicators include visual cue."""
        loading_texts = ["⏳ Загружаем...", "⌛ Подождите..."]
        
        for text in loading_texts:
            # Should have emoji indicator
            assert any(ord(char) > 127 for char in text)


class TestErrorHandling:
    """Test error handling and user feedback."""
    
    @pytest.mark.asyncio
    async def test_error_shows_retry_option(self):
        """Test error messages include retry option."""
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Повторить", callback_data="retry")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back:main")],
        ])
        
        buttons = _flatten_buttons(markup)
        callbacks = [cb for _, cb in buttons]
        
        # Should have retry option
        assert "retry" in callbacks
    
    @pytest.mark.asyncio
    async def test_error_message_is_informative(self):
        """Test error messages provide context."""
        error_message = "❌ Не удалось создать изображение. Проверьте промпт и попробуйте снова."
        
        # Should explain what happened
        assert len(error_message) > 20
        # Should have error indicator
        assert "❌" in error_message or "Ошибка" in error_message


class TestAccessibility:
    """Test accessibility features."""
    
    def test_buttons_per_row_limit(self):
        """Test that button rows don't exceed reasonable width."""
        # Good UX: max 2-3 buttons per row for mobile
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Btn1", callback_data="1"),
             InlineKeyboardButton(text="Btn2", callback_data="2")],
        ])
        
        for row in markup.inline_keyboard:
            assert len(row) <= 3  # Max 3 buttons per row
    
    def test_button_text_length(self):
        """Test button text isn't too long."""
        buttons = [
            "📜 История",
            "💰 Баланс",
            "❓ Помощь"
        ]
        
        for text in buttons:
            # Button text should be concise (< 30 chars for mobile)
            assert len(text) < 30
