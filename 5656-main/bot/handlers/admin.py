"""
Admin panel handlers - полное управление системой.
"""
import json
import logging
import os
from decimal import Decimal
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.payments.pricing import format_price_rub
from app.admin.permissions import is_admin

logger = logging.getLogger(__name__)

router = Router(name="admin")

# Global services
_db_service = None
_admin_service = None
_free_manager = None


def _strict_admin_id() -> int | None:
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id:
        return None
    try:
        return int(admin_id)
    except ValueError as e:
        logger.error(f"Failed to parse ADMIN_ID from env: {e}")
        return None


def _is_strict_admin(user_id: int) -> bool:
    admin_id = _strict_admin_id()
    return admin_id is not None and user_id == admin_id


async def _ensure_strict_admin(message: Message) -> bool:
    if not _is_strict_admin(message.from_user.id):
        logger.warning("Unauthorized admin command by user_id=%s", message.from_user.id)
        await message.answer("⛔️ Доступ запрещён")
        return False
    return True


def set_services(db_service, admin_service, free_manager):
    """Set services for handlers."""
    global _db_service, _admin_service, _free_manager
    _db_service = db_service
    _admin_service = admin_service
    _free_manager = free_manager


class AdminStates(StatesGroup):
    """FSM states for admin operations."""
    select_model_for_free = State()
    enter_free_limits = State()
    select_user_for_action = State()
    enter_topup_amount = State()
    enter_charge_amount = State()
    enter_ban_reason = State()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """Admin stats callback (redirects to admin:analytics)."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_stats")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_stats")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    # Redirect to admin:analytics
    from bot.handlers.admin import cb_admin_analytics
    await cb_admin_analytics(callback)


@router.callback_query(F.data == "admin_logs_24h")
async def cb_admin_logs_24h(callback: CallbackQuery):
    """Admin logs for last 24 hours callback (redirects to admin:log)."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_logs_24h")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_logs_24h")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    # Redirect to admin:log
    from bot.handlers.admin import cb_admin_log
    await cb_admin_log(callback)


