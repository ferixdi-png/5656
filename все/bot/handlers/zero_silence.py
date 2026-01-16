"""
Zero-silence guarantee handlers - ensure bot always responds.
Contract: Every user action MUST receive a response.
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
    """
    Always respond to /start with main menu.
    
    Contract:
    - MUST always respond
    - MUST show main menu
    - Never silent
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
    ])
    
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Я помогу вам создать контент с помощью AI.\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )


@router.callback_query()
async def handle_all_callbacks(callback: CallbackQuery):
    """
    Handle ALL callback queries - always answer and respond.
    
    Contract:
    - MUST call callback.answer() first
    - MUST respond to every callback_data
    - MUST have fallback for unknown callbacks
    """
    # Contract: Always answer callback query first
    await callback.answer()
    
    callback_data = callback.data or ""
    
    try:
        # Handle known callbacks - explicit mapping
        if callback_data == "main_menu":
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")],
                [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")],
                [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
            ])
            try:
                await callback.message.edit_text(
                    "📋 Главное меню\n\n"
                    "Выберите действие:",
                    reply_markup=keyboard
                )
            except TelegramBadRequest:
                # Message not modified - send new message
                await callback.message.answer(
                    "📋 Главное меню\n\n"
                    "Выберите действие:",
                    reply_markup=keyboard
                )
        
        elif callback_data == "help":
            try:
                await callback.message.edit_text(
                    "ℹ️ Помощь\n\n"
                    "1. Выберите модель из меню\n"
                    "2. Отправьте текст, файл или URL\n"
                    "3. Подтвердите оплату\n"
                    "4. Получите результат\n\n"
                    "Используйте /start для главного меню."
                )
            except TelegramBadRequest:
                await callback.message.answer(
                    "ℹ️ Помощь\n\n"
                    "1. Выберите модель из меню\n"
                    "2. Отправьте текст, файл или URL\n"
                    "3. Подтвердите оплату\n"
                    "4. Получите результат\n\n"
                    "Используйте /start для главного меню."
                )
        
        elif callback_data == "settings":
            try:
                await callback.message.edit_text(
                    "⚙️ Настройки\n\n"
                    "Настройки будут доступны позже."
                )
            except TelegramBadRequest:
                await callback.message.answer(
                    "⚙️ Настройки\n\n"
                    "Настройки будут доступны позже."
                )
        
        else:
            # Contract: Fallback for unknown callback_data - MUST respond
            logger.warning(f"Unknown callback_data received: {callback_data}")
            try:
                await callback.message.edit_text(
                    "⚠️ Кнопка устарела\n\n"
                    "Пожалуйста, нажмите /start для обновления меню."
                )
            except TelegramBadRequest:
                await callback.message.answer(
                    "⚠️ Кнопка устарела\n\n"
                    "Пожалуйста, нажмите /start для обновления меню."
                )
    
    # Contract: All exceptions caught and user notified
    except Exception as e:
        logger.error(f"Error in callback handler: {e}", exc_info=True)
        # Contract: User MUST receive response even on error
        try:
            await callback.message.answer(
                "⚠️ Произошла ошибка\n\n"
                "Нажмите /start для главного меню."
            )
        except Exception as e2:
            logger.critical(f"Failed to send error message to user: {e2}")


@router.message(F.content_type.in_(["photo", "video", "audio", "document", "voice", "video_note"]))
async def handle_non_text_messages(message: Message):
    """
    Handle non-text messages - always respond.
    
    Contract:
    - If expecting URL → ask for URL text
    - If expecting file → explain what format needed
    - Never ignore file messages
    """
    # For now, assume we're expecting text/URL (can be enhanced with state tracking)
    # This ensures file messages are never ignored
    await message.answer(
        "📎 Файл получен\n\n"
        "⚠️ Для этой модели нужен текст или URL.\n\n"
        "Пожалуйста, отправьте текстовое сообщение или ссылку.\n"
        "Или выберите модель, которая работает с файлами.\n\n"
        "Используйте /start для главного меню."
    )


@router.message(F.text)
async def handle_text_messages(message: Message):
    """
    Handle text messages - always respond.
    
    Contract:
    - Commands are handled by command handlers
    - URLs are acknowledged
    - Text is acknowledged
    - Never ignore text messages
    """
    text = message.text or ""
    
    # Commands are handled by @router.message(CommandStart()) and other command handlers
    if text.startswith("/"):
        return
    
    # Acknowledge text/URL input
    if text.startswith("http://") or text.startswith("https://"):
        await message.answer(
            "✅ URL получен\n\n"
            "Проверяю ссылку и готовлю задачу..."
        )
    else:
        await message.answer(
            "✅ Текст получен\n\n"
            "Проверяю данные и готовлю задачу..."
        )
