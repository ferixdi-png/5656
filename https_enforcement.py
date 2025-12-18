"""
Модуль для обеспечения использования HTTPS для всех операций.
"""

import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def enforce_https(url: str) -> str:
    """
    Принудительно использует HTTPS для URL.
    
    Args:
        url: URL для проверки
    
    Returns:
        URL с HTTPS
    """
    if not url:
        return url
    
    parsed = urlparse(url)
    
    # Если URL использует HTTP, заменяем на HTTPS
    if parsed.scheme == 'http':
        url = url.replace('http://', 'https://', 1)
        logger.warning(f"⚠️ URL изменен с HTTP на HTTPS: {url}")
    
    return url


def validate_https_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, что URL использует HTTPS.
    
    Args:
        url: URL для проверки
    
    Returns:
        (валидно, сообщение_об_ошибке)
    """
    if not url:
        return False, "URL не может быть пустым"
    
    parsed = urlparse(url)
    
    if parsed.scheme not in ['https']:
        return False, "URL должен использовать HTTPS"
    
    return True, None


def ensure_https_for_api(base_url: str) -> str:
    """
    Обеспечивает использование HTTPS для API endpoint.
    
    Args:
        base_url: Базовый URL API
    
    Returns:
        URL с HTTPS
    """
    return enforce_https(base_url)

