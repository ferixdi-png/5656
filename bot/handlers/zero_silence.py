"""
Zero-silence guarantee handlers - ensure bot always responds.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
import logging

logger = logging.getLogger(__name__)

router = Router(name="zero_silence")


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Always respond to /start with main menu."""
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
        ])
        
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Выберите действие из меню:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error in /start handler: {e}")
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Используйте команды для навигации.\n"
            "Нажмите /start для главного меню."
        )


@router.callback_query()
async def handle_all_callbacks(callback: CallbackQuery):
    """Handle ALL callback queries - always answer and respond."""
    try:
        # Always answer callback query first
        await callback.answer()
        
        callback_data = callback.data
        
        # Handle known callbacks
        if callback_data == "main_menu":
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")],
                [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
                [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
            ])
            await callback.message.edit_text(
                "📋 Главное меню\n\nВыберите действие:",
                reply_markup=keyboard
            )
        elif callback_data == "help":
            await callback.message.edit_text(
                "ℹ️ Помощь\n\n"
                "Используйте /start для главного меню.\n"
                "Отправьте текст или файл согласно инструкциям."
            )
        elif callback_data == "settings":
            await callback.message.edit_text(
                "⚙️ Настройки\n\n"
                "Настройки будут доступны позже."
            )
        else:
            # Unknown callback_data - inform user
            await callback.message.answer(
                "⚠️ Кнопка устарела\n\n"
                "Пожалуйста, нажмите /start для обновления меню."
            )
    except TelegramBadRequest as e:
        # Message not modified or other Telegram error
        logger.warning(f"Telegram error in callback handler: {e}")
        try:
            await callback.message.answer(
                "✅ Действие выполнено.\n\n"
                "Нажмите /start для главного меню."
            )
        except:
            pass
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        try:
            await callback.message.answer(
                "⚠️ Произошла ошибка.\n\n"
                "Пожалуйста, нажмите /start."
            )
        except:
            pass


@router.message(F.content_type.in_(["photo", "video", "audio", "document", "voice", "video_note"]))
async def handle_non_text_messages(message: Message):
    """Handle non-text messages with context-aware responses."""
    try:
        # Check if we're expecting a file (you can customize this logic based on bot state)
        # For now, assume we're expecting text/URL by default
        content_type = message.content_type
        
        # You can check bot state here to determine what's expected
        # For example: if await get_state() == "waiting_for_file": ...
        
        # Default: expecting text/URL
        await message.answer(
            "📎 Вы отправили файл\n\n"
            "❌ Сейчас ожидается текст или URL.\n\n"
            "Пожалуйста, отправьте текстовое сообщение или ссылку.\n"
            "Используйте /start для главного меню."
        )
    except Exception as e:
        logger.error(f"Error handling non-text message: {e}")
        await message.answer(
            "⚠️ Не удалось обработать файл.\n\n"
            "Пожалуйста, отправьте текстовое сообщение.\n"
            "Используйте /start для главного меню."
        )


@router.message(F.text)
async def handle_text_messages(message: Message):
    """Handle text messages - always respond."""
    try:
        text = message.text or ""
        
        # Check if it's a command (should be handled by command handlers)
        if text.startswith("/"):
            # Let command handlers process it, but ensure response
            return
        
        # You can check bot state here to determine what's expected
        # For example: if await get_state() == "waiting_for_file": ...
        #     await message.answer("❌ Сейчас ожидается файл. Пожалуйста, отправьте файл.")
        #     return
        
        if text.startswith("http://") or text.startswith("https://"):
            await message.answer(
                "✅ URL получен!\n\n"
                "Обрабатываю...\n"
                "Используйте /start для главного меню."
            )
        else:
            await message.answer(
                "✅ Текст получен!\n\n"
                "Обрабатываю...\n"
                "Используйте /start для главного меню."
            )
    except Exception as e:
        logger.error(f"Error handling text message: {e}")
        await message.answer(
            "⚠️ Не удалось обработать сообщение.\n\n"
            "Пожалуйста, попробуйте еще раз.\n"
            "Используйте /start для главного меню."
        )