@router.callback_query(F.data == "admin_models")
async def cb_admin_models_legacy(callback: CallbackQuery, state: FSMContext):
    """Admin models callback (redirects to admin:models)."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_models_legacy")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_models_legacy")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    # Redirect to admin:models
    from bot.handlers.admin import cb_admin_models
    await cb_admin_models(callback, state)


@router.callback_query(F.data == "admin_health")
async def cb_admin_health(callback: CallbackQuery):
    """Admin health check callback."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_health")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_health")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    
    # Show health status
    from app.utils.runtime_state import runtime_state
    text = (
        f"🏥 <b>System Health</b>\n\n"
        f"DB Schema Ready: {'✅' if runtime_state.db_schema_ready else '❌'}\n"
        f"Lock State: {'ACTIVE' if runtime_state.lock_acquired else 'PASSIVE'}\n"
        f"Bot Mode: {runtime_state.bot_mode}\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "admin_cleanup")
async def cb_admin_cleanup(callback: CallbackQuery):
    """Admin cleanup callback (placeholder)."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_cleanup")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_cleanup")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "🗑️ <b>Cleanup Logs</b>\n\n"
        "Эта функция пока не реализована.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
        ])
    )


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    """Admin stats for last 24 hours."""
    # P0-1: CRITICAL None checks
    if not message.from_user:
        logger.error("[ADMIN] message.from_user is None in cmd_admin_stats")
        await message.answer("❌ Ошибка: не удалось определить пользователя.")
        return
    
    if not await _ensure_strict_admin(message):
        return
    if not _db_service:
        await message.answer("⚠️ База данных недоступна")
        return

    try:
        async with _db_service.get_connection() as conn:
            total_jobs = await conn.fetchval(
                """
                SELECT COUNT(*) FROM jobs
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                """
            ) or 0
            success_jobs = await conn.fetchval(
                """
                SELECT COUNT(*) FROM jobs
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND status = 'done'
                """
            ) or 0
            failed_jobs = await conn.fetchval(
                """
                SELECT COUNT(*) FROM jobs
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND status = 'failed'
                """
            ) or 0
            revenue = await conn.fetchval(
                """
                SELECT COALESCE(SUM(price_rub), 0) FROM jobs
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND status = 'done'
                """
            ) or Decimal("0.00")

        logger.info("Admin %s requested 24h stats", message.from_user.id)
        await message.answer(
            "📊 <b>Статистика за 24 часа</b>\n\n"
            f"Всего задач: {total_jobs}\n"
            f"Успешных: {success_jobs}\n"
            f"Неудачных: {failed_jobs}\n"
            f"Выручка: {format_price_rub(revenue)}"
        )
    except Exception as e:
        logger.warning(f"[ADMIN_STATS] Failed to get stats (non-critical): {e}")
        await message.answer("⚠️ Статистика временно недоступна. Попробуйте позже.")


@router.message(Command("admin_user"))
async def cmd_admin_user(message: Message):
    """Show user balance and last 10 jobs by user_id."""
    # P0-1: CRITICAL None checks
    if not message.from_user:
        logger.error("[ADMIN] message.from_user is None in cmd_admin_user")
        await message.answer("❌ Ошибка: не удалось определить пользователя.")
        return
    
    if not await _ensure_strict_admin(message):
        return
    if not _db_service or not _admin_service:
        await message.answer("⚠️ База данных недоступна")
        return

    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Использование: /admin_user [id]")
        return
    try:
        user_id = int(parts[1])
    except ValueError as e:
        logger.error("Failed to parse admin_user id '%s': %s", parts[1], e)
        await message.answer("❌ Неверный формат. Использование: /admin_user [id]")
        return

    user_info = await _admin_service.get_user_info(user_id)
    if not user_info:
        await message.answer(f"❌ Пользователь {user_id} не найден")
        return

    try:
        async with _db_service.get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT model_id, status, price_rub, created_at
                FROM jobs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                user_id
            )

        jobs_lines = []
        for row in rows:
            created = row["created_at"].strftime("%d.%m %H:%M")
            price = format_price_rub(row["price_rub"])
            jobs_lines.append(f"• {created} | {row['model_id']} | {row['status']} | {price}")
        jobs_text = "\n".join(jobs_lines) if jobs_lines else "Нет задач"

        logger.info("Admin %s requested user info for %s", message.from_user.id, user_id)
        await message.answer(
            "👤 <b>Пользователь</b>\n\n"
            f"ID: <code>{user_info['user_id']}</code>\n"
            f"Username: @{user_info['username'] or '—'}\n"
            f"Имя: {user_info['first_name'] or '—'}\n\n"
            f"💰 Баланс: {format_price_rub(user_info['balance']['balance_rub'])}\n"
            f"🔒 Резерв: {format_price_rub(user_info['balance']['hold_rub'])}\n\n"
            f"🧾 Последние 10 задач:\n{jobs_text}"
        )
    except Exception as e:
        logger.warning(f"[ADMIN_USER] Failed to get user info (non-critical): {e}")
        await message.answer("⚠️ Ошибка при получении информации о пользователе. Попробуйте позже.")


@router.message(Command("admin_ops_snapshot"))
async def cmd_admin_ops_snapshot(message: Message):
    """Generate ops snapshot and send summary to admin."""
    # P0-1: CRITICAL None checks
    if not message.from_user:
        logger.error("[ADMIN] message.from_user is None in cmd_admin_ops_snapshot")
        await message.answer("❌ Ошибка: не удалось определить пользователя.")
        return
    
    if not await _ensure_strict_admin(message):
        return
    
    await message.answer("⏳ Генерация ops snapshot...")
    
    try:
        import subprocess
        import asyncio
        from pathlib import Path
        from app.ops.snapshot import generate_snapshot_summary, get_snapshot_files
        
        # Run ops checks (non-blocking, best-effort)
        try:
            # Try to run ops-all (may fail if config missing, that's OK)
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "app.ops.render_logs", "--minutes", "60",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=30.0)
        except (asyncio.TimeoutError, FileNotFoundError, Exception) as e:
            logger.warning(f"Ops fetch-logs failed (non-critical): {e}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "app.ops.db_diag",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=30.0)
        except (asyncio.TimeoutError, FileNotFoundError, Exception) as e:
            logger.warning(f"Ops db-diag failed (non-critical): {e}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "app.ops.critical5",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=30.0)
        except (asyncio.TimeoutError, FileNotFoundError, Exception) as e:
            logger.warning(f"Ops critical5 failed (non-critical): {e}")
        
        # Generate summary from available files
        render_logs, db_diag = get_snapshot_files()
        summary = generate_snapshot_summary(render_logs, db_diag)
        
        await message.answer(summary, parse_mode="HTML")
        logger.info("Admin %s requested ops snapshot", message.from_user.id)
    
    except Exception as e:
        logger.exception("Ops snapshot generation failed")
        await message.answer(
            f"❌ <b>Ошибка генерации snapshot</b>\n\n"
            f"<code>{str(e)[:200]}</code>\n\n"
            f"Проверьте логи для деталей."
        )


@router.message(Command("admin_toggle_model"))
async def cmd_admin_toggle_model(message: Message):
    """Enable/disable model by model_id."""
    # P0-1: CRITICAL None checks
    if not message.from_user:
        logger.error("[ADMIN] message.from_user is None in cmd_admin_toggle_model")
        await message.answer("❌ Ошибка: не удалось определить пользователя.")
        return
    
    if not await _ensure_strict_admin(message):
        return
    if not _admin_service:
        await message.answer("⚠️ Сервис админа недоступен")
        return

    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Использование: /admin_toggle_model [model_id]")
        return
    model_id = parts[1].strip()
    source_file = Path("models/KIE_SOURCE_OF_TRUTH.json")
    if not source_file.exists():
        await message.answer("❌ Source of truth не найден")
        return

    data = json.loads(source_file.read_text())
    model_entry = next((m for m in data.get("models", []) if m.get("model_id") == model_id), None)
    if not model_entry:
        await message.answer("❌ Модель не найдена")
        return

    if "disabled_reason" in model_entry:
        await _admin_service.enable_model(message.from_user.id, model_id, reason="admin_toggle")
        action = "enabled"
        status_text = "✅ Модель включена"
    else:
        await _admin_service.disable_model(message.from_user.id, model_id, reason="admin_toggle")
        action = "disabled"
        status_text = "⛔️ Модель отключена"

    logger.info("Admin %s toggled model %s -> %s", message.from_user.id, model_id, action)
    await message.answer(f"{status_text}: `{model_id}`", parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Admin panel entry point."""
    await state.clear()
    
    # Check admin
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        return
    
    text = (
        f"🛠 <b>Админ-панель</b>\n\n"
        f"Добро пожаловать, {message.from_user.first_name}!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Управление моделями", callback_data="admin:models")],
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin:users")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="admin:analytics")],
        [InlineKeyboardButton(text="📜 Лог действий", callback_data="admin:log")],
        [InlineKeyboardButton(text="⚙️ Runtime Status", callback_data="admin:runtime_status")],
        [InlineKeyboardButton(text="🔍 Последние 10 действий", callback_data="admin:recent_actions")],
        [InlineKeyboardButton(text="◀️ Закрыть", callback_data="admin:close")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "admin:runtime_status")
