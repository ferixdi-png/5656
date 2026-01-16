"""
Single instance lock - предотвращение 409 Conflict через единый механизм блокировки

Алгоритм:
- Если есть DATABASE_URL: использует PostgreSQL advisory lock через удержание соединения (session-level)
- Если DATABASE_URL нет: file lock в DATA_DIR (или /tmp как fallback)

ВАЖНО: Соединение держится открытым весь runtime для сохранения session-level lock.
"""

import os
import sys
import logging
import hashlib
import asyncio
from pathlib import Path
from typing import Optional, Literal

from app.utils.logging_config import get_logger
from app.config import get_settings
from app.utils.runtime_state import runtime_state

logger = get_logger(__name__)

# Lock configuration
LOCK_MODE_WAIT_PASSIVE = "wait_then_passive"  # Safe: wait, then passive if no lock
LOCK_MODE_WAIT_FORCE = "wait_then_force"      # Risky: force active even without lock
LOCK_DEFAULT_MODE = LOCK_MODE_WAIT_PASSIVE

# Retry configuration  
LOCK_WAIT_SECONDS = int(os.getenv('LOCK_WAIT_SECONDS', '60'))
LOCK_RETRY_BACKOFF_BASE = 0.5  # seconds
LOCK_RETRY_BACKOFF_MAX = 5.0   # seconds
LOCK_RETRY_INTERVAL_BG = 10    # seconds (background retry when in passive)

# Глобальное состояние lock
_lock_handle: Optional[object] = None
_lock_type: Optional[Literal['postgres', 'file']] = None
_lock_connection: Optional[object] = None  # PostgreSQL connection (для session-level lock)
_lock_mode: str = os.getenv('LOCK_MODE', LOCK_DEFAULT_MODE)
_is_active: bool = False  # True if lock acquired, False if passive
_bg_retry_task: Optional[asyncio.Task] = None  # Background task for lock retry


