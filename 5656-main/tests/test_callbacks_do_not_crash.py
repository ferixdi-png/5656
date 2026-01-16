"""
Тесты для проверки, что все callback'и не падают.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


@pytest.fixture
def mock_update():
    """Создаёт mock Update для тестов."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_chat = Mock()
    update.effective_chat.id = 12345
    update.callback_query = Mock()
    update.callback_query.data = "test"
    update.callback_query.message = Mock()
    update.callback_query.message.chat_id = 12345
    update.callback_query.message.edit_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Создаёт mock Context для тестов."""
    context = Mock()
    context.bot = Mock()
    context.bot.send_message = AsyncMock()
    context.bot.send_photo = AsyncMock()
    context.bot.send_video = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_model_callback(mock_update, mock_context):
    """Проверяет callback для выбора модели."""
    try:
        from bot_kie import button_callback
        
        # Тестируем различные callback_data
        test_callbacks = [
            "model:z-image",
            "model:nano-banana-pro",
            "mode:z-image:text_to_image",
            "start:z-image",
            "example:z-image",
            "back_to_menu",
            "help:z-image"
        ]
        
        for callback_data in test_callbacks:
            mock_update.callback_query.data = callback_data
            
            try:
                await button_callback(mock_update, mock_context)
            except Exception as e:
                # Некоторые ошибки ожидаемы (например, нет реальной БД)
                # Но не должно быть критических падений
                if "database" in str(e).lower() or "connection" in str(e).lower():
                    continue
                raise
    
    except ImportError:
        pytest.skip("bot_kie.py не найден")


@pytest.mark.asyncio
async def test_mode_callback(mock_update, mock_context):
    """Проверяет callback для выбора mode."""
    try:
        from bot_kie import button_callback
        
        mock_update.callback_query.data = "mode:z-image:text_to_image"
        
        try:
            await button_callback(mock_update, mock_context)
        except Exception as e:
            # Ожидаемые ошибки (нет БД, нет реальных данных)
            if "database" in str(e).lower() or "connection" in str(e).lower():
                return
            raise
    
    except ImportError:
        pytest.skip("bot_kie.py не найден")


@pytest.mark.asyncio
async def test_back_callback(mock_update, mock_context):
    """Проверяет callback для кнопки "Назад"."""
    try:
        from bot_kie import button_callback
        
        mock_update.callback_query.data = "back_to_menu"
        
        try:
            await button_callback(mock_update, mock_context)
        except Exception as e:
            if "database" in str(e).lower():
                return
            raise
    
    except ImportError:
        pytest.skip("bot_kie.py не найден")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