async def cb_admin_runtime_status(callback: CallbackQuery):
    """Show runtime status: ACTIVE/PASSIVE, lock holder, db ok, webhook ok."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_runtime_status")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_runtime_status")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    
    import os
    from app.utils.runtime_state import runtime_state
    from app.locking.single_instance import get_lock_debug_info
    from datetime import datetime, timezone
    
    # Get lock state
    lock_acquired = runtime_state.lock_acquired
    lock_state = "ACTIVE" if lock_acquired else "PASSIVE"
    lock_emoji = "✅" if lock_acquired else "⏸️"
    
    # Get lock debug info
    lock_debug = get_lock_debug_info()
    lock_holder_pid = lock_debug.get("holder_pid", "N/A")
    instance_id = runtime_state.instance_id or "unknown"
    
    # Check DB status
    db_status = "❌ FAIL"
    try:
        if _db_service:
            db_status = "✅ OK"
        else:
            db_status = "⚠️ WARN (no service)"
    except Exception as e:
        db_status = f"❌ FAIL ({str(e)[:30]})"
    
    # Check webhook status
    webhook_status = "❌ FAIL"
    try:
        webhook_url = os.getenv("WEBHOOK_BASE_URL", "")
        if webhook_url:
            webhook_status = "✅ OK"
        else:
            webhook_status = "⚠️ WARN (no URL)"
    except Exception as e:
        webhook_status = f"❌ FAIL ({str(e)[:30]})"
    
    # Get bot mode
    bot_mode = runtime_state.bot_mode or os.getenv("BOT_MODE", "unknown")
    dry_run = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")
    
    # Get uptime
    uptime_str = "N/A"
    if runtime_state.last_start_time:
        try:
            started = datetime.fromisoformat(runtime_state.last_start_time.replace('Z', '+00:00'))
            uptime_seconds = int((datetime.now(timezone.utc) - started).total_seconds())
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            uptime_str = f"{hours}ч {minutes}м"
        except Exception as e:
            logger.debug(f"[ADMIN] Failed to format uptime: {e}")
            uptime_str = runtime_state.last_start_time
    
    status_text = (
        f"⚙️ <b>Runtime Status</b>\n\n"
        f"{lock_emoji} <b>Lock State:</b> {lock_state}\n"
        f"   • Lock Holder PID: <code>{lock_holder_pid}</code>\n"
        f"   • Instance ID: <code>{instance_id[:16]}</code>\n\n"
        f"🗄️ <b>Database:</b> {db_status}\n"
        f"🔗 <b>Webhook:</b> {webhook_status}\n\n"
        f"🤖 <b>Bot Mode:</b> {bot_mode}\n"
        f"🔧 <b>DRY_RUN:</b> {'Да' if dry_run else 'Нет'}\n"
        f"⏱️ <b>Uptime:</b> {uptime_str}\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:runtime_status")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")]
    ])
    
    await callback.message.edit_text(status_text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin:recent_actions")
async def cb_admin_recent_actions(callback: CallbackQuery):
    """Show last 10 actions (mini-audit) for admin."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_recent_actions")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_recent_actions")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    
    from app.audit.action_logger import get_recent_actions, format_actions_for_admin
    
    actions = get_recent_actions(limit=10)
    actions_text = format_actions_for_admin(actions)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:recent_actions")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back")]
    ])
    
    await callback.message.edit_text(actions_text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin:back")
async def cb_admin_back(callback: CallbackQuery, state: FSMContext):
    """Go back to admin menu."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_back")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_back")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await callback.answer()
    # Re-show admin menu
    text = (
        f"🛠 <b>Админ-панель</b>\n\n"
        f"Добро пожаловать, {callback.from_user.first_name}!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Управление моделями", callback_data="admin:models")],
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin:users")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="admin:analytics")],
        [InlineKeyboardButton(text="📜 Лог действий", callback_data="admin:log")],
        [InlineKeyboardButton(text="⚙️ Runtime Status", callback_data="admin:runtime_status")],
        [InlineKeyboardButton(text="🔍 Последние 10 действий", callback_data="admin:recent_actions")],
        [InlineKeyboardButton(text="◀️ Закрыть", callback_data="admin:close")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "admin:close")
async def cb_admin_close(callback: CallbackQuery, state: FSMContext):
    """Close admin panel."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_close")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_close")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return

    await callback.message.delete()
    await callback.answer("Админ-панель закрыта")
    await state.clear()


