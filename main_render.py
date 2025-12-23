#!/usr/bin/env python3
"""
Production entrypoint for Render deployment.
Single, explicit initialization path with no fallbacks.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Tuple

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Explicit imports - no try/except, no importlib, no fallbacks
from app.utils.singleton_lock import acquire_singleton_lock, release_singleton_lock
from app.utils.healthcheck import start_healthcheck_server, stop_healthcheck_server
from app.utils.runtime_state import runtime_state
from app.storage.pg_storage import PGStorage, PostgresStorage
from bot.handlers import flow_router, zero_silence_router, error_handler_router, diag_router

# Import aiogram components
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError


def create_bot_application() -> Tuple[Dispatcher, Bot]:
    """
    Create and configure bot application.
    
    Returns:
        Tuple of (Dispatcher, Bot) instances
        
    Raises:
        ValueError: If TELEGRAM_BOT_TOKEN is not set
    """
    dry_run = os.getenv("DRY_RUN", "0").lower() in {"1", "true", "yes"}
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if dry_run and (not bot_token or ":" not in bot_token):
        bot_token = "123456:TEST"
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    
    # Create bot with explicit configuration
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Create dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register routers in order
    dp.include_router(flow_router)
    dp.include_router(zero_silence_router)
    dp.include_router(diag_router)
    dp.include_router(error_handler_router)
    
    logger.info("Bot application created successfully")
    return dp, bot


def build_application() -> Tuple[Dispatcher, Bot]:
    """Single entrypoint for building the bot application."""
    return create_bot_application()


async def preflight_webhook(bot: Bot) -> None:
    """Delete webhook before polling."""
    result = await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Webhook deleted: %s", result)


async def main():
    """
    Main entrypoint - explicit initialization sequence.
    No fallbacks, no try/except for imports.
    """
    logger.info("Starting bot application...")
    runtime_state.last_start_time = datetime.now(timezone.utc).isoformat()
    
    healthcheck_server = None
    port = int(os.getenv("PORT", "10000"))
    if port:
        healthcheck_server, _ = start_healthcheck_server(port)
        logger.info("Healthcheck server started on port %s", port)

    dry_run = os.getenv("DRY_RUN", "0").lower() in {"1", "true", "yes"}
    runtime_state.bot_mode = os.getenv("BOT_MODE", "polling")
    runtime_state.storage_mode = os.getenv("STORAGE_MODE", "auto")

    # Step 1: Acquire singleton lock (if DATABASE_URL provided)
    database_url = os.getenv("DATABASE_URL")
    if database_url and not dry_run:
        lock_acquired = await acquire_singleton_lock(dsn=database_url, timeout=5.0)
        runtime_state.lock_acquired = lock_acquired
        if not lock_acquired:
            logger.warning("Singleton lock not acquired - another instance may be running")
        else:
            logger.info("SINGLE_INSTANCE: ok")
    else:
        runtime_state.lock_acquired = True
    
    # Step 2: Initialize storage (if DATABASE_URL provided)
    storage = None
    if database_url and not dry_run:
        storage = PostgresStorage(dsn=database_url)
        await storage.initialize()
        logger.info("PostgreSQL storage initialized")
    
    # Step 3: Create bot application
    try:
        dp, bot = build_application()
    except ValueError as e:
        logger.error(f"Failed to create bot application: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error creating bot application: {e}", exc_info=True)
        sys.exit(1)
    
    if dry_run:
        logger.info("DRY_RUN enabled - skipping polling startup")
        await bot.session.close()
        if storage:
            await storage.close()
        await release_singleton_lock()
        stop_healthcheck_server(healthcheck_server)
        return
    if runtime_state.lock_acquired is False:
        logger.warning("Passive mode: instance without lock will not start polling")
        await bot.session.close()
        if storage:
            await storage.close()
        logger.info("Passive mode: healthcheck only")
        await asyncio.Event().wait()
        return
    if runtime_state.bot_mode != "polling":
        logger.info("BOT_MODE=%s - polling disabled", runtime_state.bot_mode)
        await bot.session.close()
        if storage:
            await storage.close()
        await release_singleton_lock()
        stop_healthcheck_server(healthcheck_server)
        return

    await preflight_webhook(bot)

    # Step 4: Start polling
    try:
        logger.info("Starting bot polling...")
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except TelegramConflictError:
        logger.error("Polling conflict detected — another instance is running")
        logger.warning("Passive mode: skipping polling to avoid conflict")
    except Exception as e:
        logger.error(f"Error during bot polling: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        if storage:
            await storage.close()
        await release_singleton_lock()
        await bot.session.close()
        stop_healthcheck_server(healthcheck_server)
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
