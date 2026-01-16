"""
Admin diagnostics command.
ПУНКТ 4: Кнопка /diag как рентген - мгновенная диагностика
"""
import os
import subprocess
from datetime import datetime
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.utils.runtime_state import runtime_state
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = Router(name="diag")


@router.message(Command("diag"))
async def cmd_diag(message: Message) -> None:
    logger.info(f"[DIAG] User {message.from_user.id} called /diag")
    
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if admin_id and message.from_user and message.from_user.id != admin_id:
        await message.answer("⛔ Доступ запрещен")
        return

    lines = ["🩺 <b>ДИАГНОСТИКА БОТА</b>\n"]
    
    # 1. Git version
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd="/app",
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2
        ).strip()
        lines.append(f"📌 <b>Коммит:</b> <code>{commit}</code>")
    except Exception as e:
        logger.debug(f"[DIAG] Failed to get git commit: {e}")
        lines.append("📌 <b>Коммит:</b> неизвестен")
    
    # 2. Bot mode & runtime state
    bot_mode = runtime_state.bot_mode or os.getenv("BOT_MODE", "unknown")
    dry_run = os.getenv("DRY_RUN", "0")
    lock_status = runtime_state.lock_acquired
    instance_id = runtime_state.instance_id or "unknown"
    
    lock_emoji = "✅" if lock_status else "⏸️"
    lock_text = "ACTIVE (lock получен)" if lock_status else "PASSIVE (нет lock)"
    
    lines.append(f"🤖 <b>Режим:</b> {bot_mode} (DRY_RUN={dry_run})")
    lines.append(f"{lock_emoji} <b>Lock:</b> {lock_text}")
    lines.append(f"🆔 <b>Instance:</b> <code>{instance_id[:16]}</code>")
    
    # 3. Database
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            from app.database.connection import get_db_session
            from sqlalchemy import text
            async with get_db_session() as session:
                result = await session.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
            lines.append(f"✅ <b>БД:</b> OK ({user_count} пользователей)")
        except Exception as e:
            lines.append(f"❌ <b>БД:</b> {type(e).__name__}")
    else:
        lines.append("⚠️ <b>БД:</b> не настроена")
    
    # 4. KIE API
    kie_key = os.getenv("KIE_API_KEY", "")
    if kie_key:
        masked = f"{kie_key[:6]}...{kie_key[-4:]}" if len(kie_key) > 10 else "***"
        lines.append(f"✅ <b>KIE API:</b> <code>{masked}</code>")
    else:
        lines.append("❌ <b>KIE API:</b> ключ не установлен")
    
    # 5. Webhook
    webhook_base = os.getenv("WEBHOOK_BASE_URL", "")
    if webhook_base:
        lines.append(f"🌐 <b>Base URL:</b> {webhook_base}")
    else:
        lines.append("❌ <b>Base URL:</b> не установлен!")
    
    # 6. Webhook registration status (CRITICAL!)
    try:
        webhook_info = await message.bot.get_webhook_info()
        if webhook_info.url:
            url_short = webhook_info.url[:50] + "..." if len(webhook_info.url) > 50 else webhook_info.url
            lines.append(f"✅ <b>Webhook:</b> зарегистрирован")
            lines.append(f"   URL: <code>{url_short}</code>")
            if webhook_info.pending_update_count > 0:
                lines.append(f"   ⚠️ Pending: {webhook_info.pending_update_count}")
            if webhook_info.last_error_message:
                lines.append(f"   ⚠️ Последняя ошибка: {webhook_info.last_error_message[:100]}")
        else:
            lines.append("❌ <b>Webhook:</b> НЕ ЗАРЕГИСТРИРОВАН!")
            lines.append("   🚫 Бот НЕ получает /start и другие команды!")
            lines.append("   💡 Требуется: регистрация webhook с Telegram")
    except Exception as e:
        lines.append(f"❌ <b>Webhook check:</b> {str(e)[:80]}")
    
    # 7. Schema ready
    schema_ready = runtime_state.db_schema_ready
    lines.append(f"{'✅' if schema_ready else '❌'} <b>Migrations:</b> {'применены' if schema_ready else 'не готовы'}")
    
    # 8. Uptime
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
        h = int(uptime_seconds // 3600)
        m = int((uptime_seconds % 3600) // 60)
        lines.append(f"⏱ <b>Uptime:</b> {h}ч {m}м")
    except Exception as e:
        logger.debug(f"[DIAG] Failed to get uptime from /proc/uptime: {e}")
    
    # 9. Time
    lines.append(f"🕐 <b>Время:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    report = "\n".join(lines)
    
    await message.answer(report, parse_mode="HTML")
    logger.info(f"[DIAG] Report sent to admin {message.from_user.id}")
