#!/usr/bin/env python3
"""
Production entrypoint for Render deployment.
Single, explicit initialization path with no fallbacks.
"""
import asyncio
import logging
import os
import signal
import sys
from typing import Optional, Tuple

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Explicit imports - no try/except, no importlib, no fallbacks
from app.utils.singleton_lock import acquire_singleton_lock, release_singleton_lock
from app.utils.healthcheck import start_healthcheck_server, stop_healthcheck_server, set_health_state
from app.storage.pg_storage import PGStorage, PostgresStorage
from bot.handlers import flow_router, zero_silence_router, error_handler_router

# Import aiogram components
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


async def preflight_webhook(bot: Bot) -> None:
    """Delete webhook before starting polling to avoid conflicts."""
    result = await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Webhook deleted: %s", result)


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
    dp = Dispatcher()
    
    # Register routers in order (flow first for /start and main UX)
    dp.include_router(flow_router)
    dp.include_router(zero_silence_router)
    dp.include_router(error_handler_router)
    
    logger.info("Bot application created successfully")
    return dp, bot


async def main():
    """
    Main entrypoint - explicit initialization sequence.
    No fallbacks, no try/except for imports.
    """
    logger.info("Starting bot application...")
    
    # Shutdown event for graceful termination
    shutdown_event = asyncio.Event()
    
    def signal_handler(sig):
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()
    
    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    healthcheck_server = None
    port = int(os.getenv("PORT", "10000"))
    if port:
        healthcheck_server, _ = start_healthcheck_server(port)
        logger.info("Healthcheck server started on port %s", port)

    dry_run = os.getenv("DRY_RUN", "0").lower() in {"1", "true", "yes"}
    bot_mode = os.getenv("BOT_MODE", "polling").lower()

    # Step 1: Acquire singleton lock (if DATABASE_URL provided and not DRY_RUN)
    lock_acquired = False
    database_url = os.getenv("DATABASE_URL")
    if database_url and not dry_run:
        lock_acquired = await acquire_singleton_lock(dsn=database_url, timeout=5.0)
        if not lock_acquired:
            logger.warning("Singleton lock not acquired - another instance is running. Running in passive mode (healthcheck only).")
            set_health_state("passive", "lock_not_acquired")
            # Passive mode: keep healthcheck running, but NO polling
            logger.info("Passive mode: healthcheck available, polling disabled")
            # Wait for shutdown signal
            try:
                await shutdown_event.wait()
                logger.info("Passive mode shutting down gracefully")
            except asyncio.CancelledError:
                logger.info("Passive mode interrupted")
            finally:
                stop_healthcheck_server(healthcheck_server)
            return
        logger.info("Singleton lock acquired successfully - running in active mode")
        set_health_state("active", "lock_acquired")
    else:
        if dry_run:
            logger.info("DRY_RUN enabled - skipping singleton lock")
            lock_acquired = True  # Allow DRY_RUN to proceed
            set_health_state("active", "dry_run_mode")
    
    # Step 2: Initialize storage (if DATABASE_URL provided and not DRY_RUN)
    storage = None
    if database_url and not dry_run:
        storage = PostgresStorage(dsn=database_url)
        await storage.initialize()
        logger.info("PostgreSQL storage initialized")
    else:
        if dry_run:
            logger.info("DRY_RUN enabled - skipping storage initialization")
    
    # Step 3: Create bot application
    try:
        dp, bot = create_bot_application()
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

    # Step 4: Check BOT_MODE guard
    if bot_mode != "polling":
        logger.info(f"BOT_MODE={bot_mode} is not ''polling'' - skipping polling startup")
        await bot.session.close()
        if storage:
            await storage.close()
        await release_singleton_lock()
        stop_healthcheck_server(healthcheck_server)
        return

    # Step 5: Preflight - delete webhook before polling
    await preflight_webhook(bot)

    # Step 6: Start polling
    try:
        logger.info("Starting bot polling...")
        # Use create_task to allow cancellation by shutdown signal
        polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        
        # Wait for either polling to finish or shutdown signal
        done, pending = await asyncio.wait(
            [polling_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # If shutdown signaled, cancel polling
        if shutdown_event.is_set():
            logger.info("Shutdown signal received, stopping polling...")
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                logger.info("Polling cancelled successfully")
        else:
            # Polling finished naturally, check result
            for task in done:
                if task == polling_task and task.exception():
                    raise task.exception()
                    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except asyncio.CancelledError:
        logger.info("Bot polling cancelled")
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