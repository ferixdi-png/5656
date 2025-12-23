"""Zero-silence guarantee handlers - ensure bot always responds."""
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
import logging

logger = logging.getLogger(__name__)

router = Router(name="zero_silence")


def _log(handler: str, user_id: int) -> None:
    logger.info("entered %s user_id=%s", handler, user_id)


def _fallback_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Меню", callback_data="home")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="back")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="home:support")],
        ]
    )


@router.callback_query()
async def fallback_callback(callback: CallbackQuery) -> None:
    _log("zero_silence_callback", callback.from_user.id)
    await callback.answer()
    logger.warning("Unknown callback: %s", callback.data)
    await callback.message.answer(
        "⚠️ Команда устарела. Откройте меню заново.",
        reply_markup=_fallback_menu(),
    )


@router.message(StateFilter(None), F.content_type.in_(["photo", "video", "audio", "document", "voice", "video_note"]))
async def handle_non_text_messages(message: Message) -> None:
    _log("zero_silence_non_text", message.from_user.id)
    await message.answer(
        "📎 Файл получен, но сейчас я жду команду или текст.\n\n"
        "Выберите задачу в меню или нажмите /start.",
        reply_markup=_fallback_menu(),
    )


@router.message(StateFilter(None), F.text)
async def handle_text_messages(message: Message) -> None:
    _log("zero_silence_text", message.from_user.id)
    text = message.text or ""
    if text.startswith("/"):
        return
    await message.answer(
        "Я готов начать работу.\n\n"
        "Выберите задачу в меню или нажмите /start.",
        reply_markup=_fallback_menu(),
    )