# ========== MODELS MANAGEMENT ==========

@router.callback_query(F.data == "admin:models")
async def cb_admin_models(callback: CallbackQuery, state: FSMContext):
    """Models management."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    # Get free models count
    free_count = 0
    if _free_manager:
        try:
            free_models = await _free_manager.get_all_free_models()
            free_count = len(free_models)
        except Exception as e:
            logger.warning("Failed to get free models: %s", e)
            free_count = 4  # fallback to known count
    else:
        # Fallback when _free_manager is not initialized
        free_count = 4
    
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_models")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_models")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    text = (
        f"🎨 <b>Управление моделями</b>\n\n"
        f"Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Список бесплатных", callback_data="admin:models:list_free")],
        [InlineKeyboardButton(text="➕ Сделать модель бесплатной", callback_data="admin:models:add_free")],
        [InlineKeyboardButton(text="� Ресинк моделей из Kie API", callback_data="admin:models:resync")],
        [InlineKeyboardButton(text="�📊 Статистика моделей", callback_data="admin:models:stats")],
        [InlineKeyboardButton(text="⚠️ Модели без schema", callback_data="admin:models:broken")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:models:list_free")
async def cb_admin_models_list_free(callback: CallbackQuery):
    """List free models."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_models_list_free")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_models_list_free")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    free_models = []
    if _free_manager:
        try:
            free_models = await _free_manager.get_all_free_models()
        except Exception as e:
            logger.warning("Failed to get free models: %s", e)
            # Fallback to known free models
            free_models = [
                {"model_id": "z-image"},
                {"model_id": "qwen/text-to-image"},
                {"model_id": "qwen/image-to-image"},
                {"model_id": "qwen/image-edit"}
            ]
    else:
        # Fallback when manager not initialized
        free_models = [
            {"model_id": "z-image"},
            {"model_id": "qwen/text-to-image"},
            {"model_id": "qwen/image-to-image"},
            {"model_id": "qwen/image-edit"}
        ]
    
    if not free_models:
        text = "🎁 <b>Бесплатные модели</b>\n\nСписок пуст"
    else:
        text = f"🎁 <b>Бесплатные модели</b> ({len(free_models)})\n\n"
        for model in free_models:
            model_id = model.get('model_id', 'unknown')
            # Free models may not have limits in dict format
            if isinstance(model, dict) and 'daily_limit' in model:
                daily = model.get('daily_limit', '—')
                hourly = model.get('hourly_limit', '—')
                text += f"• <code>{model_id}</code>\n  Лимиты: {daily}/день, {hourly}/час\n\n"
            else:
                text += f"• <code>{model_id}</code>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:models")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:models:add_free")
