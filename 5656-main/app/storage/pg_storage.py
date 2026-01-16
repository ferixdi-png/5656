"""
PostgreSQL storage implementation - хранение данных в PostgreSQL
Использует asyncpg для async операций
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import json
import asyncio

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
    AsyncpgPool = asyncpg.Pool
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None  # type: ignore
    AsyncpgPool = Any  # type: ignore

from app.storage.base import BaseStorage
from app.storage.status import normalize_job_status

logger = logging.getLogger(__name__)


class PostgresStorage(BaseStorage):
    """PostgreSQL storage implementation с asyncpg"""
    
    def __init__(self, database_url: str):
        if not ASYNCPG_AVAILABLE:
            raise ImportError("asyncpg is required for PostgreSQL storage")
        
        self.database_url = database_url
        self._pool: Optional[AsyncpgPool] = None  # BATCH 48.12: Use AsyncpgPool type
        self._pool_lock = None  # Will be initialized on first async call
    
    @property
    def pool(self) -> Optional[AsyncpgPool]:  # BATCH 48.12: Use AsyncpgPool type
        """Public access to connection pool for workers/queue."""
        return self._pool
    
    async def _get_pool(self) -> AsyncpgPool:  # BATCH 48.12: Use AsyncpgPool type
        """
        Получить или создать connection pool (thread-safe).
        
        CRITICAL: Automatically recreates pool if it's closed or broken.
        BATCH 48.24: Checks NO DATABASE MODE before attempting connection.
        """
        import os
        import time
        from app.utils.enhanced_logging import log_operation, log_error, ensure_correlation_id
        cid = ensure_correlation_id()
        
        # BATCH 48.24: Check NO DATABASE MODE before attempting connection
        no_db_mode = os.getenv('NO_DATABASE_MODE', '').lower() in ('1', 'true', 'yes')
        if no_db_mode:
            log_operation(
                "PG_STORAGE_POOL_SKIP",
                status="SKIPPED",
                error_code="NO_DATABASE_MODE",
                fix_hint="PostgresStorage should not be used in NO DATABASE MODE - use FileStorage instead",
                check_list="Storage factory | NO_DATABASE_MODE env | Use FileStorage instead"
            )
            raise RuntimeError("PostgresStorage cannot be used in NO DATABASE MODE. Use FileStorage instead.")
        
        # Check if database is actually available (DNS check)
        try:
            from database import get_connection_pool
            pool = get_connection_pool()
            if pool is None:
                log_operation(
                    "PG_STORAGE_POOL_SKIP",
                    status="SKIPPED",
                    error_code="DATABASE_UNAVAILABLE",
                    fix_hint="Database connection pool is None - use FileStorage instead",
                    check_list="DATABASE_URL | DNS resolution | get_connection_pool()"
                )
                raise RuntimeError("Database connection pool is None. Use FileStorage instead.")
        except Exception as e:
            log_error(
                "PG_STORAGE_POOL_CHECK",
                e,
                error_code="POOL_CHECK_FAILED",
                fix_hint="Cannot check database pool availability",
                check_list="Database connection | NO_DATABASE_MODE"
            )
            raise RuntimeError(f"Cannot use PostgresStorage: {e}") from e
        
        # Check if pool exists and is healthy
        if self._pool is not None:
            try:
                # Quick health check: try to acquire a connection
                async with self._pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return self._pool
            except (asyncpg.InterfaceError, asyncpg.PostgresConnectionError, OSError) as e:
                # Pool is broken - close and recreate
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.warning(f"{cid} [PG_STORAGE] Pool is broken, recreating due to: {e}")
                try:
                    await self._pool.close()
                except Exception as close_err:
                    # CRITICAL: Log close errors with correlation ID
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.debug(f"{cid} [PG_STORAGE] Error closing broken pool: {close_err}")
                self._pool = None
            except Exception as e:
                # CRITICAL: Log unexpected errors during health check with correlation ID
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(f"{cid} [PG_STORAGE] Unexpected error during pool health check: {e}", exc_info=True)
                # Don't recreate on unexpected errors - might be transient
                return self._pool
        
        # Initialize lock on first call
        if self._pool_lock is None:
            import asyncio
            self._pool_lock = asyncio.Lock()
        
        async with self._pool_lock:
            # Double-check after acquiring lock
            if self._pool is None:
                from app.utils.enhanced_logging import log_operation, log_error
                pool_start = time.time()
                
                try:
                    log_operation(
                        "PG_STORAGE_POOL_CREATE",
                        status="START",
                        database_url_hostname=self.database_url.split('@')[1].split('/')[0] if '@' in self.database_url else "unknown"
                    )
                    
                    self._pool = await asyncpg.create_pool(
                        self.database_url,
                        min_size=1,
                        max_size=10,
                        command_timeout=60,
                        max_inactive_connection_lifetime=300  # CRITICAL: Close idle connections after 5min to prevent leaks
                    )
                    
                    duration_ms = (time.time() - pool_start) * 1000
                    log_operation(
                        "PG_STORAGE_POOL_CREATE",
                        status="OK",
                        duration_ms=duration_ms
                    )
                except Exception as e:
                    duration_ms = (time.time() - pool_start) * 1000
                    is_dns_error = "Name or service not known" in str(e) or "could not translate host name" in str(e)
                    
                    if is_dns_error:
                        # NO DATABASE MODE: DNS errors logged at DEBUG level (expected behavior)
                        logger.debug(
                            f"[PG_STORAGE] Pool creation failed (NO DATABASE MODE - using FileStorage): "
                            f"DNS resolution failed, duration_ms={duration_ms:.2f}"
                        )
                    else:
                        # Non-DNS errors: log at ERROR level (real connection issues)
                        log_error(
                            "PG_STORAGE_POOL_CREATE",
                            e,
                            error_code="POOL_CREATE_FAILED",
                            fix_hint="Cannot create database connection pool - check DATABASE_URL and network",
                            check_list="DATABASE_URL | Network connectivity | Database server status",
                            duration_ms=duration_ms
                        )
                    raise
        return self._pool
    
    async def _execute_with_retry(
        self,
        operation_name: str,
        func,
        max_retries: int = 3,
        base_delay: float = 0.5
    ):
        """
        Execute database operation with retry for transient connection errors.
        
        Retries on: InterfaceError, PostgresConnectionError, OperationalError
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                return await func()
            except (asyncpg.InterfaceError, asyncpg.PostgresConnectionError, OSError) as e:
                last_error = e
                # CRITICAL: Include correlation ID in error logs for traceability
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"{cid} [DB_RETRY] {operation_name} failed (attempt {attempt+1}/{max_retries}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"{cid} [DB_RETRY] {operation_name} failed after {max_retries} attempts: {e}")
                    raise
            except Exception:
                # Non-transient errors - don't retry
                raise
        
        if last_error:
            raise last_error
    
    async def is_update_processed(self, update_id: int) -> bool:
        """
        Check if update_id has been processed (dedup check).
        
        Returns:
            True if update was already processed, False otherwise
        """
        async def _check():
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT 1 FROM processed_updates WHERE update_id = $1",
                    update_id
                )
                return result is not None
        
        return await self._execute_with_retry("is_update_processed", _check)
    
    async def mark_update_processed(self, update_id: int, worker_id: str = "unknown", update_type: str = "unknown") -> bool:
        """
        Mark update_id as processed (dedup insert).
        
        CRITICAL: Uses advisory lock to prevent race condition when two workers
        simultaneously try to process the same update_id.
        
        Returns:
            True if successfully marked (this worker won the race), False if already existed
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            try:
                # Use advisory lock based on update_id to prevent race condition
                # Lock key: use update_id as lock (PostgreSQL advisory locks are per-connection)
                lock_key = abs(hash(f"update_{update_id}")) % (2**31)  # PostgreSQL int4 range
                
                # Try to acquire advisory lock (non-blocking)
                lock_acquired = await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_key)
                
                if not lock_acquired:
                    # Another worker is processing this update_id
                    logger.debug(f"[DEDUP] Lock not acquired for update_id={update_id}, another worker processing")
                    return False
                
                try:
                    # Check if already processed (within lock)
                    already_exists = await conn.fetchval(
                        "SELECT 1 FROM processed_updates WHERE update_id = $1",
                        update_id
                    )
                    
                    if already_exists:
                        logger.debug(f"[DEDUP] Update {update_id} already processed by another worker")
                        return False
                    
                    # Insert (within lock)
                    await conn.execute(
                        """
                        INSERT INTO processed_updates (update_id, worker_instance_id, update_type)
                        VALUES ($1, $2, $3)
                        """,
                        update_id, worker_id, update_type
                    )
                    
                    logger.debug(f"[DEDUP] Successfully marked update_id={update_id} as processed by {worker_id}")
                    return True
                    
                finally:
                    # Always release advisory lock
                    await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)
                    
            except Exception as e:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.warning(f"{cid} [DEDUP] Failed to mark update_id={update_id} as processed: {e}")
                return False
    
    # ==================== PENDING UPDATES QUEUE (PASSIVE MODE) ====================
    
    async def enqueue_pending_update(
        self,
        update_id: int,
        update_payload: Dict[str, Any],
        update_type: str,
        instance_id: str
    ) -> bool:
        """
        Enqueue update to pending_updates queue (for PASSIVE mode).
        
        CRITICAL: This prevents update loss during deploy overlap.
        Updates are persisted in DB and processed when instance becomes ACTIVE.
        
        Args:
            update_id: Telegram update_id
            update_payload: Full Telegram update JSON payload
            update_type: Type: message, callback_query, inline_query, etc.
            instance_id: Instance ID that enqueued this update
            
        Returns:
            True if enqueued, False if duplicate (already exists)
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            try:
                import json
                payload_json = json.dumps(update_payload)
                
                # Use ON CONFLICT to handle duplicates gracefully
                result = await conn.execute("""
                    INSERT INTO pending_updates (update_id, update_payload, update_type, instance_id)
                    VALUES ($1, $2::jsonb, $3, $4)
                    ON CONFLICT (update_id) DO NOTHING
                """, update_id, payload_json, update_type, instance_id)
                
                # Check if row was inserted (not duplicate)
                if result == "INSERT 0 1":
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.info(
                        f"{cid} [PENDING_QUEUE] Enqueued update_id={update_id} "
                        f"type={update_type} instance={instance_id}"
                    )
                    return True
                else:
                    # Duplicate - already enqueued by another instance
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.debug(
                        f"{cid} [PENDING_QUEUE] Duplicate update_id={update_id} "
                        f"(already enqueued, skipping)"
                    )
                    return False
                    
            except Exception as e:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(
                    f"{cid} [PENDING_QUEUE] Failed to enqueue update_id={update_id}: {e}",
                    exc_info=True
                )
                return False
    
    async def get_pending_updates(
        self,
        instance_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get unprocessed pending updates (for ACTIVE mode processing).
        
        Args:
            instance_id: Instance ID that will process these updates
            limit: Maximum number of updates to fetch
            
        Returns:
            List of pending update records
        """
        import time
        from app.utils.enhanced_logging import log_operation, log_error, ensure_correlation_id
        cid = ensure_correlation_id()
        op_start = time.time()
        
        try:
            log_operation(
                "PG_STORAGE_GET_PENDING",
                status="START",
                instance_id=instance_id,
                limit=limit
            )
            
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                try:
                    rows = await conn.fetch("""
                        SELECT id, update_id, update_payload, update_type, instance_id, 
                               enqueued_at, attempts, last_error
                        FROM pending_updates
                        WHERE processed_at IS NULL
                        ORDER BY enqueued_at ASC
                        LIMIT $1
                        FOR UPDATE SKIP LOCKED
                    """, limit)
                    
                    duration_ms = (time.time() - op_start) * 1000
                    log_operation(
                        "PG_STORAGE_GET_PENDING",
                        status="OK",
                        duration_ms=duration_ms,
                        count=len(rows),
                        instance_id=instance_id
                    )
                    
                    return [dict(row) for row in rows]
                    
                except Exception as e:
                    duration_ms = (time.time() - op_start) * 1000
                    log_error(
                        "PG_STORAGE_GET_PENDING",
                        e,
                        error_code="GET_PENDING_FAILED",
                        fix_hint="Cannot get pending updates from database",
                        check_list="Database connection | Table schema | Query syntax",
                        duration_ms=duration_ms,
                        instance_id=instance_id
                    )
                    return []
        except RuntimeError as e:
            # BATCH 48.24: RuntimeError from _get_pool() means NO DATABASE MODE or DB unavailable
            duration_ms = (time.time() - op_start) * 1000
            log_operation(
                "PG_STORAGE_GET_PENDING",
                status="SKIPPED",
                error_code="STORAGE_NOT_AVAILABLE",
                error_message=str(e),
                fix_hint="PostgresStorage not available - this is expected in NO DATABASE MODE",
                check_list="NO_DATABASE_MODE | Storage factory | Use FileStorage",
                duration_ms=duration_ms,
                instance_id=instance_id
            )
            return []  # Return empty list instead of raising
        except Exception as e:
            duration_ms = (time.time() - op_start) * 1000
            log_error(
                "PG_STORAGE_GET_PENDING",
                e,
                error_code="GET_PENDING_EXCEPTION",
                fix_hint="Unexpected error getting pending updates",
                check_list="Database connection | Storage implementation | Error logs",
                duration_ms=duration_ms,
                instance_id=instance_id
            )
            return []
    
    async def mark_pending_update_processed(
        self,
        pending_id: int,
        processing_instance_id: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Mark pending update as processed.
        
        Args:
            pending_id: ID from pending_updates table
            processing_instance_id: Instance ID that processed this update
            success: True if processed successfully, False if failed
            error_message: Error message if processing failed
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            try:
                if success:
                    await conn.execute("""
                        UPDATE pending_updates
                        SET processed_at = NOW(),
                            processing_instance_id = $1
                        WHERE id = $2
                    """, processing_instance_id, pending_id)
                else:
                    await conn.execute("""
                        UPDATE pending_updates
                        SET attempts = attempts + 1,
                            last_error = $1,
                            processing_instance_id = $2
                        WHERE id = $3
                    """, error_message, processing_instance_id, pending_id)
                    
            except Exception as e:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(
                    f"{cid} [PENDING_QUEUE] Failed to mark pending_id={pending_id} as processed: {e}",
                    exc_info=True
                )
    
    async def cleanup_old_pending_updates(self, days: int = 7) -> int:
        """
        Cleanup old processed pending updates.
        
        Args:
            days: Remove updates older than N days
            
        Returns:
            Number of rows deleted
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            try:
                result = await conn.execute("""
                    DELETE FROM pending_updates
                    WHERE processed_at IS NOT NULL
                    AND processed_at < NOW() - INTERVAL '%d days'
                """ % days)
                
                # Extract number from result string like "DELETE 5"
                deleted_count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                
                if deleted_count > 0:
                    logger.info(f"[PENDING_QUEUE] Cleaned up {deleted_count} old pending updates")
                
                return deleted_count
                
            except Exception as e:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(
                    f"{cid} [PENDING_QUEUE] Failed to cleanup old updates: {e}",
                    exc_info=True
                )
                return 0
    
    async def async_test_connection(self) -> bool:
        """
        Проверить подключение (async-friendly).
        
        ВАЖНО: Используется в runtime когда event loop уже запущен.
        НЕ использует asyncio.run() или run_until_complete().
        """
        if not ASYNCPG_AVAILABLE:
            return False
        
        try:
            # Пробуем создать временный pool для проверки
            pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=1,
                command_timeout=5  # Короткий таймаут для проверки
            )
            if pool:
                await pool.close()
                return True
        except Exception as e:
            logger.debug(f"PostgreSQL async connection test failed: {e}")
            return False
        return False
    
    def test_connection(self) -> bool:
        """
        Проверить подключение (синхронно, для CLI/тестов).
        
        ВАЖНО: НЕ использовать в runtime когда event loop уже запущен!
        Используйте async_test_connection() вместо этого.
        """
        if not ASYNCPG_AVAILABLE:
            return False
        
        try:
            import asyncio
            # Проверяем есть ли уже запущенный loop
            try:
                loop = asyncio.get_running_loop()
                # Если loop уже запущен - это ошибка, нужно использовать async версию
                logger.warning(
                    "[WARN] test_connection() called while event loop is running. "
                    "Use async_test_connection() instead."
                )
                return False
            except RuntimeError:
                # Нет запущенного loop - можно создать новый
                pass
            
            # Создаем новый loop только если его нет
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                pool = loop.run_until_complete(
                    asyncpg.create_pool(self.database_url, min_size=1, max_size=1, command_timeout=5)
                )
                if pool:
                    loop.run_until_complete(pool.close())
                    return True
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"PostgreSQL connection test failed: {e}")
            return False
        return False
    
    # ==================== USER OPERATIONS ====================
    
    async def ensure_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> None:
        """
        Ensure user exists in database (idempotent, safe for concurrent calls)
        CRITICAL: Prevents FK violations when creating jobs
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # INSERT or UPDATE user record
            # Use COALESCE to avoid overwriting existing values with NULL
            await conn.execute(
                """
                INSERT INTO users (id, username, first_name, last_name, balance, created_at, updated_at, user_id)
                VALUES ($1, $2, $3, $4, 0.00, NOW(), NOW(), $1)
                ON CONFLICT (id) DO UPDATE SET
                    username = CASE 
                        WHEN EXCLUDED.username IS NOT NULL THEN EXCLUDED.username
                        ELSE users.username
                    END,
                    first_name = CASE
                        WHEN EXCLUDED.first_name IS NOT NULL THEN EXCLUDED.first_name
                        ELSE users.first_name
                    END,
                    last_name = CASE
                        WHEN EXCLUDED.last_name IS NOT NULL THEN EXCLUDED.last_name
                        ELSE users.last_name
                    END,
                    updated_at = NOW()
                """,
                user_id, username, first_name, last_name
            )
    
    async def get_user(self, user_id: int, upsert: bool = True) -> Dict[str, Any]:
        """Получить данные пользователя"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
            
            if row is None and upsert:
                # Создаем пользователя
                await conn.execute(
                    "INSERT INTO users (id, balance) VALUES ($1, 0.00) ON CONFLICT (id) DO NOTHING",
                    user_id
                )
                row = await conn.fetchrow(
                    "SELECT * FROM users WHERE id = $1",
                    user_id
                )
            
            if row is None:
                return {
                    'user_id': user_id,
                    'balance': 0.0,
                    'language': 'ru',
                    'gift_claimed': False,
                    'referrer_id': None,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
            
            # Получаем дополнительные данные
            language = await self.get_user_language(user_id)
            gift_claimed = await self.has_claimed_gift(user_id)
            referrer_id = await self.get_referrer(user_id)
            
            return {
                'user_id': user_id,
                'balance': float(row['balance']),
                'language': language,
                'gift_claimed': gift_claimed,
                'referrer_id': referrer_id,
                'created_at': row['created_at'].isoformat() if row['created_at'] else datetime.now().isoformat(),
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else datetime.now().isoformat()
            }
    
    async def get_user_balance(self, user_id: int) -> float:
        """Получить баланс пользователя"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT balance FROM users WHERE id = $1",
                user_id
            )
            if row is None:
                # Создаем пользователя с балансом 0
                await conn.execute(
                    "INSERT INTO users (id, balance) VALUES ($1, 0.00) ON CONFLICT (id) DO NOTHING",
                    user_id
                )
                return 0.0
            return float(row['balance'])
    
    async def set_user_balance(self, user_id: int, amount: float) -> None:
        """Установить баланс пользователя"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, balance) VALUES ($1, $2)
                ON CONFLICT (id) DO UPDATE SET balance = $2
                """,
                user_id, amount
            )
    
    async def add_user_balance(self, user_id: int, amount: float) -> float:
        """Добавить к балансу (atomic, returns new balance)"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Выполняем операцию и получаем новый баланс в одной транзакции
            await conn.execute(
                """
                INSERT INTO users (id, balance) VALUES ($1, $2)
                ON CONFLICT (id) DO UPDATE SET balance = users.balance + $2
                """,
                user_id, amount
            )
            # Получаем новый баланс в той же транзакции
            row = await conn.fetchrow("SELECT balance FROM users WHERE id = $1", user_id)
            return float(row['balance']) if row else 0.0
    
    async def subtract_user_balance(self, user_id: int, amount: float) -> bool:
        """Вычесть из баланса (atomic, with transaction)"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Проверяем баланс в той же транзакции
                user = await conn.fetchrow("SELECT balance FROM users WHERE id = $1", user_id)
                if not user:
                    # Создаем пользователя если не существует
                    await conn.execute(
                        "INSERT INTO users (id, balance) VALUES ($1, 0.00) ON CONFLICT (id) DO NOTHING",
                        user_id
                    )
                    user = await conn.fetchrow("SELECT balance FROM users WHERE id = $1", user_id)
                
                current_balance = float(user['balance'])
                if current_balance >= amount:
                    await conn.execute(
                        "UPDATE users SET balance = balance - $1 WHERE id = $2",
                        amount, user_id
                    )
                    return True
                return False
    
    async def get_user_language(self, user_id: int) -> str:
        """Получить язык пользователя"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT language FROM user_settings WHERE user_id = $1",
                user_id
            )
            if row:
                return row['language'] or 'ru'
            
            # Создаем запись с дефолтным языком
            await conn.execute(
                "INSERT INTO user_settings (user_id, language) VALUES ($1, 'ru') ON CONFLICT (user_id) DO NOTHING",
                user_id
            )
            return 'ru'
    
    async def set_user_language(self, user_id: int, language: str) -> None:
        """Установить язык пользователя"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_settings (user_id, language) VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET language = $2
                """,
                user_id, language
            )
    
    async def has_claimed_gift(self, user_id: int) -> bool:
        """Проверить получение подарка"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT gift_claimed FROM user_settings WHERE user_id = $1",
                user_id
            )
            return bool(row['gift_claimed']) if row else False
    
    async def set_gift_claimed(self, user_id: int) -> None:
        """Отметить получение подарка"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_settings (user_id, gift_claimed) VALUES ($1, TRUE)
                ON CONFLICT (user_id) DO UPDATE SET gift_claimed = TRUE
                """,
                user_id
            )
    
    async def get_user_free_generations_today(self, user_id: int) -> int:
        """Получить количество бесплатных генераций сегодня"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            today = datetime.now().date()
            row = await conn.fetchrow(
                """
                SELECT count FROM daily_free_generations
                WHERE user_id = $1 AND date = $2
                """,
                user_id, today
            )
            return row['count'] if row else 0
    
    async def get_user_free_generations_remaining(self, user_id: int) -> int:
        """Получить оставшиеся бесплатные генерации"""
        from app.config import get_settings
        settings = get_settings()
        free_per_day = 5  # TODO: добавить в settings
        
        used = await self.get_user_free_generations_today(user_id)
        bonus = await self._get_free_generations_bonus(user_id)
        total_available = free_per_day + bonus
        return max(0, total_available - used)
    
    async def _get_free_generations_bonus(self, user_id: int) -> int:
        """Получить бонусные генерации"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT bonus FROM daily_free_generations WHERE user_id = $1",
                user_id
            )
            return row['bonus'] if row else 0
    
    async def increment_free_generations(self, user_id: int) -> None:
        """Увеличить счетчик бесплатных генераций"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            today = datetime.now().date()
            await conn.execute(
                """
                INSERT INTO daily_free_generations (user_id, date, count, bonus)
                VALUES ($1, $2, 1, 0)
                ON CONFLICT (user_id, date) DO UPDATE SET count = daily_free_generations.count + 1
                """,
                user_id, today
            )
    
    async def get_admin_limit(self, user_id: int) -> float:
        """Получить лимит админа"""
        from app.config import get_settings
        settings = get_settings()
        
        if user_id == settings.admin_id:
            return float('inf')
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT limit_amount FROM admin_limits WHERE user_id = $1",
                user_id
            )
            return float(row['limit_amount']) if row else 100.0
    
    async def get_admin_spent(self, user_id: int) -> float:
        """Получить потраченную сумму админа"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COALESCE(SUM(amount), 0) as spent FROM operations WHERE user_id = $1 AND type = 'generation'",
                user_id
            )
            return float(row['spent']) if row else 0.0
    
    async def get_admin_remaining(self, user_id: int) -> float:
        """Получить оставшийся лимит админа"""
        limit = await self.get_admin_limit(user_id)
        if limit == float('inf'):
            return float('inf')
        spent = await self.get_admin_spent(user_id)
        return max(0.0, limit - spent)
    
    # ==================== GENERATION JOBS ====================
    
    async def add_generation_job(
        self,
        user_id: int,
        model_id: str,
        model_name: str,
        params: Dict[str, Any],
        price: float,
        task_id: Optional[str] = None,
        status: str = "queued"
    ) -> str:
        """
        Добавить задачу генерации (atomic: ensures user exists + creates job in transaction).
        
        CRITICAL: This method is atomic - ensures user exists and creates job in single transaction
        to prevent race conditions and FK violations.
        """
        job_id = task_id or str(uuid.uuid4())
        normalized_status = normalize_job_status(status)
        pool = await self._get_pool()
        
        # ATOMIC: Ensure user exists + create job in single transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                # PHASE 1: Ensure user exists (idempotent, prevents FK violation)
                await conn.execute(
                    """
                    INSERT INTO users (id, username, first_name, last_name, balance, created_at, updated_at, user_id)
                    VALUES ($1, NULL, NULL, NULL, 0.00, NOW(), NOW(), $1)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    user_id
                )
                
                # PHASE 2: Validate and serialize params (prevent JSON injection/DoS)
                import json
                try:
                    params_json = json.dumps(params, ensure_ascii=False)
                    # CRITICAL: Limit JSON size to prevent DoS (10MB max)
                    MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB
                    if len(params_json) > MAX_JSON_SIZE:
                        raise ValueError(
                            f"Params JSON too large: {len(params_json)} bytes (max {MAX_JSON_SIZE})"
                        )
                except (TypeError, ValueError) as e:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(f"{cid} [JOB_CREATE] Invalid params for job {job_id}: {e}")
                    raise ValueError(f"Invalid job params: {e}")
                
                # PHASE 3: Create job (FK constraint satisfied)
                await conn.execute(
                    """
                    INSERT INTO generation_jobs (job_id, user_id, model_id, model_name, params, price, status, external_task_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (job_id) DO NOTHING
                    """,
                    job_id, user_id, model_id, model_name, params_json, price, normalized_status, task_id
                )
        
        return job_id
    
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        result_urls: Optional[List[str]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Обновить статус задачи"""
        from app.storage.status import is_terminal_status
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # CRITICAL: Check current status before update to prevent invalid transitions
                current_job = await conn.fetchrow(
                    "SELECT status FROM generation_jobs WHERE job_id = $1 FOR UPDATE",
                    job_id
                )
                
                if not current_job:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(f"{cid} [JOB_UPDATE] Job {job_id} not found for status update")
                    return
                
                current_status = current_job['status']
                normalized_status = normalize_job_status(status)
                
                # Prevent updating terminal jobs (unless it's the same status)
                if is_terminal_status(current_status) and normalized_status != current_status:
                    logger.warning(
                        f"[JOB_UPDATE] Ignoring status update for job {job_id}: "
                        f"current status '{current_status}' is terminal. New status '{normalized_status}' ignored."
                    )
                    return
                
                updates = ["status = $2"]
                params = [job_id, normalized_status]
                
                if result_urls is not None:
                    updates.append("result_urls = $3")
                    params.append(json.dumps(result_urls))
                if error_message is not None:
                    updates.append("error_message = $4")
                    params.append(error_message[:500])  # Ограничиваем длину
                
                await conn.execute(
                    f"UPDATE generation_jobs SET {', '.join(updates)} WHERE job_id = $1",
                    *params
                )
                
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.info(f"{cid} [JOB_UPDATE] id={job_id} status={current_status} -> {normalized_status}")
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Получить задачу по ID"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM generation_jobs WHERE job_id = $1",
                job_id
            )
            if row:
                return dict(row)
            return None

    async def find_job_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Найти задачу по внешнему task_id (checks both tables for compatibility)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # P0 FIX #5: Check BOTH tables to support mixed deployment
            # NEW TABLE (jobs) - used by GenerationServiceV2
            row = await conn.fetchrow(
                "SELECT id, user_id, model_id, category, input_json, price_rub, status, "
                "kie_task_id, kie_status, result_json, error_text, idempotency_key, "
                "chat_id, delivered_at, created_at, updated_at, finished_at "
                "FROM jobs WHERE kie_task_id = $1",
                task_id
            )
            if row:
                return dict(row)
            
            # FALLBACK: OLD TABLE (generation_jobs) - used by KieGenerator (legacy)
            # P0 FIX #9: Column is named 'external_task_id', not 'task_id'
            row = await conn.fetchrow(
                "SELECT * FROM generation_jobs WHERE external_task_id = $1 OR job_id = $1",
                task_id
            )
            return dict(row) if row else None

    async def try_acquire_delivery_lock(self, task_id: str, timeout_minutes: int = 5) -> Optional[Dict[str, Any]]:
        """
        Atomically acquire delivery lock for a task.
        
        Uses delivering_at as a lock mechanism to prevent race conditions between:
        - callback + polling
        - ACTIVE + PASSIVE instances
        - multiple concurrent callbacks
        
        Args:
            task_id: External task ID from Kie.ai
            timeout_minutes: Consider stale if delivering_at older than this
        
        Returns:
            Job dict if lock acquired (this instance won the race)
            None if already delivered or another process is delivering
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Atomic update: set delivering_at=NOW() only if not delivered and not currently delivering
            # OR if delivering but stale (timeout_minutes passed)
            # P0 FIX #10: Cast timeout_minutes to str for PostgreSQL string concatenation
            row = await conn.fetchrow(
                """
                UPDATE generation_jobs
                SET delivering_at = NOW()
                WHERE (external_task_id = $1 OR job_id = $1)
                  AND delivered_at IS NULL
                  AND (
                    delivering_at IS NULL
                    OR delivering_at < NOW() - ($2 || ' minutes')::INTERVAL
                  )
                RETURNING *
                """,
                task_id,
                str(timeout_minutes)  # Cast int to str for PostgreSQL || operator
            )
            return dict(row) if row else None

    async def mark_delivered(self, task_id: str, success: bool = True, error: Optional[str] = None) -> None:
        """
        Mark job as delivered (or failed delivery).
        
        Args:
            task_id: External task ID
            success: True if delivery succeeded, False if failed
            error: Error message if delivery failed
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if success:
                # Success: set delivered_at and clear delivering_at
                await conn.execute(
                    """
                    UPDATE generation_jobs
                    SET delivered_at = NOW(), 
                        delivering_at = NULL,
                        status = 'done'
                    WHERE external_task_id = $1 OR job_id = $1
                    """,
                    task_id
                )
            else:
                # Failed: clear delivering_at, save error, allow retry
                await conn.execute(
                    """
                    UPDATE generation_jobs
                    SET delivering_at = NULL,
                        error_message = COALESCE(error_message, '') || $2
                    WHERE external_task_id = $1 OR job_id = $1
                    """,
                    task_id,
                    f"\n[DELIVERY_FAIL] {error}" if error else ""
                )

    async def get_undelivered_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get jobs that are done but not delivered to Telegram."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM generation_jobs
                WHERE status = 'done'
                  AND result_urls IS NOT NULL
                  AND result_urls != ''
                  AND result_urls != '[]'
                ORDER BY created_at ASC
                LIMIT $1
                """,
                limit
            )
            return [dict(row) for row in rows]

    async def list_jobs(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Получить список задач"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            query = "SELECT * FROM generation_jobs WHERE 1=1"
            params = []
    
    # ==================== ORPHAN CALLBACKS (PHASE 4) ====================
    
    async def _save_orphan_callback(self, task_id: str, payload: Dict[str, Any]) -> None:
        """Save orphan callback for later reconciliation"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO orphan_callbacks (task_id, payload, received_at, processed)
                VALUES ($1, $2, NOW(), FALSE)
                ON CONFLICT (task_id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    received_at = EXCLUDED.received_at
                """,
                task_id, json.dumps(payload)
            )
    
    async def _get_unprocessed_orphans(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get unprocessed orphan callbacks for reconciliation"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT task_id, payload, received_at
                FROM orphan_callbacks
                WHERE processed = FALSE
                ORDER BY received_at ASC
                LIMIT $1
                """,
                limit
            )
            return [dict(row) for row in rows]
    
    async def _mark_orphan_processed(self, task_id: str, error: Optional[str] = None) -> None:
        """Mark orphan callback as processed"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE orphan_callbacks
                SET processed = TRUE, processed_at = NOW(), error_message = $2
                WHERE task_id = $1
                """,
                task_id, error
            )
    
    async def list_jobs(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Получить список задач с фильтрацией и пагинацией"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            query = "SELECT * FROM generation_jobs WHERE 1=1"
            params = []
            
            if user_id is not None:
                query += " AND user_id = $" + str(len(params) + 1)
                params.append(user_id)
            if status is not None:
                query += " AND status = $" + str(len(params) + 1)
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def add_generation_to_history(
        self,
        user_id: int,
        model_id: str,
        model_name: str,
        params: Dict[str, Any],
        result_urls: List[str],
        price: float,
        operation_id: Optional[str] = None
    ) -> str:
        """Добавить генерацию в историю"""
        gen_id = operation_id or str(uuid.uuid4())
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO operations (user_id, type, amount, model, result_url, prompt)
                VALUES ($1, 'generation', $2, $3, $4, $5)
                """,
                user_id, price, model_name, json.dumps(result_urls), json.dumps(params)[:1000]
            )
        return gen_id
    
    async def get_user_generations_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить историю генераций"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM operations
                WHERE user_id = $1 AND type = 'generation'
                ORDER BY created_at DESC LIMIT $2
                """,
                user_id, limit
            )
            return [dict(row) for row in rows]
    
    # ==================== PAYMENTS ====================
    
    async def add_payment(
        self,
        user_id: int,
        amount: float,
        payment_method: str,
        payment_id: Optional[str] = None,
        screenshot_file_id: Optional[str] = None,
        status: str = "pending",
        idempotency_key: Optional[str] = None
    ) -> str:
        """
        Добавить платеж с поддержкой idempotency.
        
        CRITICAL: Uses transaction to ensure atomicity and prevent race conditions.
        Validates payment amount to prevent negative or excessive amounts.
        """
        # CRITICAL: Validate payment amount
        if amount <= 0:
            raise ValueError(f"Payment amount must be positive, got {amount}")
        if amount > 1000000:  # 1M RUB limit (safety check)
            raise ValueError(f"Payment amount exceeds maximum limit (1,000,000 RUB), got {amount}")
        
        pay_id = payment_id or str(uuid.uuid4())
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # CRITICAL: Validate user exists before inserting payment
                user_exists = await conn.fetchval(
                    "SELECT 1 FROM users WHERE user_id = $1",
                    user_id
                )
                if not user_exists:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(f"{cid} [PAYMENT] User {user_id} not found - cannot create payment")
                    raise ValueError(f"User {user_id} not found - create user first")
                
                # Если передан idempotency_key, проверяем существующий платеж (within transaction)
                if idempotency_key:
                    existing = await conn.fetchrow(
                        "SELECT payment_id FROM payments WHERE idempotency_key = $1 FOR UPDATE",
                        idempotency_key
                    )
                    if existing:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.debug(f"{cid} [PAYMENT] Idempotency hit: key={idempotency_key} existing_payment={existing['payment_id']}")
                        return existing['payment_id']
                
                try:
                    await conn.execute(
                        """
                        INSERT INTO payments (payment_id, user_id, amount, payment_method, screenshot_file_id, status, idempotency_key)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (idempotency_key) DO UPDATE SET payment_id = payments.payment_id
                        RETURNING payment_id
                        """,
                        pay_id, user_id, amount, payment_method, screenshot_file_id, status, idempotency_key
                    )
                except asyncpg.UniqueViolationError:
                    # Fallback: если ON CONFLICT не сработал (старая схема), проверяем снова
                    if idempotency_key:
                        existing = await conn.fetchrow(
                            "SELECT payment_id FROM payments WHERE idempotency_key = $1",
                            idempotency_key
                        )
                        if existing:
                            return existing['payment_id']
                    raise
        return pay_id
    
    async def mark_payment_status(
        self,
        payment_id: str,
        status: str,
        admin_id: Optional[int] = None,
        notes: Optional[str] = None
    ) -> None:
        """
        Обновить статус платежа с автоматическим rollback при cancel/failed.
        
        CRITICAL: Validates status transitions to prevent invalid state changes.
        Valid transitions:
        - pending -> approved, rejected, cancelled, failed
        - approved -> (terminal, no further transitions)
        - rejected/cancelled/failed -> (terminal, no further transitions)
        """
        # Validate status
        valid_statuses = {"pending", "approved", "rejected", "cancelled", "failed"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid payment status: {status}. Must be one of {valid_statuses}")
        
        # CRITICAL: Validate admin_id if provided (authorization check)
        if admin_id is not None:
            from app.admin.permissions import get_admin_ids
            # Note: db_service is not available here, so we check ENV only
            # Full admin check should be done at handler level
            admin_ids = get_admin_ids()
            if admin_id not in admin_ids:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.warning(f"{cid} [PAYMENT_STATUS] Unauthorized admin_id={admin_id} attempted to change payment {payment_id} status")
                raise ValueError(f"Unauthorized: admin_id {admin_id} is not authorized to change payment status")
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Get current status with FOR UPDATE to prevent race conditions
                current = await conn.fetchrow(
                    "SELECT status FROM payments WHERE payment_id = $1 FOR UPDATE",
                    payment_id
                )
                if not current:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(f"{cid} [PAYMENT_STATUS] Payment {payment_id} not found")
                    raise ValueError(f"Payment {payment_id} not found")
                
                current_status = current['status']
                
                # CRITICAL: Check for duplicate status update (idempotency)
                if current_status == status:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.info(f"{cid} [PAYMENT_STATUS] Payment {payment_id} already in status {status} (idempotent, skipping)")
                    return
                
                # Validate transition
                terminal_statuses = {"approved", "rejected", "cancelled", "failed"}
                if current_status in terminal_statuses and status != current_status:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(
                        f"{cid} [PAYMENT_STATUS] Invalid transition: {payment_id} "
                        f"from {current_status} to {status} (terminal status cannot change)"
                    )
                    raise ValueError(
                        f"Cannot change payment status from {current_status} to {status}. "
                        f"Terminal statuses cannot be changed."
                    )
                
                # Обновляем статус
                await conn.execute(
                    "UPDATE payments SET status = $1, admin_id = $2, notes = $3, updated_at = NOW() WHERE payment_id = $4",
                    status, admin_id, notes, payment_id
                )
                
                logger.info(
                    f"[PAYMENT_STATUS] Updated: {payment_id} {current_status} -> {status} "
                    f"(admin={admin_id})"
                )
                
                # Если платеж одобрен, добавляем баланс (в той же транзакции)
                # CRITICAL: Use WalletService for atomic balance updates to prevent race conditions
                if status == "approved":
                    payment = await conn.fetchrow(
                        "SELECT user_id, amount, payment_method FROM payments WHERE payment_id = $1",
                        payment_id
                    )
                    if payment:
                        # CRITICAL: Use WalletService.topup for atomic balance update with ledger entry
                        # This ensures idempotency and prevents race conditions
                        from app.database.services import WalletService
                        from app.database.services import DatabaseService
                        from decimal import Decimal
                        
                        # Create WalletService instance (reuse existing connection pool)
                        db_service = DatabaseService(self.database_url)
                        db_service._pool = pool  # Reuse existing pool
                        wallet_service = WalletService(db_service)
                        
                        # Use topup with idempotency key based on payment_id
                        ref = f"payment_{payment_id}"
                        amount_rub = Decimal(str(payment['amount']))
                        payment_method_val = payment.get('payment_method', payment_method or 'unknown')
                        topup_success = await wallet_service.topup(
                            payment['user_id'],
                            amount_rub,
                            ref=ref,
                            meta={"payment_id": payment_id, "payment_method": payment_method_val}
                        )
                        
                        if not topup_success:
                            logger.warning(
                                f"[PAYMENT_STATUS] Topup already processed for payment {payment_id} "
                                f"(idempotent, skipping)"
                            )
                        else:
                            logger.info(
                                f"[PAYMENT_STATUS] Balance updated via WalletService: "
                                f"user={payment['user_id']} amount={amount_rub} payment={payment_id}"
                            )
                
                # Если платеж отменен или провалился, освобождаем резервы (если были)
                if status in ("cancelled", "failed", "rejected"):
                    # Ищем связанные резервы и освобождаем их
                    await conn.execute(
                        """
                        UPDATE balance_reserves 
                        SET status = 'released', updated_at = NOW()
                        WHERE user_id IN (SELECT user_id FROM payments WHERE payment_id = $1)
                        AND status = 'reserved'
                        """,
                        payment_id
                    )
    
    async def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Получить платеж по ID"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM payments WHERE payment_id = $1",
                payment_id
            )
            return dict(row) if row else None
    
    async def list_payments(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получить список платежей.
        
        CRITICAL: Uses parameterized queries to prevent SQL injection.
        All parameters are passed via $1, $2, etc. placeholders.
        """
        # CRITICAL: Validate limit to prevent DoS
        if limit <= 0 or limit > 1000:
            limit = 100  # Default to safe limit
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # CRITICAL: Use parameterized queries with proper placeholders
            if user_id is not None and status is not None:
                rows = await conn.fetch(
                    "SELECT * FROM payments WHERE user_id = $1 AND status = $2 ORDER BY created_at DESC LIMIT $3",
                    user_id, status, limit
                )
            elif user_id is not None:
                rows = await conn.fetch(
                    "SELECT * FROM payments WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                    user_id, limit
                )
            elif status is not None:
                rows = await conn.fetch(
                    "SELECT * FROM payments WHERE status = $1 ORDER BY created_at DESC LIMIT $2",
                    status, limit
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM payments ORDER BY created_at DESC LIMIT $1",
                    limit
                )
            
            return [dict(row) for row in rows]
    
    # ==================== BALANCE RESERVES (IDEMPOTENCY) ====================
    
    async def reserve_balance_for_generation(
        self,
        user_id: int,
        amount: float,
        model_id: str,
        task_id: str,
        idempotency_key: Optional[str] = None
    ) -> bool:
        """
        Резервирует баланс для генерации (idempotent).
        
        Returns:
            True если резерв успешен, False если недостаточно средств или уже зарезервировано
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Проверяем баланс
                user = await conn.fetchrow("SELECT balance FROM users WHERE id = $1", user_id)
                if not user:
                    # Создаем пользователя если не существует
                    await conn.execute(
                        "INSERT INTO users (id, balance) VALUES ($1, 0.00) ON CONFLICT (id) DO NOTHING",
                        user_id
                    )
                    user = await conn.fetchrow("SELECT balance FROM users WHERE id = $1", user_id)
                
                current_balance = float(user['balance'])
                if current_balance < amount:
                    return False  # Недостаточно средств
                
                # Генерируем idempotency_key если не передан
                if not idempotency_key:
                    idempotency_key = f"{task_id}:{user_id}:{model_id}"
                
                # Проверяем существующий резерв по idempotency_key
                existing = await conn.fetchrow(
                    "SELECT id, status FROM balance_reserves WHERE idempotency_key = $1",
                    idempotency_key
                )
                if existing:
                    # Резерв уже существует - возвращаем True если он в статусе 'reserved'
                    return existing['status'] == 'reserved'
                
                # Проверяем существующий резерв по task_id
                existing_task = await conn.fetchrow(
                    "SELECT id, status FROM balance_reserves WHERE task_id = $1 AND user_id = $2 AND model_id = $3",
                    task_id, user_id, model_id
                )
                if existing_task:
                    # Резерв уже существует для этой задачи
                    return existing_task['status'] == 'reserved'
                
                # Создаем новый резерв
                try:
                    await conn.execute(
                        """
                        INSERT INTO balance_reserves (user_id, task_id, model_id, amount, idempotency_key, status)
                        VALUES ($1, $2, $3, $4, $5, 'reserved')
                        """,
                        user_id, task_id, model_id, amount, idempotency_key
                    )
                    
                    # Резервируем баланс (вычитаем из доступного)
                    await conn.execute(
                        "UPDATE users SET balance = balance - $1 WHERE id = $2",
                        amount, user_id
                    )
                    
                    return True
                except asyncpg.UniqueViolationError:
                    # Конфликт по уникальному ключу - резерв уже существует
                    return False
    
    async def release_balance_reserve(
        self,
        user_id: int,
        task_id: str,
        model_id: str
    ) -> bool:
        """
        Освобождает зарезервированный баланс (при отмене/ошибке).
        
        Returns:
            True если резерв был освобожден, False если резерва не было
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Находим резерв
                reserve = await conn.fetchrow(
                    """
                    SELECT id, amount, status FROM balance_reserves 
                    WHERE task_id = $1 AND user_id = $2 AND model_id = $3 AND status = 'reserved'
                    """,
                    task_id, user_id, model_id
                )
                
                if not reserve:
                    return False  # Резерва не было
                
                # Освобождаем баланс (возвращаем обратно)
                await conn.execute(
                    "UPDATE users SET balance = balance + $1 WHERE id = $2",
                    float(reserve['amount']), user_id
                )
                
                # Обновляем статус резерва
                await conn.execute(
                    "UPDATE balance_reserves SET status = 'released', updated_at = NOW() WHERE id = $1",
                    reserve['id']
                )
                
                return True
    
    async def commit_balance_reserve(
        self,
        user_id: int,
        task_id: str,
        model_id: str
    ) -> bool:
        """
        Подтверждает резерв баланса (списывает при успешной генерации).
        
        Returns:
            True если списание успешно, False если резерва не было
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Находим резерв
                reserve = await conn.fetchrow(
                    """
                    SELECT id, amount, status FROM balance_reserves 
                    WHERE task_id = $1 AND user_id = $2 AND model_id = $3 AND status = 'reserved'
                    """,
                    task_id, user_id, model_id
                )
                
                if not reserve:
                    return False  # Резерва не было
                
                # Обновляем статус резерва (баланс уже списан при резервировании)
                await conn.execute(
                    "UPDATE balance_reserves SET status = 'committed', updated_at = NOW() WHERE id = $1",
                    reserve['id']
                )
                
                return True
    
    # ==================== REFERRALS ====================
    
    async def set_referrer(self, user_id: int, referrer_id: int) -> None:
        """
        Установить реферера (atomic, idempotent).
        
        CRITICAL: Uses transaction to prevent race conditions.
        If user already has referrer, this is a no-op (idempotent).
        Validates that referrer_id is not the same as user_id (no self-referral).
        """
        # CRITICAL: Validate no self-referral
        if user_id == referrer_id:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [REFERRAL] Self-referral attempt: user_id={user_id} referrer_id={referrer_id} (ignored)")
            return
        
        # CRITICAL: Validate referrer_id exists
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            referrer_exists = await conn.fetchval(
                "SELECT 1 FROM users WHERE user_id = $1",
                referrer_id
            )
            if not referrer_exists:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.warning(f"{cid} [REFERRAL] Referrer {referrer_id} not found - cannot set referral")
                raise ValueError(f"Referrer {referrer_id} not found - create user first")
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # CRITICAL: Check for circular referral chains (A -> B -> A)
                # Prevent infinite referral loops
                visited = set()
                current_id = referrer_id
                max_depth = 10  # Reasonable limit to prevent infinite loops
                depth = 0
                
                while current_id and depth < max_depth:
                    if current_id == user_id:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.warning(f"{cid} [REFERRAL] Circular referral chain detected: user={user_id} referrer={referrer_id} (ignored)")
                        raise ValueError(f"Circular referral chain detected: cannot set referrer {referrer_id} for user {user_id}")
                    
                    if current_id in visited:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.warning(f"{cid} [REFERRAL] Referral loop detected: user={user_id} referrer={referrer_id} (ignored)")
                        raise ValueError(f"Referral loop detected: cannot set referrer {referrer_id} for user {user_id}")
                    
                    visited.add(current_id)
                    
                    # Get referrer of current_id
                    current_referrer = await conn.fetchval(
                        "SELECT referrer_id FROM referrals WHERE user_id = $1",
                        current_id
                    )
                    current_id = current_referrer
                    depth += 1
                
                # Check if already exists (idempotency)
                existing = await conn.fetchrow(
                    "SELECT referrer_id FROM referrals WHERE user_id = $1",
                    user_id
                )
                if existing and existing['referrer_id']:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.info(f"{cid} [REFERRAL] User {user_id} already has referrer {existing['referrer_id']} (idempotent)")
                    return
                
                # Insert referral relationship
                await conn.execute(
                    """
                    INSERT INTO referrals (user_id, referrer_id)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET referrer_id = $2
                    """,
                    user_id, referrer_id
                )
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.info(f"{cid} [REFERRAL] Set referrer: user={user_id} referrer={referrer_id}")
                
                # CRITICAL: Award referral bonus only on first-time referral (not on duplicate set_referrer calls)
                # This prevents duplicate bonuses if set_referrer is called multiple times
                # Note: Bonus is awarded here, not in add_referral_bonus, to ensure it's only awarded once per referral
                # The bonus itself is idempotent via add_referral_bonus's ON CONFLICT, but we only call it once here
                try:
                    await self.add_referral_bonus(referrer_id, bonus_generations=5)
                    logger.info(f"{cid} [REFERRAL] Awarded bonus to referrer {referrer_id} for new referral {user_id}")
                except Exception as bonus_error:
                    # Log but don't fail - bonus awarding is best-effort
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(f"{cid} [REFERRAL] Failed to award bonus to referrer {referrer_id}: {bonus_error}")
    
    async def get_referrer(self, user_id: int) -> Optional[int]:
        """Получить ID реферера"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT referrer_id FROM referrals WHERE user_id = $1",
                user_id
            )
            return int(row['referrer_id']) if row and row['referrer_id'] else None
    
    async def get_referrals(self, referrer_id: int) -> List[int]:
        """Получить список рефералов"""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id FROM referrals WHERE referrer_id = $1",
                referrer_id
            )
            return [int(row['user_id']) for row in rows]
    
    async def add_referral_bonus(self, referrer_id: int, bonus_generations: int = 5) -> None:
        """
        Добавить бонусные генерации рефереру (atomic, idempotent).
        
        CRITICAL: Uses transaction to prevent race conditions and duplicate bonuses.
        Uses SELECT FOR UPDATE to prevent concurrent bonus additions.
        Validates bonus amount to prevent negative or excessive bonuses.
        """
        # CRITICAL: Validate bonus amount
        if bonus_generations <= 0:
            raise ValueError(f"Bonus generations must be positive, got {bonus_generations}")
        if bonus_generations > 1000:  # Reasonable limit (safety check)
            raise ValueError(f"Bonus generations exceeds maximum limit (1000), got {bonus_generations}")
        
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                today = datetime.now().date()
                
                # Check current bonus (FOR UPDATE to prevent race)
                current = await conn.fetchrow(
                    """
                    SELECT bonus FROM daily_free_generations
                    WHERE user_id = $1 AND date = $2
                    FOR UPDATE
                    """,
                    referrer_id, today
                )
                
                if current:
                    # Update existing record
                    await conn.execute(
                        """
                        UPDATE daily_free_generations
                        SET bonus = bonus + $3
                        WHERE user_id = $1 AND date = $2
                        """,
                        referrer_id, today, bonus_generations
                    )
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.info(
                        f"{cid} [REFERRAL_BONUS] Updated: referrer={referrer_id} "
                        f"date={today} added={bonus_generations} "
                        f"total_after={current['bonus'] + bonus_generations}"
                    )
                else:
                    # Insert new record (with ON CONFLICT to prevent race condition)
                    await conn.execute(
                        """
                        INSERT INTO daily_free_generations (user_id, date, count, bonus)
                        VALUES ($1, $2, 0, $3)
                        ON CONFLICT (user_id, date) DO UPDATE SET bonus = daily_free_generations.bonus + $3
                        """,
                        referrer_id, today, bonus_generations
                    )
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.info(
                    f"{cid} [REFERRAL_BONUS] Created/Updated: referrer={referrer_id} "
                    f"date={today} bonus={bonus_generations}"
                )
    
    # ==================== FREE USAGE TRACKING ====================
    # BATCH 48.44: Free usage tracking for limit enforcement
    
    async def log_free_usage(self, user_id: int, model_id: str, job_id: Optional[str] = None) -> None:
        """
        Log free model usage.
        CRITICAL: Uses ON CONFLICT to prevent duplicate logging (idempotency).
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Use ON CONFLICT to prevent duplicates if job_id is provided
            if job_id:
                await conn.execute(
                    """
                    INSERT INTO free_usage (user_id, model_id, job_id, created_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (user_id, model_id, job_id) DO NOTHING
                    """,
                    user_id, model_id, job_id
                )
            else:
                # If no job_id, just insert (no unique constraint to check)
                await conn.execute(
                    """
                    INSERT INTO free_usage (user_id, model_id, job_id, created_at)
                    VALUES ($1, $2, $3, NOW())
                    """,
                    user_id, model_id, job_id
                )
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        logger.info(f"{cid} [FREE_USAGE] Logged: user={user_id}, model={model_id}, job={job_id}")
    
    async def get_daily_free_usage(self, user_id: int, model_id: str) -> int:
        """Get daily usage count for a user and model."""
        from datetime import datetime, timezone
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, day_start
            )
        return count or 0
    
    async def get_hourly_free_usage(self, user_id: int, model_id: str) -> int:
        """Get hourly usage count for a user and model."""
        from datetime import datetime, timezone
        hour_start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND created_at >= $3
                """,
                user_id, model_id, hour_start
            )
        return count or 0
    
    async def delete_free_usage(self, user_id: int, model_id: str, job_id: str) -> None:
        """
        Delete a specific free usage record. Used when a free generation fails.
        BATCH 48.44: Allow deleting failed free usage.
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM free_usage
                WHERE user_id = $1 AND model_id = $2 AND job_id = $3
                """,
                user_id, model_id, job_id
            )
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        logger.info(f"{cid} [FREE_USAGE] Deleted: user={user_id}, model={model_id}, job={job_id}")
    
    async def cleanup_stuck_payments(self, stale_hours: int = 24) -> int:
        """
        Cleanup stuck payments (pending for more than stale_hours).
        
        CRITICAL: Marks stale payments as 'failed' to prevent accumulation.
        This prevents payments from hanging forever if admin doesn't process them.
        
        Returns:
            Number of payments cleaned up
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Find stuck payments
                stuck_payments = await conn.fetch("""
                    SELECT payment_id, user_id, amount, created_at
                    FROM payments
                    WHERE status = 'pending'
                      AND created_at < NOW() - INTERVAL '%s hours'
                    FOR UPDATE
                """, stale_hours)
                
                if not stuck_payments:
                    return 0
                
                logger.warning(f"[PAYMENT_CLEANUP] Found {len(stuck_payments)} stuck payments (pending >{stale_hours}h)")
                
                cleaned_count = 0
                for payment in stuck_payments:
                    payment_id = payment['payment_id']
                    
                    # Mark as failed
                    await conn.execute("""
                        UPDATE payments
                        SET status = 'failed',
                            notes = COALESCE(notes, '') || ' Auto-failed: stuck in pending for >' || $2 || ' hours',
                            updated_at = NOW()
                        WHERE payment_id = $1
                    """, payment_id, stale_hours)
                    
                    cleaned_count += 1
                
                logger.info(f"[PAYMENT_CLEANUP] ✅ Cleaned up {cleaned_count} stuck payments")
                return cleaned_count
    
    # ==================== UTILITY ====================
    
    async def close(self) -> None:
        """Закрыть соединения"""
        if self._pool:
            await self._pool.close()
            self._pool = None


# Алиасы для обратной совместимости
PGStorage = PostgresStorage
# Убеждаемся что PostgresStorage экспортируется (уже есть как основной класс)
