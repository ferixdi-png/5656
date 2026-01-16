"""
Admin panel handlers for telegram bot.

Provides admin-only commands for:
- Viewing error logs
- Statistics (users, generations, balance)
- Managing models (enable/disable)
- System health checks
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
router = Router()

# Admin IDs (will be set from config)
ADMIN_IDS = set()


def set_admin_ids(admin_ids: list[int]) -> None:
    """Configure admin IDs."""
    global ADMIN_IDS
    ADMIN_IDS = set(admin_ids)


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in ADMIN_IDS


def require_admin(user_id: int) -> bool:
    """Check admin status and log attempt."""
    if not is_admin(user_id):
        logger.warning(f"[ADMIN] Unauthorized access attempt from user {user_id}")
        return False
    return True


@router.message(Command("admin"))
async def cmd_admin(message: types.Message) -> None:
    """Show admin menu."""
    if not require_admin(message.from_user.id):
        await message.reply("❌ Unauthorized")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="❌ Error Logs (last 24h)", callback_data="admin_logs_24h")],
        [InlineKeyboardButton(text="🔧 Model Management", callback_data="admin_models")],
        [InlineKeyboardButton(text="🏥 System Health", callback_data="admin_health")],
        [InlineKeyboardButton(text="🗑️ Cleanup Logs", callback_data="admin_cleanup")],
    ])

    await message.reply(
        "🛡️ <b>Admin Panel</b>\n\n"
        "Select an option:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(lambda q: q.data == "admin_stats")
async def cb_admin_stats(query: types.CallbackQuery) -> None:
    """Show statistics."""
    if not require_admin(query.from_user.id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    try:
        from app.database.services import get_db_pool

        pool = get_db_pool()
        if not pool:
            await query.answer("❌ Database not available", show_alert=True)
            return

        async with pool.acquire() as conn:
            # Get user count
            user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            
            # Get total balance
            total_balance = await conn.fetchval(
                "SELECT COALESCE(SUM(balance_rub), 0) FROM wallets"
            )
            
            # Get today's generations count
            today = datetime.now().date()
            gen_count = await conn.fetchval(
                "SELECT COUNT(*) FROM ledger WHERE kind='charge' AND DATE(created_at)=$1",
                today
            )
            
            # Get error count (failed transactions)
            error_count = await conn.fetchval(
                "SELECT COUNT(*) FROM ledger WHERE status='failed'"
            )

        text = (
            "📊 <b>System Statistics</b>\n\n"
            f"👥 Total users: <code>{user_count}</code>\n"
            f"💰 Total balance: <code>{total_balance:.2f}₽</code>\n"
            f"📈 Today's generations: <code>{gen_count}</code>\n"
            f"❌ Errors total: <code>{error_count}</code>\n"
        )

        await query.message.edit_text(text, parse_mode="HTML")
        await query.answer()

    except Exception as e:
        logger.exception("Error getting stats: %s", e)
        await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@router.callback_query(lambda q: q.data == "admin_logs_24h")
async def cb_admin_logs(query: types.CallbackQuery) -> None:
    """Show error logs from last 24 hours."""
    if not require_admin(query.from_user.id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    try:
        from app.database.services import get_db_pool

        pool = get_db_pool()
        if not pool:
            await query.answer("❌ Database not available", show_alert=True)
            return

        since = datetime.now() - timedelta(hours=24)

        async with pool.acquire() as conn:
            # Get failed transactions
            failed = await conn.fetch(
                """
                SELECT id, user_id, kind, amount_rub, ref, created_at
                FROM ledger
                WHERE status='failed' AND created_at >= $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                since
            )

        if not failed:
            await query.message.edit_text(
                "✅ No errors in last 24 hours",
                parse_mode="HTML"
            )
        else:
            lines = ["❌ <b>Errors (last 24h, max 10)</b>\n"]
            for row in failed:
                lines.append(
                    f"• {row['kind']} {row['amount_rub']}₽ "
                    f"(user: {row['user_id']}, ref: {row['ref']})"
                )
            
            text = "\n".join(lines)
            await query.message.edit_text(text, parse_mode="HTML")

        await query.answer()

    except Exception as e:
        logger.exception("Error getting logs: %s", e)
        await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@router.callback_query(lambda q: q.data == "admin_models")
async def cb_admin_models(query: types.CallbackQuery) -> None:
    """Show model management interface."""
    if not require_admin(query.from_user.id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    try:
        from app.database.services import get_db_pool

        pool = get_db_pool()
        if not pool:
            await query.answer("❌ Database not available", show_alert=True)
            return

        async with pool.acquire() as conn:
            models = await conn.fetch(
                "SELECT model_id, enabled, daily_limit FROM free_models LIMIT 10"
            )

        if not models:
            text = "ℹ️ No free models configured yet"
        else:
            lines = ["🔧 <b>Free Models (first 10)</b>\n"]
            for model in models:
                status = "✅" if model['enabled'] else "❌"
                lines.append(
                    f"{status} {model['model_id']}\n"
                    f"   Limit: {model['daily_limit']}/day"
                )
            text = "\n".join(lines)

        await query.message.edit_text(text, parse_mode="HTML")
        await query.answer()

    except Exception as e:
        logger.exception("Error getting models: %s", e)
        await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@router.callback_query(lambda q: q.data == "admin_health")
async def cb_admin_health(query: types.CallbackQuery) -> None:
    """Show system health."""
    if not require_admin(query.from_user.id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    try:
        from app.database.services import get_db_pool

        pool = get_db_pool()
        
        checks = {
            "🗄️ Database": "✅" if pool else "❌",
            "🤖 Bot": "✅",  # If we're here, bot is running
            "⏰ Time": f"✅ {datetime.now().isoformat()}",
        }

        # Try to ping database
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                checks["🗄️ Database"] = "✅ OK"
            except Exception as e:
                checks["🗄️ Database"] = f"⚠️ {str(e)[:30]}"

        text = "🏥 <b>System Health</b>\n\n"
        text += "\n".join(f"{k}: {v}" for k, v in checks.items())

        await query.message.edit_text(text, parse_mode="HTML")
        await query.answer()

    except Exception as e:
        logger.exception("Error checking health: %s", e)
        await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


@router.callback_query(lambda q: q.data == "admin_cleanup")
async def cb_admin_cleanup(query: types.CallbackQuery) -> None:
    """Cleanup old logs."""
    if not require_admin(query.from_user.id):
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    try:
        from app.database.services import get_db_pool

        pool = get_db_pool()
        if not pool:
            await query.answer("❌ Database not available", show_alert=True)
            return

        # Delete logs older than 30 days
        cutoff = datetime.now() - timedelta(days=30)

        async with pool.acquire() as conn:
            deleted = await conn.fetchval(
                "DELETE FROM ledger WHERE created_at < $1 AND status IN ('done', 'failed')",
                cutoff
            )

        text = (
            f"🗑️ <b>Cleanup Complete</b>\n\n"
            f"Deleted {deleted} records older than 30 days"
        )

        await query.message.edit_text(text, parse_mode="HTML")
        await query.answer()
        logger.info(f"[ADMIN] Cleanup: deleted {deleted} old records")

    except Exception as e:
        logger.exception("Error during cleanup: %s", e)
        await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)