async def cb_admin_models_add_free(callback: CallbackQuery, state: FSMContext):
    """Add free model."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    text = (
        f"➕ <b>Сделать модель бесплатной</b>\n\n"
        f"Введите ID модели (например: <code>gemini_flash_2_0</code>)"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:models")]
    ])
    
    await state.set_state(AdminStates.select_model_for_free)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(AdminStates.select_model_for_free)
async def process_free_model_id(message: Message, state: FSMContext):
    """Process model ID for free."""
    # P0-1: CRITICAL None checks
    if not message.from_user:
        logger.error("[ADMIN] message.from_user is None in process_free_model_id")
        await message.answer("❌ Ошибка: не удалось определить пользователя.")
        return
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        await state.clear()
        return
    
    model_id = message.text.strip()
    
    # Save to state
    await state.update_data(free_model_id=model_id)
    await state.set_state(AdminStates.enter_free_limits)
    
    text = (
        f"➕ <b>Настройка лимитов</b>\n\n"
        f"Модель: <code>{model_id}</code>\n\n"
        f"Введите лимиты в формате:\n"
        f"<code>daily hourly</code>\n\n"
        f"Например: <code>5 2</code> (5 в день, 2 в час)\n"
        f"Или просто <code>5</code> (только дневной лимит)"
    )
    
    await message.answer(text)


@router.message(AdminStates.enter_free_limits)
async def process_free_limits(message: Message, state: FSMContext):
    """Process free limits."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        await state.clear()
        return
    
    data = await state.get_data()
    model_id = data.get("free_model_id")
    
    parts = message.text.strip().split()
    
    try:
        daily_limit = int(parts[0])
        hourly_limit = int(parts[1]) if len(parts) > 1 else 2
    except (ValueError, IndexError) as e:
        # MASTER PROMPT: No bare except - specific exception types for parseInt errors
        logger.error(f"Failed to parse free model limits from '{message.text}': {e}")
        await message.answer("❌ Неверный формат. Попробуйте ещё раз:")
        return
    
    # Add free model
    await _admin_service.set_model_free(
        admin_id=message.from_user.id,
        model_id=model_id,
        daily_limit=daily_limit,
        hourly_limit=hourly_limit
    )
    
    text = (
        f"✅ <b>Модель настроена</b>\n\n"
        f"<code>{model_id}</code>\n"
        f"Лимиты: {daily_limit}/день, {hourly_limit}/час"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Управление моделями", callback_data="admin:models")],
        [InlineKeyboardButton(text="◀️ В админку", callback_data="admin:main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data == "admin:models:stats")
async def cb_admin_models_stats(callback: CallbackQuery):
    """Show models statistics."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_models_stats")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_models_stats")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    # BUTTON TRACE
    from app.utils.correlation import ensure_correlation_id
    from app.observability.button_trace import (
        log_button_received,
        log_button_routed,
        log_button_accepted,
        log_button_rejected,
    )
    from app.observability.v2 import log_ui_render
    
    cid = ensure_correlation_id(str(callback.id))
    update_id = getattr(callback, "update_id", None)
    user_id = callback.from_user.id if callback.from_user else None
    callback_data = callback.data or "admin:models:stats"
    
    log_button_received(cid=cid, callback_data=callback_data, update_id=update_id, user_id=user_id)
    log_button_routed(cid=cid, callback_data=callback_data, handler_name="cb_admin_models_stats", update_id=update_id)
    
    if not is_admin(callback.from_user.id):
        log_button_rejected(cid=cid, callback_data=callback_data, handler_name="cb_admin_models_stats", update_id=update_id, reason="not_admin")
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    log_button_accepted(cid=cid, callback_data=callback_data, handler_name="cb_admin_models_stats", update_id=update_id, reason="admin_authorized")
    
    # Fail-open: handle DB unavailability gracefully
    try:
        from app.admin.analytics import Analytics
        
        analytics = Analytics(_db_service)
        top_models = await analytics.get_top_models(limit=10)
        
        text = f"📊 <b>Топ-10 моделей</b>\n\n"
        
        for i, model in enumerate(top_models, 1):
            model_id = model['model_id']
            uses = model['total_uses']
            revenue = model['revenue']
            success_rate = model['success_rate']
            
            text += f"{i}. <code>{model_id}</code>\n"
            text += f"   Использований: {uses}, Revenue: {format_price_rub(revenue)}\n"
            text += f"   Success rate: {success_rate:.1f}%\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:models")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        # Fail-open: log warning without traceback, show user-friendly message
        logger.warning(f"[ADMIN_MODELS_STATS] Top models failed (non-critical): {e}")
        await callback.message.edit_text(
            "📊 <b>Топ-10 моделей</b>\n\n"
            "⚠️ Статистика временно недоступна\n\n"
            "Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:models")]
            ])
        )
        await callback.answer("Статистика недоступна", show_alert=False)


# ========== USERS MANAGEMENT ==========

@router.callback_query(F.data == "admin:users")
async def cb_admin_users(callback: CallbackQuery):
    """Users management."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_users")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_users")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    text = (
        f"👥 <b>Управление пользователями</b>\n\n"
        f"Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin:users:find")],
        [InlineKeyboardButton(text="💰 Начислить баланс", callback_data="admin:users:topup")],
        [InlineKeyboardButton(text="💸 Списать баланс", callback_data="admin:users:charge")],
        [InlineKeyboardButton(text="🚫 Заблокировать", callback_data="admin:users:ban")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:users:topup")
async def cb_admin_users_topup(callback: CallbackQuery, state: FSMContext):
    """Topup user balance (placeholder - requires user_id input)."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_users_topup")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_users_topup")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "💰 <b>Начисление баланса</b>\n\n"
        "Эта функция требует ввода user_id.\n"
        "Используйте команду /admin_user <user_id> для просмотра пользователя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:users")]
        ])
    )


@router.callback_query(F.data == "admin:users:charge")
async def cb_admin_users_charge(callback: CallbackQuery, state: FSMContext):
    """Charge user balance (placeholder - requires user_id input)."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "💸 <b>Списание баланса</b>\n\n"
        "Эта функция требует ввода user_id.\n"
        "Используйте команду /admin_user <user_id> для просмотра пользователя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:users")]
        ])
    )


@router.callback_query(F.data == "admin:users:ban")
async def cb_admin_users_ban(callback: CallbackQuery, state: FSMContext):
    """Ban user (placeholder - requires user_id input)."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    await callback.message.edit_text(
        "🚫 <b>Блокировка пользователя</b>\n\n"
        "Эта функция требует ввода user_id.\n"
        "Используйте команду /admin_user <user_id> для просмотра пользователя.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:users")]
        ])
    )


@router.callback_query(F.data == "admin:users:find")
async def cb_admin_users_find(callback: CallbackQuery, state: FSMContext):
    """Find user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    text = (
        f"🔍 <b>Поиск пользователя</b>\n\n"
        f"Введите user_id:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:users")]
    ])
    
    await state.set_state(AdminStates.select_user_for_action)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(AdminStates.select_user_for_action)
