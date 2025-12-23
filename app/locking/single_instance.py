"""
PostgreSQL advisory lock for singleton instance management.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    try:
        import psycopg
        HAS_PSYCOPG = True
    except ImportError:
        HAS_PSYCOPG = False


class SingletonLock:
    """
    PostgreSQL advisory lock for ensuring only one instance runs.
    """
    
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn
        self._connection = None
        self._lock_id = 12345  # Fixed lock ID
    
    async def acquire(self, timeout: float = 5.0) -> bool:
        """
        Acquire singleton lock.
        
        Args:
            timeout: Lock acquisition timeout in seconds
            
        Returns:
            True if lock acquired, False otherwise
            
        Raises:
            ValueError: If dsn not provided
            ImportError: If no PostgreSQL driver available
            ConnectionError: If connection fails
            asyncio.TimeoutError: If timeout exceeded
        """
        if not self.dsn:
            raise ValueError("Database URL required for singleton lock")
        
        if HAS_ASYNCPG:
            self._connection = await asyncio.wait_for(
                asyncpg.connect(self.dsn),
                timeout=timeout
            )
            # Try to acquire advisory lock
            acquired = await self._connection.fetchval(
                "SELECT pg_try_advisory_lock($1)",
                self._lock_id
            )
            if acquired:
                logger.info("Singleton lock acquired")
                return True
            else:
                logger.warning("Singleton lock not acquired (another instance running?)")
                await self._connection.close()
                self._connection = None
                return False
        elif HAS_PSYCOPG:
            self._connection = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(self.dsn),
                timeout=timeout
            )
            async with self._connection.cursor() as cur:
                await cur.execute(
                    "SELECT pg_try_advisory_lock(%s)",
                    (self._lock_id,)
                )
                result = await cur.fetchone()
                if result and result[0]:
                    logger.info("Singleton lock acquired")
                    return True
                else:
                    logger.warning("Singleton lock not acquired")
                    await self._connection.close()
                    self._connection = None
                    return False
        else:
            raise ImportError("No PostgreSQL driver available (asyncpg or psycopg required)")
    
    async def release(self) -> None:
        """Release singleton lock."""
        if self._connection:
            try:
                if HAS_ASYNCPG:
                    await self._connection.execute(
                        "SELECT pg_advisory_unlock($1)",
                        self._lock_id
                    )
                elif HAS_PSYCOPG:
                    async with self._connection.cursor() as cur:
                        await cur.execute(
                            "SELECT pg_advisory_unlock(%s)",
                            (self._lock_id,)
                        )
                await self._connection.close()
                self._connection = None
                logger.info("Singleton lock released")
            except Exception as e:
                logger.warning(f"Error releasing singleton lock: {e}")

