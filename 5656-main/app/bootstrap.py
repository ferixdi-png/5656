"""
Bootstrap - создание Application с dependency container
Все зависимости хранятся в application.bot_data["deps"]
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from telegram.ext import Application
from telegram import Bot

from app.config import Settings, get_settings
from app.storage import get_storage
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class DependencyContainer:
    """Контейнер зависимостей для бота"""
    
    def __init__(self):
        self.settings: Optional[Settings] = None
        self.storage = None
        self.kie_client = None
        self.lock_conn = None
        self.lock_key_int: Optional[int] = None
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.active_generations: Dict[int, Dict[str, Any]] = {}
        self.active_generations_lock = asyncio.Lock()
        self.saved_generations: Dict[int, list] = {}
        
    async def initialize(self, settings: Settings):
        """Инициализирует все зависимости"""
        self.settings = settings
        
        # Инициализация storage
        try:
            self.storage = get_storage()
            # CRITICAL: Always use async_test_connection in async runtime
            if hasattr(self.storage, 'async_test_connection'):
                test_result = await self.storage.async_test_connection()
                if test_result:
                    logger.info("[OK] Storage initialized (async test passed)")
                else:
                    logger.warning("[WARN] Storage async connection test failed")
            else:
                logger.info("[OK] Storage initialized (no async test available)")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize storage: {e}")
            # Мягкая деградация - продолжаем без storage
            self.storage = None
        
        # Инициализация KIE client (ленивая, при первом использовании)
        # Не инициализируем здесь, чтобы избежать side effects при импорте
        
        # Инициализация singleton lock (ленивая)
        # Не инициализируем здесь, чтобы избежать side effects при импорте
        
        logger.info("[OK] Dependency container initialized")
    
    def get_storage(self):
        """Получить storage"""
        return self.storage
    
    def get_kie_client(self):
        """Получить KIE client (ленивая инициализация)"""
        if self.kie_client is None:
            # Ленивая инициализация при первом использовании
            try:
                from kie_client import KieClient
                if self.settings and self.settings.kie_api_key:
                    self.kie_client = KieClient(
                        api_key=self.settings.kie_api_key,
                        api_url=self.settings.kie_api_url or "https://api.kie.ai"
                    )
                    logger.info("[OK] KIE client initialized")
                else:
                    logger.warning("[WARN] KIE_API_KEY not set, KIE client not available")
            except ImportError:
                logger.warning("[WARN] kie_client module not found")
            except Exception as e:
                logger.error(f"[ERROR] Failed to initialize KIE client: {e}")
        
        return self.kie_client


def get_deps(application: Application) -> DependencyContainer:
    """
    Получить dependency container из application
    
    Args:
        application: Telegram Application
        
    Returns:
        DependencyContainer
    """
    if "deps" not in application.bot_data:
        # Создаем если еще нет
        application.bot_data["deps"] = DependencyContainer()
    
    return application.bot_data["deps"]


async def create_application(settings: Optional[Settings] = None) -> Application:
    """
    Создает Telegram Application с dependency container
    
    Args:
        settings: Настройки (если None, загружаются из env)
        
    Returns:
        Application с инициализированными зависимостями
    """
    if settings is None:
        settings = get_settings()
    
    # Создаем Application с post_init для обработки ошибок updater
    async def post_init(app: Application) -> None:
        """Post-init hook для обработки ошибок updater"""
        # Обработчик ошибок уже добавлен в bot_kie.py, но убеждаемся что он есть
        logger.debug("[BOOTSTRAP] Post-init hook called")
    
    # Создаем Application с post_init
    application = Application.builder().token(settings.telegram_bot_token).post_init(post_init).build()
    
    # Инициализируем dependency container
    deps = DependencyContainer()
    await deps.initialize(settings)
    application.bot_data["deps"] = deps
    
    logger.info("[OK] Application created with dependency container")
    
    return application


async def build_application(settings: Optional[Settings] = None) -> Application:
    """
    Создает и настраивает Application (alias для create_application)
    
    Args:
        settings: Настройки (если None, загружаются из env)
        
    Returns:
        Application с инициализированными зависимостями
    """
    return await create_application(settings)