async def process_user_find(message: Message, state: FSMContext):
    """Process user search."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        await state.clear()
        return
    
    try:
        user_id = int(message.text.strip())
    except ValueError as e:
        # MASTER PROMPT: No bare except - specific exception type for parseInt
        logger.error(f"Failed to parse user_id from '{message.text}': {e}")
        await message.answer("❌ Неверный формат. Введите числовой user_id:")
        return
    
    # Get user info
    user_info = await _admin_service.get_user_info(user_id)
    
    if not user_info:
        await message.answer(f"❌ Пользователь {user_id} не найден")
        await state.clear()
        return
    
    # Format info
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"ID: <code>{user_info['user_id']}</code>\n"
        f"Username: @{user_info['username'] or '—'}\n"
        f"Имя: {user_info['first_name'] or '—'}\n"
        f"Роль: {user_info['role']}\n\n"
        f"<b>Баланс:</b>\n"
        f"💰 Доступно: {format_price_rub(user_info['balance']['balance_rub'])}\n"
        f"🔒 В резерве: {format_price_rub(user_info['balance']['hold_rub'])}\n\n"
        f"<b>Статистика:</b>\n"
        f"Генераций: {user_info['stats']['total_jobs']} (успешных: {user_info['stats']['success_jobs']})\n"
        f"Потрачено: {format_price_rub(user_info['stats']['total_spent'])}\n"
        f"Free использований: {user_info['free_usage']['total_all_time']} (сегодня: {user_info['free_usage']['total_today']})\n\n"
        f"Зарегистрирован: {user_info['created_at'].strftime('%d.%m.%Y %H:%M')}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:users")]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    await state.clear()


# ========== ANALYTICS ==========

@router.callback_query(F.data == "admin:analytics")
async def cb_admin_analytics(callback: CallbackQuery):
    """Show analytics."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_analytics")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_analytics")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    # BUTTON TRACE: received → routed → accepted/rejected
    from app.utils.correlation import ensure_correlation_id, get_correlation_id
    from app.observability.button_trace import (
        log_button_received,
        log_button_routed,
        log_button_accepted,
        log_button_rejected,
    )
    from app.observability.v2 import log_ui_render
    import time
    
    cid = ensure_correlation_id(str(callback.id))
    update_id = getattr(callback, "update_id", None)
    user_id = callback.from_user.id if callback.from_user else None
    callback_data = callback.data or "admin:analytics"
    
    log_button_received(
        cid=cid,
        callback_data=callback_data,
        update_id=update_id,
        user_id=user_id,
    )
    
    log_button_routed(
        cid=cid,
        callback_data=callback_data,
        handler_name="cb_admin_analytics",
        update_id=update_id,
    )
    
    start_time = time.time()
    
    if not is_admin(callback.from_user.id):
        log_button_rejected(
            cid=cid,
            callback_data=callback_data,
            handler_name="cb_admin_analytics",
            update_id=update_id,
            reason="not_admin",
        )
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    log_button_accepted(
        cid=cid,
        callback_data=callback_data,
        handler_name="cb_admin_analytics",
        update_id=update_id,
        reason="admin_authorized",
    )
    
    # Fail-open: handle DB unavailability gracefully
    try:
        from app.admin.analytics import Analytics
        
        analytics = Analytics(_db_service)
        
        # Get stats (all methods are fail-open)
        revenue_stats = await analytics.get_revenue_stats(period_days=30)
        activity_stats = await analytics.get_user_activity(period_days=7)
        conversion = await analytics.get_free_to_paid_conversion()
        
        # Check if DB was unavailable (all stats are empty)
        if not _db_service or (revenue_stats.get('total_revenue', 0) == 0 and 
                              activity_stats.get('total_users', 0) == 0 and
                                conversion.get('total_free_users', 0) == 0):
            text = (
                f"📊 <b>Аналитика</b>\n\n"
                f"⚠️ База данных недоступна\n"
                f"Статистика временно недоступна.\n\n"
                f"Проверьте подключение к БД."
            )
        else:
            text = (
                f"📊 <b>Аналитика</b>\n\n"
                f"<b>Выручка (30 дней):</b>\n"
                f"💰 Revenue: {format_price_rub(revenue_stats['total_revenue'])}\n"
                f"💵 Topups: {format_price_rub(revenue_stats['total_topups'])}\n"
                f"↩️ Refunds: {format_price_rub(revenue_stats['total_refunds'])}\n"
                f"👥 Платящих: {revenue_stats['paying_users']}\n"
                f"📈 ARPU: {format_price_rub(revenue_stats['avg_revenue_per_user'])}\n\n"
                f"<b>Активность (7 дней):</b>\n"
                f"👤 Новых: {activity_stats['new_users']}\n"
                f"✅ Активных: {activity_stats['active_users']}\n"
                f"📊 Всего: {activity_stats['total_users']}\n\n"
                f"<b>Free → Paid конверсия:</b>\n"
                f"Free users: {conversion['total_free_users']}\n"
                f"Converted: {conversion['converted_users']}\n"
                f"Rate: {conversion['conversion_rate']:.1f}%"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 Топ моделей", callback_data="admin:models:stats")],
            [InlineKeyboardButton(text="❌ Ошибки", callback_data="admin:analytics:errors")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
        # BUTTON TRACE: ui_render
        log_ui_render(
            cid=cid,
            screen_id="admin:analytics",
            user_id=user_id,
            reason="analytics_displayed",
        )
        
        await callback.answer()
        
    except Exception as e:
        # Fail-open: log warning without traceback, show user-friendly message
        logger.warning(f"[ADMIN_ANALYTICS] Analytics failed (non-critical): {e}")
        await callback.message.edit_text(
            "📊 <b>Аналитика</b>\n\n"
            "⚠️ Статистика временно недоступна\n\n"
            "Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
            ])
        )
        await callback.answer("Статистика недоступна", show_alert=False)


