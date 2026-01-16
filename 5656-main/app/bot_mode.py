#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Mode Manager - строгое разделение polling и webhook
Гарантирует что только один режим активен
"""

import os
import logging
from typing import Literal
from telegram import Bot
from telegram.error import Conflict

logger = logging.getLogger(__name__)

from app.utils.webhook import get_webhook_base_url, get_webhook_secret_token

BotMode = Literal["polling", "webhook"]


def get_bot_mode() -> BotMode:
    """
    Получает режим работы бота из ENV
    Default: polling для локальной разработки, webhook для Render Web Service
    """
    mode = os.getenv("BOT_MODE", "").lower().strip()
    
    # Автоопределение для Render
    if not mode:
        # Если есть PORT и WEBHOOK_BASE_URL/WEBHOOK_URL - вероятно webhook режим
        if os.getenv("PORT") and get_webhook_base_url():
            mode = "webhook"
        else:
            mode = "polling"
    
    if mode not in ["polling", "webhook"]:
        logger.warning(f"Invalid BOT_MODE={mode}, defaulting to polling")
        mode = "polling"
    
    logger.info(f"📡 Bot mode: {mode}")
    return mode


async def ensure_polling_mode(bot: Bot) -> bool:
    """
    Гарантирует что бот в polling режиме
    Удаляет webhook перед запуском polling
    
    Returns:
        True если готов к polling, False если ошибка
    """
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.warning(f"⚠️ Webhook detected: {webhook_info.url}, removing...")
            result = await bot.delete_webhook(drop_pending_updates=True)
            logger.info(f"✅ Webhook deleted: {result}")
            
            # Проверяем что webhook действительно удалён
            webhook_info_after = await bot.get_webhook_info()
            if webhook_info_after.url:
                logger.error(f"❌ Webhook still active: {webhook_info_after.url}")
                return False
            
            logger.info("✅ Webhook confirmed deleted, ready for polling")
        else:
            logger.info("✅ No webhook set, ready for polling")
        
        return True
    except Conflict as e:
        logger.error(f"❌ Conflict detected while ensuring polling mode: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Error ensuring polling mode: {e}")
        return False


async def ensure_webhook_mode(bot: Bot, webhook_url: str) -> bool:
    """
    Гарантирует что бот в webhook режиме
    Устанавливает webhook и проверяет что polling не запущен
    
    Returns:
        True если готов к webhook, False если ошибка
    """
    if not webhook_url:
        logger.error("❌ WEBHOOK_BASE_URL not set for webhook mode")
        return False
    
    try:
        # Устанавливаем webhook
        secret_token = get_webhook_secret_token()
        if secret_token:
            result = await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                secret_token=secret_token,
            )
        else:
            result = await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
            )
        logger.info(f"✅ Webhook set: {result}")
        
        # Проверяем что webhook установлен
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url != webhook_url:
            logger.error(f"❌ Webhook not set correctly: {webhook_info.url} != {webhook_url}")
            return False
        
        logger.info(f"✅ Webhook confirmed: {webhook_info.url}")
        return True
    except Conflict as e:
        logger.error(f"❌ Conflict detected while setting webhook: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
        return False


def handle_conflict_gracefully(error: Conflict, mode: BotMode) -> None:
    """
    Graceful обработка Conflict ошибки
    Логирует и завершает процесс без агрессивных retry
    
    КРИТИЧНО: Использует os._exit(0) для немедленного завершения,
    чтобы предотвратить повторные конфликты и остановить polling loop немедленно.
    """
    logger.error(f"❌❌❌ Conflict detected in {mode} mode: {error}")
    logger.error("   Another instance is already running")
    logger.error("   Exiting gracefully to allow orchestrator restart")
    
    # НЕ делаем retry, НЕ перезапускаем - просто выходим
    # os._exit(0) завершает процесс немедленно, обходя cleanup handlers
    # Это предотвращает повторные конфликты и останавливает polling loop
    import os
    os._exit(0)




