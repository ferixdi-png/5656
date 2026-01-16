"""
Application configuration - Settings class and get_settings function
Loads configuration from environment variables with validation
"""

import os
import sys
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

from app.utils.webhook import (
    build_webhook_url,
    get_webhook_base_url,
    get_webhook_secret_path,
    get_webhook_secret_token,
)

# Глобальный экземпляр settings (singleton)
_settings: Optional['Settings'] = None

# Явный экспорт для импорта
__all__ = ['Settings', 'get_settings', 'reset_settings']


class Settings:
    """Application settings loaded from environment variables"""
    
    def __init__(self, validate: bool = False):
        """Инициализирует настройки из environment variables"""
        
        # Обязательные переменные
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        if not self.telegram_bot_token:
            if validate:
                logger.error("=" * 60)
                logger.error("MISSING REQUIRED ENVIRONMENT VARIABLE")
                logger.error("=" * 60)
                logger.error("TELEGRAM_BOT_TOKEN is required but not set")
                logger.error("Please set TELEGRAM_BOT_TOKEN in environment variables")
                logger.error("=" * 60)
                sys.exit(1)
            else:
                logger.warning("TELEGRAM_BOT_TOKEN not set - bot will not work")
        
        # Опциональные переменные с дефолтами
        admin_id_str = os.getenv('ADMIN_ID', '0')
        try:
            self.admin_id = int(admin_id_str) if admin_id_str else 0
        except ValueError:
            self.admin_id = 0
            logger.warning(f"Invalid ADMIN_ID: {admin_id_str}, using 0")
        
        self.database_url = os.getenv('DATABASE_URL', '').strip()
        self.kie_api_key = os.getenv('KIE_API_KEY', '').strip()
        self.kie_api_url = (
            os.getenv('KIE_API_URL', '').strip()
            or os.getenv('KIE_BASE_URL', '').strip()
            or 'https://api.kie.ai'
        )
        
        # Runtime configuration
        self.test_mode = os.getenv('TEST_MODE', '0') == '1'
        self.dry_run = os.getenv('DRY_RUN', '0') == '1'
        self.allow_real_generation = os.getenv('ALLOW_REAL_GENERATION', '1') != '0'
        
        # Storage configuration
        self.storage_mode = os.getenv('STORAGE_MODE', 'auto').lower()
        self.data_dir = os.getenv('DATA_DIR', '/app/data')
        
        # Bot mode
        self.bot_mode = os.getenv('BOT_MODE', 'polling').lower()
        self.webhook_base_url = get_webhook_base_url()
        self.webhook_secret_path = get_webhook_secret_path(self.telegram_bot_token)
        self.webhook_secret_token = get_webhook_secret_token()
        self.webhook_url = build_webhook_url(self.webhook_base_url, self.webhook_secret_path)
        
        # Port for healthcheck
        port_str = os.getenv('PORT', '0')
        try:
            self.port = int(port_str) if port_str else 0
        except ValueError:
            self.port = 0
            logger.warning(f"Invalid PORT: {port_str}, using 0 (no healthcheck)")
        
        # Payment configuration (optional)
        self.payment_phone = os.getenv('PAYMENT_PHONE', '').strip()
        self.payment_bank = os.getenv('PAYMENT_BANK', '').strip()
        self.payment_card_holder = os.getenv('PAYMENT_CARD_HOLDER', '').strip()
        
        # Support configuration (optional)
        self.support_telegram = os.getenv('SUPPORT_TELEGRAM', '').strip()
        self.support_text = os.getenv('SUPPORT_TEXT', '').strip()
        
        # Pricing
        credit_rate_str = os.getenv('CREDIT_TO_RUB_RATE', '0.1')
        try:
            self.credit_to_rub_rate = float(credit_rate_str)
        except ValueError:
            self.credit_to_rub_rate = 0.1
            logger.warning(f"Invalid CREDIT_TO_RUB_RATE: {credit_rate_str}, using 0.1")
        
        # Currency conversion
        usd_to_rub_str = os.getenv('USD_TO_RUB', '100.0')
        try:
            self.usd_to_rub = float(usd_to_rub_str)
        except ValueError:
            self.usd_to_rub = 100.0
            logger.warning(f"Invalid USD_TO_RUB: {usd_to_rub_str}, using 100.0")
        
        # Price multiplier (×2 для пользовательских цен)
        price_multiplier_str = os.getenv('PRICE_MULTIPLIER', '2.0')
        try:
            self.price_multiplier = float(price_multiplier_str)
        except ValueError:
            self.price_multiplier = 2.0
            logger.warning(f"Invalid PRICE_MULTIPLIER: {price_multiplier_str}, using 2.0")
    
    def get_storage_mode(self) -> str:
        """
        Определяет режим хранения данных.
        
        Returns:
            'postgres' если DATABASE_URL доступен, иначе 'json'
        """
        if self.storage_mode == 'postgres':
            return 'postgres'
        elif self.storage_mode == 'json':
            return 'json'
        elif self.storage_mode == 'auto':
            # AUTO режим: пробуем определить автоматически
            if self.database_url:
                return 'postgres'
            else:
                return 'json'
        else:
            # Неизвестный режим - используем auto логику
            if self.database_url:
                return 'postgres'
            else:
                return 'json'
    
    def validate(self):
        """Валидирует обязательные настройки"""
        errors = []
        
        if not self.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        
        if errors:
            error_msg = "\n".join(f"  - {err}" for err in errors)
            logger.error("=" * 60)
            logger.error("CONFIGURATION VALIDATION FAILED")
            logger.error("=" * 60)
            logger.error(error_msg)
            logger.error("=" * 60)
            raise ValueError("Configuration validation failed")
    
    @classmethod
    def from_env(cls, validate: bool = False) -> 'Settings':
        """Создает Settings из environment variables"""
        return cls(validate=validate)


def get_settings(validate: bool = False) -> Settings:
    """
    Получить глобальный экземпляр Settings (singleton)
    
    Args:
        validate: Если True, валидирует обязательные поля при создании
    
    Returns:
        Settings instance
    """
    global _settings
    
    if _settings is None:
        _settings = Settings.from_env(validate=validate)
    
    return _settings


def reset_settings():
    """Сбросить глобальный экземпляр settings (для тестов)"""
    global _settings
    _settings = None