@router.callback_query(F.data == "admin:analytics:errors")
async def cb_admin_analytics_errors(callback: CallbackQuery):
    """Show error stats."""
    # BUTTON TRACE
    from app.utils.correlation import ensure_correlation_id
    from app.observability.button_trace import (
        log_button_received,
        log_button_routed,
        log_button_accepted,
        log_button_rejected,
    )
    from app.observability.v2 import log_ui_render
    
    cid = ensure_correlation_id(str(callback.id))
    update_id = getattr(callback, "update_id", None)
    user_id = callback.from_user.id if callback.from_user else None
    callback_data = callback.data or "admin:analytics:errors"
    
    log_button_received(cid=cid, callback_data=callback_data, update_id=update_id, user_id=user_id)
    log_button_routed(cid=cid, callback_data=callback_data, handler_name="cb_admin_analytics_errors", update_id=update_id)
    
    if not is_admin(callback.from_user.id):
        log_button_rejected(cid=cid, callback_data=callback_data, handler_name="cb_admin_analytics_errors", update_id=update_id, reason="not_admin")
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    log_button_accepted(cid=cid, callback_data=callback_data, handler_name="cb_admin_analytics_errors", update_id=update_id, reason="admin_authorized")
    
    # Fail-open: handle DB unavailability gracefully
    try:
        from app.admin.analytics import Analytics
        
        analytics = Analytics(_db_service)
        errors = await analytics.get_error_stats(limit=10)
        
        text = f"❌ <b>Ошибки генерации</b>\n\n"
        
        if not errors:
            text += "<i>Нет ошибок</i>"
        else:
            for error in errors:
                model_id = error['model_id']
                count = error['fail_count']
                last_fail = error['last_fail'].strftime('%d.%m %H:%M')
                text += f"• <code>{model_id}</code>\n  Ошибок: {count}, последняя: {last_fail}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:analytics")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        
        # BUTTON TRACE: ui_render
        log_ui_render(cid=cid, screen_id="admin:analytics:errors", user_id=user_id, reason="error_stats_displayed")
        
        await callback.answer()
        
    except Exception as e:
        # Fail-open: log warning without traceback, show user-friendly message
        logger.warning(f"[ADMIN_ANALYTICS] Error stats failed (non-critical): {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибки генерации</b>\n\n"
            "⚠️ Статистика временно недоступна\n\n"
            "Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:analytics")]
            ])
        )
        await callback.answer("Статистика недоступна", show_alert=False)


# ========== ADMIN LOG ==========

@router.callback_query(F.data == "admin:log")
async def cb_admin_log(callback: CallbackQuery):
    """Show admin actions log."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_log")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_log")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    log = await _admin_service.get_admin_log(limit=20)
    
    text = f"📜 <b>Лог действий</b> (последние 20)\n\n"
    
    if not log:
        text += "<i>Лог пуст</i>"
    else:
        for entry in log:
            admin_id = entry['admin_id']
            action = entry['action_type']
            target = entry['target_id'] or '—'
            created = entry['created_at'].strftime('%d.%m %H:%M')
            
            text += f"• {created}: Admin {admin_id}\n  {action} → {target}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:models:broken")
async def cb_admin_models_broken(callback: CallbackQuery, state: FSMContext):
    """Show models without valid input_schema."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    # Load registry and find broken models
    from app.ui.marketing_menu import load_registry
    
    registry = load_registry()
    broken_models = []
    
    for model in registry:
        if model.get("type") != "model":
            continue
        
        # Check if model has valid schema
        input_schema = model.get("input_schema", {})
        properties = input_schema.get("properties", {})
        
        if not input_schema or not properties:
            model_id = model.get("model_id", "unknown")
            price = model.get("price", 0)
            is_pricing_known = model.get("is_pricing_known", False)
            broken_models.append({
                "model_id": model_id,
                "price": price,
                "enabled": is_pricing_known
            })
    
    if not broken_models:
        text = (
            f"✅ <b>Все модели валидны</b>\n\n"
            f"Нет моделей без input_schema"
        )
    else:
        text = (
            f"⚠️ <b>Модели без input_schema</b>\n\n"
            f"Найдено: {len(broken_models)}\n\n"
            f"Эти модели скрыты от пользователей:\n\n"
        )
        
        for m in broken_models[:10]:  # Limit to 10
            status = "🟢" if m["enabled"] else "🔴"
            text += f"{status} {m['model_id']}\n"
            text += f"   Цена: {m['price']} RUB\n\n"
        
        if len(broken_models) > 10:
            text += f"... ещё {len(broken_models) - 10} моделей\n\n"
        
        text += (
            f"<b>Решение:</b>\n"
            f"• Enrichment через KIE API\n"
            f"• Ручное добавление schema\n"
            f"• Используется fallback (prompt-only)"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:models")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:main")
