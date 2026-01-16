"""
Deploy-Aware Middleware (Batch 48.9)

Graceful degradation во время деплоя:
- Генерации показывают "⏳ Бот обновляется..."
- Балансы сохраняются (но новые генерации не принимаются)
- После деплоя → всё работает нормально
"""
import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Callable, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# Deploy detection (BATCH 48.10: cross-platform)
DEPLOY_MARKER_FILE = Path(tempfile.gettempdir()) / "deploy_in_progress.marker"
DEPLOY_TIMEOUT_SECONDS = 300  # 5 minutes
_deploy_marker_lock = asyncio.Lock()  # BATCH 48.10: Prevent race conditions


def is_deploy_in_progress() -> bool:
    """
    Check if deploy is in progress.
    
    Механизм:
    - При старте бота создаётся marker file
    - После полной инициализации marker удаляется
    - Если marker существует > 5 минут → считаем что deploy завершился (stale marker)
    """
    if not os.path.exists(DEPLOY_MARKER_FILE):
        return False
    
    try:
        # Check marker age
        marker_age = time.time() - os.path.getmtime(DEPLOY_MARKER_FILE)
        
        if marker_age > DEPLOY_TIMEOUT_SECONDS:
            logger.warning(f"⚠️ Stale deploy marker detected (age: {marker_age:.0f}s), removing...")
            os.remove(DEPLOY_MARKER_FILE)
            return False
        
        logger.debug(f"🚧 Deploy in progress (marker age: {marker_age:.0f}s)")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to check deploy marker: {e}")
        return False


async def mark_deploy_start():
    """Mark deploy as started (BATCH 48.10: async + lock + cross-platform)."""
    async with _deploy_marker_lock:
        try:
            # Ensure temp directory exists
            DEPLOY_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Write marker file
            await asyncio.to_thread(
                DEPLOY_MARKER_FILE.write_text,
                str(time.time()),
                encoding='utf-8'
            )
            logger.info(f"🚧 Deploy marker created: {DEPLOY_MARKER_FILE}")
        except Exception as e:
            logger.error(f"❌ Failed to create deploy marker: {e}", exc_info=True)


async def mark_deploy_complete():
    """Mark deploy as completed (BATCH 48.10: async + lock)."""
    async with _deploy_marker_lock:
        try:
            if DEPLOY_MARKER_FILE.exists():
                await asyncio.to_thread(DEPLOY_MARKER_FILE.unlink)
                logger.info(f"✅ Deploy marker removed: {DEPLOY_MARKER_FILE}")
        except FileNotFoundError:
            logger.debug("Deploy marker already removed")
        except Exception as e:
            logger.error(f"❌ Failed to remove deploy marker: {e}", exc_info=True)


class DeployAwareMiddleware(BaseMiddleware):
    """
    Middleware который проверяет deploy status.
    
    Если deploy in progress:
    - Генерации → "⏳ Бот обновляется, попробуйте через минуту"
    - Остальные команды → работают нормально
    """
    
    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery | Message,
        data: dict[str, Any]
    ) -> Any:
        # Check if deploy in progress
        if not is_deploy_in_progress():
            # Deploy complete → normal flow
            return await handler(event, data)
        
        # Deploy in progress → check if this is a generation request
        is_generation_request = False
        
        if isinstance(event, CallbackQuery):
            # Check callback_data
            callback_data = event.data or ""
            
            # Generation-related callbacks
            generation_keywords = [
                "confirm",  # Confirm generation
                "start_gen",  # Start generation
                "generate",  # Generate button
                "model:",  # Model selection
            ]
            
            for keyword in generation_keywords:
                if keyword in callback_data:
                    is_generation_request = True
                    break
        
        if is_generation_request:
            # Show deploy message
            await event.answer(
                "⏳ Бот обновляется, попробуйте через минуту",
                show_alert=True
            )
            
            # Also send message
            if isinstance(event, CallbackQuery):
                try:
                    await event.message.edit_text(
                        "🚧 <b>Бот обновляется</b>\n\n"
                        "⏳ Пожалуйста, подождите минуту и попробуйте снова.\n\n"
                        "💰 Ваш баланс сохранён и будет доступен после обновления.",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=event.data)],
                                [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")]
                            ]
                        )
                    )
                except Exception:
                    pass
            
            logger.info(f"🚧 Blocked generation request during deploy: user={event.from_user.id}")
            return  # Don't call handler
        
        # Not a generation request → allow
        return await handler(event, data)


def get_deploy_status_text() -> str:
    """
    Get deploy status text for display.
    
    Returns:
        Human-readable deploy status
    """
    if is_deploy_in_progress():
        try:
            marker_age = time.time() - os.path.getmtime(DEPLOY_MARKER_FILE)
            remaining = max(0, DEPLOY_TIMEOUT_SECONDS - marker_age)
            return f"🚧 Deploy in progress (осталось ~{remaining / 60:.0f} мин)"
        except Exception:
            return "🚧 Deploy in progress"
    else:
        return "✅ Ready"

