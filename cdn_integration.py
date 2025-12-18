"""
Модуль для интеграции с CDN для медиа-файлов.
"""

import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# CDN конфигурация
CDN_CONFIG = {
    'enabled': True,
    'base_url': None,  # Будет установлено из env
    'cache_ttl': 3600,  # 1 час
    'supported_formats': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'webm']
}


def get_cdn_url(original_url: str, format: Optional[str] = None) -> str:
    """
    Получает CDN URL для медиа-файла.
    
    Args:
        original_url: Оригинальный URL файла
        format: Формат файла (опционально)
    
    Returns:
        CDN URL или оригинальный URL, если CDN не настроен
    """
    if not CDN_CONFIG.get('enabled'):
        return original_url
    
    cdn_base = CDN_CONFIG.get('base_url')
    if not cdn_base:
        # Пытаемся получить из env
        import os
        cdn_base = os.getenv('CDN_BASE_URL')
        if cdn_base:
            CDN_CONFIG['base_url'] = cdn_base
        else:
            return original_url
    
    # В реальной реализации здесь будет загрузка файла в CDN
    # Пока возвращаем оригинальный URL
    logger.debug(f"🌐 CDN URL для {original_url}: {cdn_base}")
    return original_url


def is_cdn_supported_format(file_url: str) -> bool:
    """
    Проверяет, поддерживается ли формат файла CDN.
    
    Args:
        file_url: URL файла
    
    Returns:
        True, если формат поддерживается
    """
    parsed = urlparse(file_url)
    path = parsed.path.lower()
    
    for fmt in CDN_CONFIG['supported_formats']:
        if path.endswith(f'.{fmt}'):
            return True
    
    return False


def upload_to_cdn(file_url: str) -> Optional[str]:
    """
    Загружает файл в CDN.
    
    Args:
        file_url: URL файла для загрузки
    
    Returns:
        CDN URL или None
    """
    if not CDN_CONFIG.get('enabled'):
        return None
    
    if not is_cdn_supported_format(file_url):
        logger.warning(f"⚠️ Формат файла {file_url} не поддерживается CDN")
        return None
    
    # В реальной реализации здесь будет загрузка в CDN
    # Пока возвращаем None
    logger.info(f"📤 Загрузка в CDN: {file_url}")
    return None