async def cb_admin_main(callback: CallbackQuery, state: FSMContext):
    """Return to admin main menu."""
    # P0-1: CRITICAL None checks
    if not callback.from_user:
        logger.error("[ADMIN] callback.from_user is None in cb_admin_main")
        await callback.answer("❌ Ошибка: не удалось определить пользователя.", show_alert=True)
        return
    if not callback.message:
        logger.error("[ADMIN] callback.message is None in cb_admin_main")
        await callback.answer("❌ Ошибка: сообщение недоступно.", show_alert=True)
        return
    
    await state.clear()
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    text = (
        f"🛠 <b>Админ-панель</b>\n\n"
        f"Главное меню"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Управление моделями", callback_data="admin:models")],
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin:users")],
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="admin:analytics")],
        [InlineKeyboardButton(text="📜 Лог действий", callback_data="admin:log")],
        [InlineKeyboardButton(text="📟 Что нового", callback_data="admin:changelog")],
        [InlineKeyboardButton(text="◀️ Закрыть", callback_data="admin:close")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:changelog")
async def cb_admin_changelog(callback: CallbackQuery):
    """Show last 5 changes from CHANGELOG.md."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    # P0-4: Read changelog file (fail-open if missing)
    changelog_path = Path(__file__).parent.parent.parent / "CHANGELOG.md"
    text = "📟 <b>Что нового</b>\n\n"
    
    try:
        if changelog_path.exists():
            content = changelog_path.read_text(encoding="utf-8")
            # Extract last 5 entries (simple parsing - look for ## [version] patterns)
            lines = content.split("\n")
            entries = []
            current_entry = []
            in_entry = False
            
            for line in lines:
                if line.startswith("## ["):
                    if in_entry and current_entry:
                        entries.append("\n".join(current_entry))
                    current_entry = [line]
                    in_entry = True
                elif in_entry:
                    current_entry.append(line)
                    # Limit entry size (Telegram message limit ~4096 chars)
                    if len("\n".join(current_entry)) > 3000:
                        current_entry.append("...")
                        break
            
            if in_entry and current_entry:
                entries.append("\n".join(current_entry))
            
            # Take last 5 entries
            last_5 = entries[-5:] if len(entries) > 5 else entries
            if last_5:
                text += "\n\n".join(last_5)
                # Truncate if too long
                if len(text) > 4000:
                    text = text[:4000] + "\n\n... (полный changelog в репозитории)"
            else:
                text += "Нет записей в changelog."
        else:
            text += "⚠️ Файл CHANGELOG.md не найден."
    except Exception as e:
        logger.warning(f"[ADMIN_CHANGELOG] Failed to read changelog (fail-open): {e}")
        text += "⚠️ Не удалось загрузить changelog. Попробуйте позже."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin:main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:models:resync")
async def cb_admin_models_resync(callback: CallbackQuery):
    """Resync models from Kie API."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("🔄 Запуск ресинка...", show_alert=True)
    
    # Показываем процесс
    await callback.message.edit_text(
        "🔄 <b>Ресинк моделей</b>\n\n"
        "⏳ Загрузка моделей из Kie API...\n"
        "Это может занять несколько минут."
    )
    
    try:
        import subprocess
        import asyncio
        
        # Запускаем скрипт синхронизации
        process = await asyncio.create_subprocess_exec(
            "python3",
            "scripts/build_registry_v3.py",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/workspaces/5656"
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Успех
            output = stdout.decode('utf-8')
            
            # Парсим результаты (простой подсчёт строк с "• ")
            models_count = output.count("• ")
            
            text = (
                f"✅ <b>Ресинк завершён!</b>\n\n"
                f"📊 Синхронизировано моделей: {models_count}\n\n"
                f"<i>Source of truth обновлён</i>"
            )
        else:
            # Ошибка
            error = stderr.decode('utf-8')
            text = (
                f"❌ <b>Ошибка ресинка</b>\n\n"
                f"<code>{error[:500]}</code>"
            )
    
    except Exception as e:
        logger.error(f"Resync error: {e}", exc_info=True)
        text = (
            f"❌ <b>Ошибка</b>\n\n"
            f"{str(e)}"
        )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к моделям", callback_data="admin:models")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


# Export
__all__ = ["router", "set_services"]
