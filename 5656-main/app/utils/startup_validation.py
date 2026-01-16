"""
Startup validation - проверка обязательных ENV переменных при старте
"""

import os
import sys
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Keep imports after logger setup to avoid circular dependencies
from app.utils.webhook import get_webhook_base_url
# Импортируем mask на уровне модуля для безопасности
try:
    from app.utils.mask import mask
except ImportError:
    # Fallback если mask недоступен
    def mask(value: str) -> str:
        if not value:
            return '[EMPTY]'
        if len(value) <= 8:
            return '****'
        return f"{value[:2]}...{value[-2:]}"

# Обязательные ENV ключи (контракт)
REQUIRED_ENV_KEYS = [
    'ADMIN_ID',
    'BOT_MODE',
    'DATABASE_URL',
    'DB_MAXCONN',
    'KIE_API_KEY',
    'PAYMENT_BANK',
    'PAYMENT_CARD_HOLDER',
    'PAYMENT_PHONE',
    'PORT',
    'SUPPORT_TELEGRAM',
    'SUPPORT_TEXT',
    'TELEGRAM_BOT_TOKEN',
    'WEBHOOK_BASE_URL',
]

# Webhook security (при BOT_MODE=webhook) - настоятельно рекомендуется
WEBHOOK_RECOMMENDED_KEYS = [
    'WEBHOOK_SECRET_PATH',
    'WEBHOOK_SECRET_TOKEN',
    'KIE_CALLBACK_PATH',
    'KIE_CALLBACK_TOKEN',
]

def validate_env_keys() -> Tuple[bool, List[str]]:
    """
    Валидирует наличие всех обязательных ENV ключей.
    
    Returns:
        Tuple[bool, List[str]]: (is_valid, missing_keys)
    """
    missing = []
    
    for key in REQUIRED_ENV_KEYS:
        value = os.getenv(key, '').strip()
        if not value:
            missing.append(key)
    
    return len(missing) == 0, missing


def validate_env_key_format(key: str) -> bool:
    """
    Валидирует формат значения ENV ключа (базовая проверка).
    
    Args:
        key: Имя ENV переменной
        
    Returns:
        True если значение валидно, False иначе
    """
    value = os.getenv(key, '').strip()
    
    if not value:
        return False
    
    # Специфичные проверки для некоторых ключей
    if key == 'ADMIN_ID':
        try:
            int(value)
            return True
        except ValueError:
            return False
    
    if key == 'PORT':
        try:
            port = int(value)
            return 1 <= port <= 65535
        except ValueError:
            return False
    
    if key == 'DB_MAXCONN':
        try:
            maxconn = int(value)
            return maxconn > 0
        except ValueError:
            return False
    
    if key == 'BOT_MODE':
        return value.lower() in ('polling', 'webhook', 'auto', 'passive')
    
    if key == 'DATABASE_URL':
        # Validate PostgreSQL URL format
        if not value.startswith(('postgresql://', 'postgres://')):
            return False
        try:
            from urllib.parse import urlparse
            parsed = urlparse(value)
            # Check required components
            if not parsed.hostname or not parsed.path:
                return False
            # Path should be database name (non-empty after /)
            if len(parsed.path) < 2:  # At least "/dbname"
                return False
            return True
        except Exception:
            return False
    
    # Для остальных - просто проверяем что не пусто
    return True


def validate_webhook_requirements() -> None:
    """
    Validate webhook-specific requirements.

    CRITICAL: Checks all required variables for webhook mode to prevent runtime errors.
    
    Raises:
        ValueError: if webhook mode is enabled but required variables are missing.
    """
    mode = os.getenv("BOT_MODE", "").lower().strip()
    if mode != "webhook":
        return

    # Check required webhook variables
    missing = []
    webhook_base = get_webhook_base_url()
    if not webhook_base:
        missing.append("WEBHOOK_BASE_URL")
    
    # Check recommended security variables (warn but don't fail)
    webhook_secret_path = os.getenv("WEBHOOK_SECRET_PATH", "").strip()
    webhook_secret_token = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip()
    if not webhook_secret_path or not webhook_secret_token:
        logger.warning(
            "[WEBHOOK_SECURITY] WEBHOOK_SECRET_PATH and WEBHOOK_SECRET_TOKEN are recommended "
            "for production webhook security"
        )
    
    if missing:
        raise ValueError(
            f"Webhook mode requires the following environment variables: {', '.join(missing)}"
        )


def startup_validation() -> bool:
    """
    Выполняет полную валидацию при старте приложения.
    
    Returns:
        True если все проверки пройдены, иначе False (и выходит с sys.exit)
    """
    logger.info("=" * 60)
    logger.info("STARTUP VALIDATION")
    logger.info("=" * 60)
    
    # Проверка наличия ключей
    is_valid, missing = validate_env_keys()
    
    if not is_valid:
        logger.error("=" * 60)
        logger.error("MISSING REQUIRED ENVIRONMENT VARIABLES")
        logger.error("=" * 60)
        for key in missing:
            logger.error(f"  - {key}")
        logger.error("=" * 60)
        logger.error("Please set all required environment variables.")
        logger.error("See docs/env.md for details.")
        logger.error("=" * 60)
        sys.exit(1)
    
    # Проверка формата значений
    format_errors = []
    for key in REQUIRED_ENV_KEYS:
        if not validate_env_key_format(key):
            format_errors.append(key)
    
    if format_errors:
        logger.error("=" * 60)
        logger.error("INVALID ENVIRONMENT VARIABLE FORMATS")
        logger.error("=" * 60)
        for key in format_errors:
            value = os.getenv(key, '')
            # Маскируем значение для безопасности
            masked_value = mask(value) if value else '[EMPTY]'
            logger.error(f"  - {key}: {masked_value}")
        logger.error("=" * 60)
        logger.error("Please check environment variable formats.")
        logger.error("See docs/env.md for details.")
        logger.error("=" * 60)
        sys.exit(1)

    # Проверка webhook requirements
    try:
        validate_webhook_requirements()
    except ValueError as e:
        logger.error("=" * 60)
        logger.error("INVALID WEBHOOK CONFIGURATION")
        logger.error("=" * 60)
        logger.error(str(e))
        logger.error("=" * 60)
        sys.exit(1)
    
    # Логируем успех (без значений)
    logger.info("✅ All required environment variables are set")
    logger.info(f"✅ Validated {len(REQUIRED_ENV_KEYS)} environment variables")
    logger.info("=" * 60)
    
    return True
