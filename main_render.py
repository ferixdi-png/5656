#!/usr/bin/env python3
"""
Production entrypoint for Render deployment.
Single, explicit initialization path with no fallbacks.
"""
import asyncio
import logging
import os
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
from app.storage.pg_storage import PGStorage, PostgresStorage
from bot.handlers import zero_silence_router, error_handler_router

# Import aiogram components
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


def create_bot_application() -> Tuple[Dispatcher, Bot]:
    """
    Create and configure bot application.
    
    Returns:
        Tuple of (Dispatcher, Bot) instances
        
    Raises:
        ValueError: If BOT_TOKEN is not set
    """
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable is required")
    
    # Create bot with explicit configuration
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Create dispatcher
    dp = Dispatcher()
    
    # Register routers in order
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
    
    # Step 1: Acquire singleton lock (if DATABASE_URL provided)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        lock_acquired = await acquire_singleton_lock(dsn=database_url, timeout=5.0)
        if not lock_acquired:
            logger.warning("Singleton lock not acquired - another instance may be running")
    
    # Step 2: Initialize storage (if DATABASE_URL provided)
    storage = None
    if database_url:
        storage = PostgresStorage(dsn=database_url)
        await storage.initialize()
        logger.info("PostgreSQL storage initialized")
    
    # Step 3: Create bot application
    try:
        dp, bot = create_bot_application()
    except ValueError as e:
        logger.error(f"Failed to create bot application: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error creating bot application: {e}", exc_info=True)
        sys.exit(1)
    
    # Step 4: Start polling
    try:
        logger.info("Starting bot polling...")
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error during bot polling: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        if storage:
            await storage.close()
        await release_singleton_lock()
        await bot.session.close()
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

