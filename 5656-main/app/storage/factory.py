"""
Storage factory - автоматический выбор storage (JSON или PostgreSQL)
AUTO режим: если DATABASE_URL доступен и коннектится -> pg, иначе json
"""

import logging
import os
from typing import Optional

from app.storage.base import BaseStorage
from app.storage.json_storage import JsonStorage
from app.storage.pg_storage import PostgresStorage

logger = logging.getLogger(__name__)

# Глобальный экземпляр storage (singleton)
_storage_instance: Optional[BaseStorage] = None


def create_storage(
    storage_mode: Optional[str] = None,
    database_url: Optional[str] = None,
    data_dir: Optional[str] = None
) -> BaseStorage:
    """
    Создает storage instance
    
    Args:
        storage_mode: 'postgres', 'json', или 'auto' (default)
        database_url: URL базы данных (если None, берется из env)
        data_dir: Директория для JSON (если None, берется из env или './data')
    
    Returns:
        BaseStorage instance
    """
    global _storage_instance
    
    if _storage_instance is not None:
        return _storage_instance
    
    # Определяем режим
    if storage_mode is None:
        storage_mode = os.getenv('STORAGE_MODE', 'auto').lower()
    
    # AUTO режим: пробуем PostgreSQL, если не получается - FileStorage (NO DATABASE MODE)
    if storage_mode == 'auto':
        # BATCH 48.24: Check NO DATABASE MODE first
        no_db_mode = os.getenv('NO_DATABASE_MODE', '').lower() in ('1', 'true', 'yes')
        if no_db_mode:
            # Use FileStorage in NO DATABASE MODE
            from app.storage.file_storage import FileStorage
            _storage_instance = FileStorage()
            logger.info("[OK] Using FileStorage (NO DATABASE MODE)")
            return _storage_instance
        
        database_url = database_url or os.getenv('DATABASE_URL')
        
        if database_url:
            # BATCH 48.24: Check if database is actually available before creating PostgresStorage
            try:
                from database import get_connection_pool
                pool = get_connection_pool()
                if pool is None:
                    # Database unavailable - use FileStorage (NO DATABASE MODE - expected)
                    from app.storage.file_storage import FileStorage
                    _storage_instance = FileStorage()
                    logger.debug("[STORAGE] Using FileStorage (NO DATABASE MODE)")
                    return _storage_instance
            except Exception:
                # Database check failed - use FileStorage (NO DATABASE MODE - expected)
                from app.storage.file_storage import FileStorage
                _storage_instance = FileStorage()
                logger.debug("[STORAGE] Using FileStorage (NO DATABASE MODE)")
                return _storage_instance
            
            try:
                # Пробуем создать PostgreSQL storage
                pg_storage = PostgresStorage(database_url)
                # CRITICAL: Never call sync test_connection() - always use async version
                # Pool initialization will happen on first actual query
                logger.info("[OK] PostgreSQL storage initialized (pool will initialize on first query)")
                _storage_instance = pg_storage
                return _storage_instance
            except Exception as e:
                logger.warning(f"[WARN] PostgreSQL initialization failed: {e}, falling back to FileStorage")
        
        # Fallback на FileStorage (NO DATABASE MODE)
        from app.storage.file_storage import FileStorage
        _storage_instance = FileStorage()
        logger.info(f"[OK] Using FileStorage (AUTO mode fallback)")
        return _storage_instance
    
    # Явный режим
    if storage_mode == 'postgres':
        database_url = database_url or os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL is required for PostgreSQL storage")
        _storage_instance = PostgresStorage(database_url)
        logger.info("[OK] Using PostgreSQL storage (explicit mode)")
        return _storage_instance
    
    elif storage_mode == 'json':
        data_dir = data_dir or os.getenv('DATA_DIR', './data')
        _storage_instance = JsonStorage(data_dir)
        logger.info(f"[OK] Using JSON storage (explicit mode, data_dir={data_dir})")
        return _storage_instance
    
    else:
        raise ValueError(f"Invalid storage_mode: {storage_mode}. Use 'postgres', 'json', or 'auto'")


def get_storage() -> BaseStorage:
    """
    Получить текущий storage instance (singleton)
    
    Returns:
        BaseStorage instance
    """
    global _storage_instance
    
    if _storage_instance is None:
        _storage_instance = create_storage()
    
    return _storage_instance


def reset_storage() -> None:
    """Сбросить storage instance (для тестов)"""
    global _storage_instance
    _storage_instance = None


