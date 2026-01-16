#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Singleton Lock - гарантирует только один экземпляр бота запущен
Поддерживает Redis lock (если доступен) и file lock (fallback)
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения lock
_lock_instance: Optional['SingletonLock'] = None


class SingletonLock:
    """Singleton lock для предотвращения множественных экземпляров бота"""
    
    def __init__(self, lock_key: str = "telegram_bot_polling"):
        self.lock_key = lock_key
        self.redis_client = None
        self.file_lock_path = None
        self.file_lock_handle = None
        self._acquired = False
        
        # Пробуем Redis lock
        self._init_redis()
        
        # Если Redis недоступен, используем file lock
        if not self.redis_client:
            self._init_file_lock()
    
    def _init_redis(self):
        """Инициализация Redis lock"""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return
        
        try:
            import redis
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Проверяем подключение
            self.redis_client.ping()
            logger.info("✅ Redis lock available")
        except ImportError:
            logger.debug("Redis not installed, using file lock")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using file lock")
            self.redis_client = None
    
    def _init_file_lock(self):
        """Инициализация file lock"""
        if sys.platform == 'win32':
            # Windows: используем временную директорию
            lock_dir = Path(os.getenv("TEMP", os.getenv("TMP", "/tmp")))
        else:
            # Linux: используем /tmp
            lock_dir = Path("/tmp")
        
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.file_lock_path = lock_dir / f"{self.lock_key}.lock"
        logger.info(f"File lock path: {self.file_lock_path}")
    
    def acquire(self, timeout: int = 5) -> bool:
        """
        Пытается получить lock
        Returns: True если lock получен, False если другой экземпляр уже работает
        """
        if self._acquired:
            return True
        
        # Пробуем Redis lock
        if self.redis_client:
            try:
                # SETNX с TTL (30 секунд, обновляется каждые 10 секунд)
                result = self.redis_client.set(
                    self.lock_key,
                    f"{os.getpid()}:{time.time()}",
                    nx=True,
                    ex=30
                )
                if result:
                    self._acquired = True
                    logger.info(f"✅ Redis lock acquired: {self.lock_key}")
                    # Запускаем background task для обновления TTL
                    self._start_redis_renewal()
                    return True
                else:
                    logger.warning(f"⚠️ Redis lock already held by another instance: {self.lock_key}")
                    return False
            except Exception as e:
                logger.warning(f"Redis lock failed: {e}, trying file lock")
        
        # Fallback: file lock
        if self.file_lock_path:
            try:
                if sys.platform == 'win32':
                    # Windows: используем msvcrt
                    import msvcrt
                    self.file_lock_handle = open(self.file_lock_path, 'w')
                    try:
                        msvcrt.locking(self.file_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                        self.file_lock_handle.write(f"{os.getpid()}:{time.time()}\n")
                        self.file_lock_handle.flush()
                        self._acquired = True
                        logger.info(f"✅ File lock acquired: {self.file_lock_path}")
                        return True
                    except IOError:
                        self.file_lock_handle.close()
                        self.file_lock_handle = None
                        logger.warning(f"⚠️ File lock already held: {self.file_lock_path}")
                        return False
                else:
                    # Linux: используем fcntl
                    import fcntl
                    self.file_lock_handle = open(self.file_lock_path, 'w')
                    try:
                        fcntl.flock(self.file_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        self.file_lock_handle.write(f"{os.getpid()}:{time.time()}\n")
                        self.file_lock_handle.flush()
                        self._acquired = True
                        logger.info(f"✅ File lock acquired: {self.file_lock_path}")
                        return True
                    except IOError:
                        self.file_lock_handle.close()
                        self.file_lock_handle = None
                        logger.warning(f"⚠️ File lock already held: {self.file_lock_path}")
                        return False
            except Exception as e:
                logger.error(f"File lock failed: {e}")
                return False
        
        # Если оба метода не сработали, разрешаем запуск (но логируем предупреждение)
        logger.warning("⚠️ No lock mechanism available, allowing startup (may cause conflicts)")
        return True
    
    def _start_redis_renewal(self):
        """Запускает background task для обновления Redis lock TTL"""
        if not self.redis_client or not self._acquired:
            return
        
        def renew_lock():
            while self._acquired:
                try:
                    time.sleep(10)
                    if self._acquired and self.redis_client:
                        self.redis_client.expire(self.lock_key, 30)
                except Exception as e:
                    logger.error(f"Redis lock renewal failed: {e}")
                    break
        
        import threading
        renewal_thread = threading.Thread(target=renew_lock, daemon=True)
        renewal_thread.start()
    
    def release(self):
        """Освобождает lock"""
        if not self._acquired:
            return
        
        self._acquired = False
        
        # Освобождаем Redis lock
        if self.redis_client:
            try:
                self.redis_client.delete(self.lock_key)
                logger.info("✅ Redis lock released")
            except Exception as e:
                logger.error(f"Failed to release Redis lock: {e}")
        
        # Освобождаем file lock
        if self.file_lock_handle:
            try:
                if sys.platform != 'win32':
                    import fcntl
                    fcntl.flock(self.file_lock_handle.fileno(), fcntl.LOCK_UN)
                self.file_lock_handle.close()
                if self.file_lock_path and self.file_lock_path.exists():
                    self.file_lock_path.unlink()
                logger.info("✅ File lock released")
            except Exception as e:
                logger.error(f"Failed to release file lock: {e}")
            finally:
                self.file_lock_handle = None
    
    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Failed to acquire singleton lock")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def get_singleton_lock(lock_key: str = "telegram_bot_polling") -> SingletonLock:
    """Получает глобальный экземпляр singleton lock"""
    global _lock_instance
    if _lock_instance is None:
        _lock_instance = SingletonLock(lock_key)
    return _lock_instance






