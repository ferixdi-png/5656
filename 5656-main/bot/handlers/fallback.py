"""
Global fallback handler for unknown callbacks.

CRITICAL: This handler MUST be registered LAST in dispatcher to catch all unhandled callbacks.
Ensures NO SILENT CLICKS - every callback gets a response.
"""
import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.telemetry.telemetry_helpers import get_update_id, safe_answer_callback
from app.telemetry.events import log_callback_received, log_callback_rejected
from app.telemetry.logging_contract import ReasonCode

logger = logging.getLogger(__name__)

router = Router(name="fallback")


@router.callback_query(F.data)
async def fallback_unknown_callback(callback: CallbackQuery, cid=None, bot_state=None, data: dict = None):
    """
    Global fallback for unknown/unhandled callbacks.
    
    This handler catches ANY callback that wasn't matched by other routers.
    Logs UNKNOWN_CALLBACK and responds to user with actionable message.
    """
    user_id = callback.from_user.id if callback.from_user else None
    chat_id = callback.message.chat.id if (callback.message and callback.message.chat) else None
    callback_data = callback.data
    
    # Safely get update_id using helper
    update_id = get_update_id(callback, data or {})
    
    # Generate cid if not provided (for telemetry)
    from app.telemetry.events import generate_cid
    final_cid = cid or generate_cid()
    
    # Log telemetry (always log, even if cid was None)
    log_callback_received(
        callback_data=callback_data,
        query_id=callback.id,
        user_id=user_id,
        chat_id=chat_id or 0,
        update_id=update_id,
        cid=final_cid
    )
    log_callback_rejected(
        cid=final_cid,
        user_id=user_id,
        chat_id=chat_id or 0,
        reason_code=ReasonCode.UNKNOWN_CALLBACK,
        reason_detail=f"No handler for callback_data: {callback_data}",
        bot_state=bot_state
    )
    
    # Log for debugging (use final_cid)
    logger.warning(
        f"[FALLBACK] Unknown callback: data={callback_data} "
        f"user_id={user_id} chat_id={chat_id} cid={final_cid}"
    )
    
    # CRITICAL: Always answer callback to prevent "loading" state in Telegram
    await safe_answer_callback(
        callback,
        text="⚠️ Эта кнопка устарела. Обновите меню: /start",
        show_alert=False,
        logger_instance=logger
    )
    
    # Optionally send message with refresh button
    try:
        if callback.message:
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            
            await callback.message.edit_text(
                "⚠️ <b>Кнопка устарела</b>\n\n"
                "Меню обновлено. Нажмите кнопку ниже для обновления:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить меню", callback_data="main_menu")]
                ])
            )
    except Exception as e:
        logger.debug(f"[FALLBACK] Could not edit message: {e}")


__all__ = ["router"]
