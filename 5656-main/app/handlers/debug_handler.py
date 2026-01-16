"""
/debug команда для администратора.

Позволяет:
1. Включать DEBUG_LOGS на N минут
2. Видеть last_10_events summary
3. Получить последний cid для отладки
"""

import logging
import os
from datetime import datetime, timedelta
from aiogram import types
from app.telemetry.logging_contract import log_event, Domain

logger = logging.getLogger(__name__)

# Глобальное состояние debug мода (не production-grade, но подойдёт для MVP)
_DEBUG_ENABLED_UNTIL: datetime = None
_LAST_EVENTS: list = []  # List[dict] с последними 10 событиями
_MAX_EVENTS_BUFFER = 10


def enable_debug_mode(minutes: int = 30) -> None:
    """Включить debug mode на N минут."""
    global _DEBUG_ENABLED_UNTIL
    _DEBUG_ENABLED_UNTIL = datetime.utcnow() + timedelta(minutes=minutes)


def is_debug_enabled() -> bool:
    """Проверить включен ли debug mode."""
    global _DEBUG_ENABLED_UNTIL
    if _DEBUG_ENABLED_UNTIL is None:
        return False
    if datetime.utcnow() > _DEBUG_ENABLED_UNTIL:
        _DEBUG_ENABLED_UNTIL = None
        return False
    return True


def record_event_to_buffer(event_dict: dict) -> None:
    """Записать событие в буфер last_10_events."""
    global _LAST_EVENTS
    _LAST_EVENTS.append(event_dict)
    if len(_LAST_EVENTS) > _MAX_EVENTS_BUFFER:
        _LAST_EVENTS.pop(0)


def get_last_events_summary() -> str:
    """Получить summary последних 10 событий для админа."""
    if not _LAST_EVENTS:
        return "No events recorded yet."
    
    lines = []
    for event in _LAST_EVENTS[-10:]:  # Last 10
        cid = event.get("cid", "?")
        name = event.get("name", "?")
        screen = event.get("screen_id", "-")
        reason = event.get("reason_code", "-")
        
        line = f"• [{cid}] {name} | screen={screen} | {reason}"
        lines.append(line)
    
    return "\n".join(lines)


def get_last_cid() -> str:
    """Получить последний correlation_id для отладки."""
    if not _LAST_EVENTS:
        return "No events yet"
    return _LAST_EVENTS[-1].get("cid", "?")


async def cmd_debug(update: types.Update, **kwargs) -> None:
    """
    /debug команда - только для админа.
    
    Показывает:
    - Текущий mode (ACTIVE/PASSIVE)
    - last_10_events summary
    - Кнопка "Show last CID"
    """
    
    user_id = update.effective_user.id
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    
    cid = kwargs.get("cid", "debug_cmd")
    
    # Проверка прав
    if user_id != admin_id:
        log_event(
            "COMMAND_REJECTED",
            correlation_id=cid,
            user_id=user_id,
            chat_id=update.effective_chat.id,
            reason_code="PERMISSION_DENIED",
            reason_text="Only ADMIN_ID can use /debug",
            domain=Domain.UX,
        )
        
        await update.message.reply_text(
            "❌ Only administrator can use /debug command."
        )
        return
    
    # Logирование
    log_event(
        "DEBUG_COMMAND",
        correlation_id=cid,
        user_id=user_id,
        chat_id=update.effective_chat.id,
        domain=Domain.UX,
    )
    
    # Получить текущий state
    bot_state = kwargs.get("bot_state", "UNKNOWN")
    debug_enabled = is_debug_enabled()
    
    # Построить response
    text = f"""🔧 DEBUG PANEL

**Current Mode**: {bot_state}
**Debug Logs**: {"✅ ON" if debug_enabled else "❌ OFF"}

**Last 10 Events**:
```
{get_last_events_summary()}
```

**Last CID**: `{get_last_cid()}`

Use /debug_on to enable debug logs for 30 min.
"""
    
    # Клавиатура
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🔴 Enable Debug (30m)",
                    callback_data="debug_on_30",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="📋 Show Last CID",
                    callback_data="debug_show_last_cid",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="❌ Close",
                    callback_data="debug_close",
                ),
            ],
        ]
    )
    
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def cb_debug_on_30(callback: types.CallbackQuery, **kwargs) -> None:
    """Включить debug logs на 30 минут."""
    
    user_id = callback.from_user.id
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    cid = kwargs.get("cid")
    
    if user_id != admin_id:
        await callback.answer("❌ Permission denied", show_alert=True)
        return
    
    enable_debug_mode(minutes=30)
    
    log_event(
        "DEBUG_ENABLED",
        correlation_id=cid,
        user_id=user_id,
        chat_id=callback.message.chat.id,
        domain=Domain.UX,
        extra={"duration_minutes": 30},
    )
    
    await callback.answer("✅ Debug logs enabled for 30 minutes", show_alert=False)
    await callback.message.edit_text(
        f"✅ Debug enabled until {(_DEBUG_ENABLED_UNTIL or datetime.utcnow()).isoformat()}"
    )


async def cb_debug_show_last_cid(callback: types.CallbackQuery, **kwargs) -> None:
    """Показать последний correlation_id."""
    
    cid = kwargs.get("cid")
    
    last_cid = get_last_cid()
    
    text = f"""
**Last Correlation ID**:

```
{last_cid}
```

Paste this in logs search to find the full request trace.
"""
    
    await callback.answer()
    await callback.message.edit_text(text, parse_mode="Markdown")


async def cb_debug_close(callback: types.CallbackQuery, **kwargs) -> None:
    """Закрыть debug panel."""
    
    await callback.message.delete()
    await callback.answer()
