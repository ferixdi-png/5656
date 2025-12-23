"""
PostgreSQL storage implementation with async connection testing.
"""
import asyncio
import logging
from typing import Optional
import os

logger = logging.getLogger(__name__)

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    try:
        import psycopg
        from psycopg.rows import dict_row
        HAS_PSYCOPG = True
    except ImportError:
        HAS_PSYCOPG = False


async def async_check_pg(dsn: str, timeout: float = 5.0) -> bool:
    """
    Async check PostgreSQL connection.
    Does NOT use asyncio.run() or run_until_complete() - safe for nested event loops.
    
    Args:
        dsn: PostgreSQL connection string
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    if not dsn:
        return False
        
    try:
        if HAS_ASYNCPG:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn),
                timeout=timeout
            )
            await conn.close()
            return True
        elif HAS_PSYCOPG:
            conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(dsn),
                timeout=timeout
            )
            await conn.close()
            return True
        else:
            logger.error("No async PostgreSQL driver available (asyncpg or psycopg)")
            return False
    except asyncio.TimeoutError:
        logger.warning(f"PostgreSQL connection test timed out after {timeout}s")
        return False
    except Exception as e:
        logger.warning(f"PostgreSQL connection test failed: {e}")
        return False


def sync_check_pg(dsn: str, timeout: float = 5.0) -> bool:
    """
    Synchronous check PostgreSQL connection (for CLI tools only).
    Uses asyncio.run() - should NOT be called from async context.
    
    Args:
        dsn: PostgreSQL connection string
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    if not dsn:
        return False
        
    try:
        return asyncio.run(async_check_pg(dsn, timeout))
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            logger.error("sync_check_pg() called from async context. Use async_check_pg() instead.")
            raise
        logger.warning(f"PostgreSQL connection test failed: {e}")
        return False
    except Exception as e:
        logger.warning(f"PostgreSQL connection test failed: {e}")
        return False


class PGStorage:
    """PostgreSQL storage backend."""
    
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.getenv("DATABASE_URL")
        self._pool = None
        self._connection = None
        
    async def initialize(self) -> bool:
        """Initialize PostgreSQL connection pool."""
        if not self.dsn:
            raise ValueError("DATABASE_URL not set - storage requires database URL")
            
        # Test connection first
        if not await async_check_pg(self.dsn):
            raise ConnectionError("PostgreSQL connection test failed")
            
        if HAS_ASYNCPG:
            self._pool = await asyncpg.create_pool(self.dsn)
            logger.info("PostgreSQL connection pool created")
            await self._ensure_tables()
            return True
        elif HAS_PSYCOPG:
            self._connection = await psycopg.AsyncConnection.connect(self.dsn)
            logger.info("PostgreSQL connection created")
            await self._ensure_tables()
            return True
        else:
            raise ImportError("No async PostgreSQL driver available (asyncpg or psycopg required)")
    
    async def close(self):
        """Close PostgreSQL connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _ensure_tables(self) -> None:
        query = (
            "CREATE TABLE IF NOT EXISTS charge_events ("
            "task_id TEXT PRIMARY KEY,"
            "status TEXT NOT NULL,"
            "user_id BIGINT,"
            "amount NUMERIC,"
            "model_id TEXT,"
            "metadata JSONB,"
            "updated_at TIMESTAMPTZ DEFAULT NOW()"
            ")"
        )
        await self._execute(query, None)

    async def _execute(self, query: str, values: Optional[tuple]) -> None:
        if self._pool:
            async with self._pool.acquire() as conn:
                await conn.execute(query, *(values or ()))
            return
        if self._connection:
            query = query.replace("$1", "%s").replace("$2", "%s").replace("$3", "%s").replace("$4", "%s").replace("$5", "%s").replace("$6", "%s")
            async with self._connection.cursor() as cur:
                await cur.execute(query, values or ())
                await self._connection.commit()

    async def _fetchrow(self, query: str, values: Optional[tuple]) -> Optional[dict]:
        if self._pool:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, *(values or ()))
                return dict(row) if row else None
        if self._connection:
            query = query.replace("$1", "%s")
            async with self._connection.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, values or ())
                return await cur.fetchone()
        return None

    async def save_pending_charge(self, charge_info: dict) -> None:
        query = (
            "INSERT INTO charge_events (task_id, status, user_id, amount, model_id, metadata) "
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (task_id) DO UPDATE SET "
            "status = EXCLUDED.status, user_id = EXCLUDED.user_id, amount = EXCLUDED.amount, "
            "model_id = EXCLUDED.model_id, metadata = EXCLUDED.metadata, updated_at = NOW()"
        )
        values = (
            charge_info["task_id"],
            "pending",
            charge_info["user_id"],
            charge_info["amount"],
            charge_info["model_id"],
            charge_info.get("metadata", {}),
        )
        await self._execute(query, values)

    async def save_committed_charge(self, charge_info: dict) -> None:
        await self._update_status(charge_info, "committed")

    async def save_released_charge(self, charge_info: dict) -> None:
        await self._update_status(charge_info, "released")

    async def _update_status(self, charge_info: dict, status: str) -> None:
        query = (
            "INSERT INTO charge_events (task_id, status, user_id, amount, model_id, metadata) "
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (task_id) DO UPDATE SET "
            "status = EXCLUDED.status, updated_at = NOW()"
        )
        values = (
            charge_info["task_id"],
            status,
            charge_info["user_id"],
            charge_info["amount"],
            charge_info["model_id"],
            charge_info.get("metadata", {}),
        )
        await self._execute(query, values)

    async def get_charge_status(self, task_id: str) -> Optional[str]:
        query = "SELECT status FROM charge_events WHERE task_id = $1"
        row = await self._fetchrow(query, (task_id,))
        return row.get("status") if row else None


# Alias for compatibility
PostgresStorage = PGStorage