def get_lock_key() -> int:
    """
    Получить ключ для advisory lock (на основе BOT_TOKEN).
    
    Public function for use in diagnostics and logging.
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
    
    # Используем render_singleton_lock логику для совместимости
    namespace = "telegram_polling"
    combined = f"{namespace}:{bot_token}".encode('utf-8')
    
    # Используем SHA256 и берем первые 8 байт (64 бита) для bigint
    hash_bytes = hashlib.sha256(combined).digest()[:8]
    
    # Конвертируем в unsigned int64, затем приводим к signed bigint
    unsigned_key = int.from_bytes(hash_bytes, byteorder='big', signed=False)
    
    # Приводим к signed bigint
    MAX_BIGINT = 9223372036854775807
    lock_key = unsigned_key % (MAX_BIGINT + 1)
    
    return lock_key


def _get_lock_key() -> int:
    """Private alias for backward compatibility."""
    return get_lock_key()


def _acquire_postgres_lock() -> Optional[object]:
    """
    Пытается получить PostgreSQL advisory lock через session-level connection.
    
    КРИТИЧНО: Использует render_singleton_lock который АВТОМАТИЧЕСКИ убивает stale процессы
    и ждёт 3 секунды для освобождения lock. Retry НЕ НУЖЕН - lock получается в первой попытке.
    
    Returns:
        dict с 'connection' и 'lock_key' если lock получен, None если нет
    """
    try:
        # BATCH 48.20: NO DATABASE MODE - Skip PostgreSQL lock attempts silently
        no_db_mode = os.getenv('NO_DATABASE_MODE', '').lower() in ('1', 'true', 'yes')
        if no_db_mode:
            return None
        
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return None
        
        # BATCH 48.20: Check if asyncpg is available, silently skip if not
        try:
            import asyncpg
        except ImportError:
            return None
        
        # Пытаемся получить connection pool из database.py (psycopg2)
        # BATCH 48.20: Silent in NO DATABASE MODE
        try:
            from database import get_connection_pool
            pool = get_connection_pool()
        except Exception:
            return None
        
        if pool is None:
            return None
        
        # Используем render_singleton_lock для получения lock
        try:
            import render_singleton_lock
            
            lock_key = get_lock_key()
            
            # acquire_lock_session автоматически убивает stale процессы и ждёт 3s
            # Retry НЕ НУЖЕН - если lock не получен, значит другой АКТИВНЫЙ инстанс
            conn = render_singleton_lock.acquire_lock_session(pool, lock_key)
            if conn:
                instance_id = os.getenv("INSTANCE_NAME", runtime_state.instance_id)
                heartbeat_stop, _thread = render_singleton_lock.start_lock_heartbeat(
                    pool, lock_key, instance_id
                )
                logger.info(f"[LOCK] PostgreSQL advisory lock acquired (key={lock_key})")
                return {
                    'connection': conn,
                    'pool': pool,
                    'lock_key': lock_key,
                    'heartbeat_stop': heartbeat_stop,
                }
            
            logger.debug(f"[LOCK] PostgreSQL advisory lock NOT acquired (key={lock_key}) - another active instance")
            return None
        except ImportError:
            logger.debug("[LOCK] render_singleton_lock not available")
            return None
        except Exception as e:
            logger.debug(f"[LOCK] Failed to acquire PostgreSQL lock: {e}")
            return None
    
    except Exception as e:
        logger.debug(f"[LOCK] PostgreSQL lock acquisition failed: {e}")
        return None


def _acquire_file_lock() -> Optional[object]:
    """
    Пытается получить file lock.
    
    Returns:
        FileLock object если lock получен, None если нет
    """
    try:
        from filelock import FileLock, Timeout
        
        # Определяем путь к lock файлу
        settings = get_settings()
        data_dir = Path(settings.data_dir) if settings.data_dir else Path('/tmp')
        
        # Создаем директорию если не существует
        data_dir.mkdir(parents=True, exist_ok=True)
        lock_file = data_dir / 'bot_single_instance.lock'
        
        # Пробуем получить lock (non-blocking)
        lock = FileLock(lock_file, timeout=0.1)
        
        try:
            lock.acquire(timeout=0.1)
            logger.info(f"[LOCK] File lock acquired: {lock_file}")
            return lock
        except Timeout:
            logger.info(f"[LOCK] File lock NOT acquired: {lock_file} - another instance is running")
            return None
    
    except ImportError:
        logger.debug("[LOCK] filelock not available, skipping file lock")
        return None
    except Exception as e:
        logger.debug(f"[LOCK] Failed to acquire file lock: {e}")
        return None


# REMOVED: _force_release_stale_lock() was conceptually wrong
# Advisory locks are session-scoped and cannot be released from a different session
# On Render deploy overlap, we WAIT for old instance to release the lock naturally


def acquire_single_instance_lock() -> bool:
    """
    Попытаться получить single instance lock с retry и wait/passive логикой.
    
    Алгоритм:
    1. Пытается получить lock в течение LOCK_WAIT_SECONDS с exponential backoff
    2. Если lock получен -> ACTIVE mode (return True)
    3. Если не получен:
       - LOCK_MODE=wait_then_passive -> PASSIVE mode (return False)
       - LOCK_MODE=wait_then_force -> FORCE ACTIVE (return True, risky!)
    
    Returns:
        True если ACTIVE mode (lock acquired or forced)
        False если PASSIVE mode (webhook returns 200 but no side effects)
    """
    global _lock_handle, _lock_type, _lock_connection, _is_active
    
    # BATCH 48.22: NO DATABASE MODE - Skip PostgreSQL lock attempts silently
    no_db_mode = os.getenv('NO_DATABASE_MODE', '').lower() in ('1', 'true', 'yes')
    if no_db_mode:
        # Skip PostgreSQL lock, go directly to file lock (no logs)
        database_url = None
    else:
        # Check if asyncpg is available
        try:
            import asyncpg
        except ImportError:
            # Silent fallback to file lock
            database_url = None
        else:
            database_url = os.getenv('DATABASE_URL')
            # BATCH 48.22: Also check if database is actually available (DNS check)
            if database_url:
                # Quick check: if get_connection_pool() returns None, we're in NO DATABASE MODE
                try:
                    from database import get_connection_pool
                    pool = get_connection_pool()
                    if pool is None:
                        database_url = None  # Silent fallback to file lock
                except Exception:
                    database_url = None  # Silent fallback to file lock
    
    lock_mode = os.getenv('LOCK_MODE', LOCK_DEFAULT_MODE)
    
    # Пробуем PostgreSQL advisory lock с retry (only if database_url is available)
    if database_url:
        logger.info("[LOCK] Attempting to acquire PostgreSQL advisory lock...")
        logger.info(f"[LOCK] Mode: {lock_mode}, Wait: {LOCK_WAIT_SECONDS}s")
        
        import time
        start_time = time.time()
        attempt = 0
        
        while time.time() - start_time < LOCK_WAIT_SECONDS:
            lock_data = _acquire_postgres_lock()
            if lock_data:
                _lock_handle = lock_data
                _lock_connection = lock_data['connection']
                _lock_type = 'postgres'
                _is_active = True
                logger.info(f"[LOCK] ✅ ACTIVE MODE: PostgreSQL advisory lock acquired (attempt {attempt + 1})")
                return True
            
            # Exponential backoff
            attempt += 1
            backoff = min(LOCK_RETRY_BACKOFF_BASE * (2 ** attempt), LOCK_RETRY_BACKOFF_MAX)
            remaining = LOCK_WAIT_SECONDS - (time.time() - start_time)
            
            if remaining <= 0:
                break
                
            wait_time = min(backoff, remaining)
            logger.debug(f"[LOCK] Attempt {attempt} failed, retrying in {wait_time:.1f}s...")
            # BATCH 48.14: This function is called from sync context, so time.sleep is OK
            # The function acquire_single_instance_lock() is sync, not async
            time.sleep(wait_time)
        
        # Lock not acquired after wait period
        logger.info("=" * 60)
        logger.info(f"[LOCK] PostgreSQL advisory lock NOT acquired after {LOCK_WAIT_SECONDS}s")
        logger.info("[LOCK] This is normal during Render deploy overlap or NO DATABASE MODE")
        
        if lock_mode == LOCK_MODE_WAIT_FORCE:
            logger.info("[LOCK] ⚠️  FORCE ACTIVE MODE (risky!)")
            logger.info("[LOCK] Proceeding as ACTIVE despite missing lock")
            logger.info("[LOCK] WARNING: May cause conflicts if multiple instances running!")
            logger.info("=" * 60)
            _is_active = True
            return True
        else:
            logger.info("[LOCK] ⏸️  PASSIVE MODE: Webhook will return 200 but no processing")
            logger.info("[LOCK] Background retry task will attempt to acquire lock periodically")
            logger.info("=" * 60)
            _is_active = False
            return False
    
    # Fallback to filelock if no DATABASE_URL
    lock_handle = _acquire_file_lock()
    if lock_handle:
        _lock_handle = lock_handle
        _lock_connection = None
        _lock_type = 'file'
        _is_active = True
        logger.info("[LOCK] ✅ ACTIVE MODE: File lock acquired")
        return True
    
    # No lock mechanism available
    logger.info("[LOCK] ✅ No lock mechanism available (NO DATABASE MODE), proceeding as ACTIVE")
    _is_active = True
    return True


def release_single_instance_lock():
    """Освободить single instance lock"""
    global _lock_handle, _lock_type, _lock_connection
    
    if _lock_handle is None:
        return
    
    try:
        if _lock_type == 'postgres':
            # Освобождаем PostgreSQL advisory lock
            lock_data = _lock_handle
            if isinstance(lock_data, dict):
                conn = lock_data.get('connection')
                pool = lock_data.get('pool')
                lock_key = lock_data.get('lock_key')
                
                if conn and pool and lock_key is not None:
                    try:
                        import render_singleton_lock
                        render_singleton_lock.stop_lock_heartbeat(lock_data.get("heartbeat_stop"))
                        render_singleton_lock.release_lock_session(pool, conn, lock_key)
                        logger.info("[LOCK] PostgreSQL advisory lock released")
                    except Exception as e:
                        logger.warning(f"[LOCK] Failed to release PostgreSQL lock: {e}")
        
        elif _lock_type == 'file':
            # Освобождаем filelock
            _lock_handle.release()
            logger.info("[LOCK] File lock released")
    
    except Exception as e:
        logger.warning(f"[LOCK] Failed to release lock: {e}")
    finally:
        _lock_handle = None
        _lock_connection = None
        _lock_type = None


def is_lock_held() -> bool:
    """Проверить, удерживается ли lock"""
    return _lock_handle is not None and _lock_type is not None


def is_active_mode() -> bool:
    """
    Проверить, в ACTIVE ли режиме бот (lock получен или forced).
    PASSIVE mode: webhook returns 200 but no side effects.
    """
    return _is_active


async def start_background_lock_retry():
    """
    Запустить фоновую задачу для retry lock acquisition в PASSIVE режиме.
    Когда lock становится доступным, переключаемся в ACTIVE mode автоматически.
    """
    global _bg_retry_task
    
    if _is_active:
        logger.debug("[LOCK] Already in ACTIVE mode, no background retry needed")
        return
    
    if _bg_retry_task is not None:
        logger.debug("[LOCK] Background retry task already running")
        return
    
    async def _retry_loop():
        global _lock_handle, _lock_type, _lock_connection, _is_active
        
        logger.info("[LOCK] Starting background lock retry task...")
        attempt = 0
        while not _is_active:
            await asyncio.sleep(LOCK_RETRY_INTERVAL_BG)
            
            if _is_active:
                logger.info("[LOCK] Lock acquired by another path, stopping retry")
                break
            
            attempt += 1
            logger.info(f"[LOCK] Background retry attempt {attempt}...")
            
            # Try to acquire lock (synchronous call)
            try:
                lock_data = _acquire_postgres_lock()
                if lock_data:
                    _lock_handle = lock_data
                    _lock_connection = lock_data['connection']
                    _lock_type = 'postgres'
                    _is_active = True
                    logger.info("=" * 60)
                    logger.info(f"[LOCK] ✅ PASSIVE → ACTIVE: Lock acquired on retry {attempt}!")
                    logger.info("[LOCK] Bot now processing updates normally")
                    logger.info("=" * 60)
                    break
            except Exception as e:
                logger.warning(f"[LOCK] Background retry {attempt} failed: {e}")
    
    _bg_retry_task = asyncio.create_task(_retry_loop())
    logger.info("[LOCK] Background lock retry task started")


def stop_background_lock_retry():
    """Остановить фоновую задачу retry lock acquisition"""
    global _bg_retry_task
    
    if _bg_retry_task is not None:
        _bg_retry_task.cancel()
        _bg_retry_task = None
        logger.info("[LOCK] Background lock retry task stopped")

try:
    import psycopg
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


# Lock TTL in seconds (aggressive for zero-downtime rolling deployment)
LOCK_TTL = 10
HEARTBEAT_INTERVAL = 3  # Heartbeat more frequently to avoid false stale detection


class SingletonLock:
    """
    PostgreSQL advisory lock with stale detection using render_singleton_lock.
    
    CRITICAL: Uses render_singleton_lock for lock acquisition to ensure
    stale lock detection and termination works correctly.
    """
    
    def __init__(self, dsn: Optional[str] = None, instance_name: str = "bot-instance"):
        self.dsn = dsn
        self.instance_name = instance_name
        self._lock_handle = None  # dict with connection/pool/lock_key from render_singleton_lock
        self._acquired = False
        self._heartbeat_stop = None
    
    async def acquire(self, timeout: float = 5.0) -> bool:
        """
        Acquire singleton lock using render_singleton_lock (with stale detection).
        
        Args:
            timeout: Timeout in seconds for lock acquisition attempt (NOT USED - render_singleton_lock handles this)
        
        Returns:
            True if lock acquired, False otherwise
        """
        if not self.dsn:
            logger.warning("No database URL - running without singleton lock")
            return False
        
        try:
            # Use render_singleton_lock which has stale detection built-in
            lock_data = _acquire_postgres_lock()
            
            if lock_data:
                self._lock_handle = lock_data
                self._heartbeat_stop = lock_data.get("heartbeat_stop")
                self._acquired = True
                logger.info(f"✅ Singleton lock acquired by {self.instance_name}")
                return True
            else:
                logger.warning(f"⚠️ Singleton lock NOT acquired - another instance is active")
                return False
        
        except Exception as e:
            logger.error(f"Error acquiring singleton lock: {e}")
            return False
    
    async def release(self):
        """Release singleton lock using render_singleton_lock."""
        if not self._acquired:
            logger.debug("Lock already released or not acquired - skipping release")
            return
        
        logger.info(f"🔓 Starting lock release for {self.instance_name}...")
        self._acquired = False
        
        if not self._lock_handle:
            logger.warning("No lock handle available for lock release")
            return
        
        try:
            # Release advisory lock using render_singleton_lock
            lock_data = self._lock_handle
            if isinstance(lock_data, dict):
                conn = lock_data.get('connection')
                pool = lock_data.get('pool')
                lock_key = lock_data.get('lock_key')
                
                if conn and pool and lock_key is not None:
                    try:
                        import render_singleton_lock
                        render_singleton_lock.stop_lock_heartbeat(self._heartbeat_stop)
                        render_singleton_lock.release_lock_session(pool, conn, lock_key)
                        logger.info(f"✅ Singleton lock fully released by {self.instance_name}")
                    except Exception as e:
                        logger.error(f"❌ Error releasing lock: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ Error during lock release: {e}", exc_info=True)
        finally:
            self._lock_handle = None
            self._heartbeat_stop = None

    def get_lock_debug_info(self) -> dict:
        """Return diagnostic info about lock holder and heartbeat."""
        try:
            import render_singleton_lock
        except Exception:
            return {}

        lock_key = None
        pool = None
        if isinstance(self._lock_handle, dict):
            lock_key = self._lock_handle.get("lock_key")
            pool = self._lock_handle.get("pool")

        if not lock_key or not pool:
            return {}

        info = render_singleton_lock.get_lock_holder_info(pool, lock_key)
        info["takeover_event"] = render_singleton_lock.get_last_takeover_event()
        return info


def get_lock_debug_info() -> dict:
    """Return lock debug info for health endpoints."""
    info = {
        "state": "ACTIVE" if _is_active else "PASSIVE",
    }
    try:
        import render_singleton_lock
    except Exception:
        return info

    lock_key = None
    pool = None
    if isinstance(_lock_handle, dict):
        lock_key = _lock_handle.get("lock_key")
        pool = _lock_handle.get("pool")

    if lock_key and pool:
        info.update(render_singleton_lock.get_lock_holder_info(pool, lock_key))

    info["takeover_event"] = render_singleton_lock.get_last_takeover_event()
    return info


# Public exports for diagnostics and logging
__all__ = [
    "SingletonLock",
    "acquire_single_instance_lock",
    "release_single_instance_lock",
    "is_lock_held",
    "is_active_mode",
    "start_background_lock_retry",
    "stop_background_lock_retry",
    "get_lock_key",
    "get_lock_debug_info",
]
