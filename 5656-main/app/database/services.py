"""
Storage layer for database operations (asyncpg-based).

Production-safe with:
- Transactions for atomic operations
- Idempotency for payments
- Connection pooling
- Error handling
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

from app.database.schema import apply_schema, verify_schema
from app.utils.correlation import correlation_tag

logger = logging.getLogger(__name__)


class DatabaseService:
    """Main database service with connection pooling."""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """
        Initialize connection pool and apply schema.
        
        CRITICAL: Automatically recreates pool if initialization fails.
        """
        # BATCH 48.31: Check NO DATABASE MODE before attempting connection
        no_db_mode = os.getenv('NO_DATABASE_MODE', '').lower() in ('1', 'true', 'yes')
        if no_db_mode:
            raise RuntimeError("DatabaseService cannot be initialized in NO DATABASE MODE")
        
        if not HAS_ASYNCPG:
            raise ImportError("asyncpg is required for database operations")
        
        # Extract hostname from DSN for diagnostics
        db_hostname = "unknown"
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.dsn)
            db_hostname = parsed.hostname or "unknown"
        except Exception:
            pass
        
        from app.utils.correlation import correlation_tag
        cid = correlation_tag()
        logger.debug(f"{cid} [DB_INIT] 🔧 Attempting database connection to hostname: {db_hostname}")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._pool = await asyncpg.create_pool(
                    self.dsn,
                    min_size=2,
                    max_size=10,
                    command_timeout=60,
                    max_inactive_connection_lifetime=300  # CRITICAL: Close idle connections after 5min to prevent leaks
                )
                
                # Apply schema
                async with self._pool.acquire() as conn:
                    await apply_schema(conn)
                    schema_ok = await verify_schema(conn)
                    if not schema_ok:
                        raise RuntimeError("Schema verification failed")
                
                # CRITICAL: Log successful initialization with correlation ID for traceability
                logger.info(f"{cid} [DB_INIT] ✅ Database initialized with schema")
                return
                
            except (asyncpg.InterfaceError, asyncpg.PostgresConnectionError, OSError) as e:
                # NO DATABASE MODE: All DB errors logged at DEBUG level to avoid noise
                is_dns_error = isinstance(e, OSError) and hasattr(e, 'errno') and e.errno == -2
                
                if attempt < max_retries - 1:
                    delay = 0.5 * (2 ** attempt)  # Exponential backoff
                    logger.debug(
                        f"{cid} [DB_INIT] Pool initialization failed (attempt {attempt+1}/{max_retries}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt: All errors at DEBUG level (NO DATABASE MODE - expected)
                    logger.debug(
                        f"{cid} [DB_INIT] Database unavailable (NO DATABASE MODE - using FileStorage): {e}"
                    )
                    raise
    
    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactions."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    async def acquire(self):
        """Acquire connection from pool."""
        return await self._pool.acquire()
    
    async def release(self, conn):
        """Release connection back to pool."""
        await self._pool.release(conn)
    
    @asynccontextmanager
    async def get_connection(self):
        """Get connection context manager (compatible with FreeModelManager, AdminService, etc)."""
        conn = await self._pool.acquire()
        try:
            yield conn
        finally:
            await self._pool.release(conn)


class UserService:
    """User management operations."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def get_or_create(self, user_id: int, username: str = None, 
                           first_name: str = None) -> Dict[str, Any]:
        """Get or create user."""
        # CRITICAL: Validate user_id
        if not isinstance(user_id, int) or user_id <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [USER] Invalid user_id: {user_id} (must be positive integer)")
            raise ValueError(f"Invalid user_id: {user_id} (must be positive integer)")
        
        async with self.db.transaction() as conn:
            # Try to get existing user
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1",
                user_id
            )
            
            if user:
                # Update last_seen
                await conn.execute(
                    "UPDATE users SET last_seen_at = NOW() WHERE user_id = $1",
                    user_id
                )
                return dict(user)
            
            # Create new user + wallet
            user = await conn.fetchrow("""
                INSERT INTO users (id, user_id, username, first_name)
                VALUES ($1, $1, $2, $3)
                RETURNING *
            """, user_id, username, first_name)
            
            # Create wallet
            await conn.execute("""
                INSERT INTO wallets (user_id, balance_rub, hold_rub)
                VALUES ($1, 0.00, 0.00)
            """, user_id)
            
            logger.info(f"Created new user {user_id}")
            return dict(user)


class WalletService:
    """Wallet and balance operations."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def get_balance(self, user_id: int) -> Dict[str, Decimal]:
        """Get wallet balance."""
        # CRITICAL: Validate user_id
        if not isinstance(user_id, int) or user_id <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [WALLET] Invalid user_id: {user_id} (must be positive integer)")
            return {"balance_rub": Decimal("0.00"), "hold_rub": Decimal("0.00")}
        
        async with self.db.transaction() as conn:
            # P0-4: Note: get_balance is read-only, no FOR UPDATE needed
            wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1",
                user_id
            )
            if not wallet:
                return {"balance_rub": Decimal("0.00"), "hold_rub": Decimal("0.00")}
            return dict(wallet)
    
    async def get_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get ledger history."""
        # CRITICAL: Validate user_id
        if not isinstance(user_id, int) or user_id <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [WALLET] Invalid user_id: {user_id} (must be positive integer)")
            return []
        
        # CRITICAL: Validate limit
        if not isinstance(limit, int) or limit <= 0 or limit > 1000:
            limit = 20  # Safe default
        
        async with self.db.transaction() as conn:
            rows = await conn.fetch("""
                SELECT kind, amount_rub, status, ref, meta, created_at
                FROM ledger
                WHERE user_id = $1 AND status = 'done'
                ORDER BY created_at DESC
                LIMIT $2
            """, user_id, limit)
            return [dict(row) for row in rows]
    
    async def topup(self, user_id: int, amount_rub: Decimal, 
                   ref: str, meta: Dict = None) -> bool:
        """Add funds (idempotent)."""
        # CRITICAL: Validate user_id
        if not isinstance(user_id, int) or user_id <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [TOPUP] Invalid user_id: {user_id} (must be positive integer)")
            return False
        
        # CRITICAL: Validate amount is positive
        if amount_rub <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [TOPUP] Invalid amount: {amount_rub} (must be positive)")
            return False
        
        async with self.db.transaction() as conn:
            # Check idempotency
            existing = await conn.fetchval(
                "SELECT id FROM ledger WHERE ref = $1 AND status = 'done'",
                ref
            )
            if existing:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.warning(f"{cid} [TOPUP] Topup {ref} already processed")
                return False
            
            # Insert ledger entry - idempotent via UNIQUE index
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'topup', $2, 'done', $3, $4)
                ON CONFLICT (ref) DO NOTHING
            """, user_id, amount_rub, ref, meta or {})
            
            # CRITICAL: Use FOR UPDATE to prevent race conditions on balance update
            wallet = await conn.fetchrow(
                "SELECT balance_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                user_id
            )
            if not wallet:
                # Auto-create wallet if missing - idempotent via UNIQUE constraint
                await conn.execute(
                    "INSERT INTO wallets (user_id, balance_rub) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
                    user_id, amount_rub
                )
                # Re-fetch wallet after potential insert
                wallet = await conn.fetchrow(
                    "SELECT balance_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                    user_id
                )
                if wallet:
                    # Update wallet if it was just created or already existed
                    await conn.execute("""
                        UPDATE wallets
                        SET balance_rub = balance_rub + $2,
                            updated_at = NOW()
                        WHERE user_id = $1
                    """, user_id, amount_rub)
                else:
                    # Still no wallet after insert - this should not happen
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(f"{cid} [TOPUP] Failed to create wallet for user {user_id}")
                    return False
            else:
                # Update wallet
                await conn.execute("""
                    UPDATE wallets
                    SET balance_rub = balance_rub + $2,
                        updated_at = NOW()
                    WHERE user_id = $1
                """, user_id, amount_rub)
            
            logger.info(f"{correlation_tag()} Topup {user_id}: +{amount_rub} RUB (ref: {ref})")
            return True
    
    async def hold(self, user_id: int, amount_rub: Decimal, 
                  ref: str, meta: Dict = None) -> bool:
        """Hold funds for pending operation."""
        # CRITICAL: Validate amount is positive
        if amount_rub <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [HOLD] Invalid amount: {amount_rub} (must be positive)")
            return False
        
        async with self.db.transaction() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM ledger WHERE ref = $1 AND kind = 'hold' AND status = 'done'",
                ref
            )
            if existing:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.info(f"{cid} [HOLD] Hold {ref} already processed")
                return True

            # Check available balance (balance_rub - hold_rub must be >= amount_rub)
            wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                user_id
            )
            if not wallet:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.warning(f"{cid} [HOLD] Wallet not found for user {user_id}")
                return False
            
            # CRITICAL: Prevent negative balance after hold
            available_balance = wallet['balance_rub'] - wallet['hold_rub']
            if available_balance < amount_rub:
                logger.warning(
                    f"{correlation_tag()} Insufficient available balance: "
                    f"user={user_id} available={available_balance} required={amount_rub} "
                    f"balance_rub={wallet['balance_rub']} hold_rub={wallet['hold_rub']}"
                )
                return False
            
            # Insert ledger - idempotent via UNIQUE index
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'hold', $2, 'done', $3, $4)
                ON CONFLICT (ref) DO NOTHING
            """, user_id, amount_rub, ref, meta or {})
            
            # Move balance to hold
            # CRITICAL: Verify balance won't become negative after update
            new_balance = wallet['balance_rub'] - amount_rub
            if new_balance < 0:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(
                    f"{cid} [HOLD] Balance would become negative: user={user_id} "
                    f"balance_rub={wallet['balance_rub']} amount_rub={amount_rub} "
                    f"new_balance={new_balance}"
                )
                return False
            
            await conn.execute("""
                UPDATE wallets
                SET balance_rub = balance_rub - $2,
                    hold_rub = hold_rub + $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, amount_rub)
            
            # CRITICAL: Verify balance after update (defense-in-depth)
            verify_wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1",
                user_id
            )
            if verify_wallet and verify_wallet['balance_rub'] < 0:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(
                    f"{cid} [HOLD] CRITICAL: Balance became negative after hold: user={user_id} "
                    f"balance_rub={verify_wallet['balance_rub']} hold_rub={verify_wallet['hold_rub']}"
                )
                # Rollback is automatic via transaction
            
            logger.info(f"{correlation_tag()} Hold {user_id}: {amount_rub} RUB (ref: {ref})")
            return True
    
    async def charge(self, user_id: int, amount_rub: Decimal, 
                    ref: str, meta: Dict = None) -> bool:
        """Charge held funds (idempotent, prevents double-charge)."""
        # CRITICAL: Validate amount is positive
        if amount_rub <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [CHARGE] Invalid amount: {amount_rub} (must be positive)")
            return False
        
        async with self.db.transaction() as conn:
            # CRITICAL: SELECT FOR UPDATE to prevent race on same ref
            existing = await conn.fetchval(
                "SELECT id FROM ledger WHERE ref = $1 AND kind = 'charge' FOR UPDATE",
                ref
            )
            if existing:
                logger.info(f"{correlation_tag()} Charge {ref} already processed (idempotent)")
                return True

            # CRITICAL: Check that hold exists and was created for this ref
            hold_record = await conn.fetchrow(
                "SELECT id, amount_rub FROM ledger WHERE ref = $1 AND kind = 'hold' AND status = 'done' FOR UPDATE",
                ref
            )
            if not hold_record:
                logger.warning(
                    f"{correlation_tag()} Charge {ref} failed: no hold record found for ref (user={user_id})"
                )
                return False
            
            # Validate hold amount matches charge amount
            if hold_record['amount_rub'] < amount_rub:
                logger.warning(
                    f"{correlation_tag()} Charge {ref} failed: hold amount {hold_record['amount_rub']} < charge amount {amount_rub}"
                )
                return False
            
            # Check wallet hold_rub is sufficient
            wallet = await conn.fetchrow(
                "SELECT hold_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                user_id
            )
            if not wallet or wallet['hold_rub'] < amount_rub:
                logger.warning(
                    f"{correlation_tag()} Charge {ref} failed: insufficient hold_rub "
                    f"(user={user_id} hold_rub={wallet['hold_rub'] if wallet else 0} required={amount_rub})"
                )
                return False
            
            # Insert ledger - idempotent via UNIQUE index
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'charge', $2, 'done', $3, $4)
                ON CONFLICT (ref) DO NOTHING
            """, user_id, amount_rub, ref, meta or {})
            
            # Deduct from hold
            await conn.execute("""
                UPDATE wallets
                SET hold_rub = hold_rub - $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, amount_rub)
            
            logger.info(f"{correlation_tag()} Charge {user_id}: -{amount_rub} RUB (ref: {ref})")
            return True
    
    async def refund(self, user_id: int, amount_rub: Decimal, 
                    ref: str, meta: Dict = None) -> bool:
        """Refund from hold to balance (idempotent, prevents double-refund)."""
        # CRITICAL: Validate amount is positive
        if amount_rub <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [REFUND] Invalid amount: {amount_rub} (must be positive)")
            return False
        
        async with self.db.transaction() as conn:
            # CRITICAL: SELECT FOR UPDATE to prevent race on same ref
            existing = await conn.fetchval(
                "SELECT id FROM ledger WHERE ref = $1 AND kind = 'refund' FOR UPDATE",
                ref
            )
            if existing:
                logger.warning(f"{correlation_tag()} Refund {ref} already processed (idempotent)")
                return True
            
            # Insert ledger - idempotent via UNIQUE index
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'refund', $2, 'done', $3, $4)
                ON CONFLICT (ref) DO NOTHING
            """, user_id, amount_rub, ref, meta or {})
            
            # Move hold back to balance
            await conn.execute("""
                UPDATE wallets
                SET hold_rub = hold_rub - $2,
                    balance_rub = balance_rub + $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, amount_rub)
            
            # P0-5: CRITICAL - Verify balance and hold are not negative after refund
            verify_wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1",
                user_id
            )
            if verify_wallet:
                if verify_wallet['balance_rub'] < 0:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(
                        f"{cid} [REFUND] CRITICAL: Balance became negative after refund: user={user_id} "
                        f"balance_rub={verify_wallet['balance_rub']}"
                    )
                    # Rollback is automatic via transaction
                    return False
                if verify_wallet['hold_rub'] < 0:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(
                        f"{cid} [REFUND] CRITICAL: Hold became negative after refund: user={user_id} "
                        f"hold_rub={verify_wallet['hold_rub']}"
                    )
                    # Rollback is automatic via transaction
                    return False
            
            logger.info(f"{correlation_tag()} Refund {user_id}: +{amount_rub} RUB (ref: {ref})")
            return True

    async def release(self, user_id: int, amount_rub: Decimal,
                     ref: str, meta: Dict = None) -> bool:
        """
        Release held funds back to balance (idempotent).
        
        CRITICAL: Validates that hold exists before releasing to prevent negative hold_rub.
        """
        # CRITICAL: Validate user_id
        if not isinstance(user_id, int) or user_id <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [RELEASE] Invalid user_id: {user_id} (must be positive integer)")
            return False
        
        # CRITICAL: Validate amount is positive
        if amount_rub <= 0:
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            logger.warning(f"{cid} [RELEASE] Invalid amount: {amount_rub} (must be positive)")
            return False
        
        async with self.db.transaction() as conn:
            # Check if already released (idempotency)
            existing = await conn.fetchval(
                "SELECT id FROM ledger WHERE ref = $1 AND kind = 'release' AND status = 'done'",
                ref
            )
            if existing:
                logger.info(f"{correlation_tag()} Release {ref} already processed (idempotent)")
                return True

            # CRITICAL: Check that hold exists and is sufficient (FOR UPDATE to prevent race)
            wallet = await conn.fetchrow(
                "SELECT hold_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                user_id
            )
            if not wallet:
                logger.warning(f"{correlation_tag()} Release {ref} failed: wallet not found for user {user_id}")
                return False
            
            # CRITICAL: Validate hold_rub is sufficient before release
            if wallet['hold_rub'] < amount_rub:
                logger.warning(
                    f"{correlation_tag()} Release {ref} failed: insufficient hold_rub "
                    f"(user={user_id} hold_rub={wallet['hold_rub']} required={amount_rub})"
                )
                return False

            # Insert ledger - idempotent via UNIQUE index
            await conn.execute("""
                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                VALUES ($1, 'release', $2, 'done', $3, $4)
                ON CONFLICT (ref) DO NOTHING
            """, user_id, amount_rub, ref, meta or {})

            await conn.execute("""
                UPDATE wallets
                SET hold_rub = hold_rub - $2,
                    balance_rub = balance_rub + $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """, user_id, amount_rub)

            # P0-5: CRITICAL - Verify balance and hold are not negative after release
            verify_wallet = await conn.fetchrow(
                "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1",
                user_id
            )
            if verify_wallet:
                if verify_wallet['balance_rub'] < 0:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(
                        f"{cid} [RELEASE] CRITICAL: Balance became negative after release: user={user_id} "
                        f"balance_rub={verify_wallet['balance_rub']}"
                    )
                    # Rollback is automatic via transaction
                    return False
                if verify_wallet['hold_rub'] < 0:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(
                        f"{cid} [RELEASE] CRITICAL: Hold became negative after release: user={user_id} "
                        f"hold_rub={verify_wallet['hold_rub']}"
                    )
                    # Rollback is automatic via transaction
                    return False

            logger.info(f"{correlation_tag()} Release {user_id}: +{amount_rub} RUB (ref: {ref})")
            return True


class JobService:
    """Job (generation task) operations."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def create(self, user_id: int, model_id: str, category: str,
                    input_json: Dict, price_rub: Decimal, 
                    idempotency_key: str) -> Optional[int]:
        """Create new job (idempotent)."""
        async with self.db.transaction() as conn:
            # Check idempotency
            existing = await conn.fetchval(
                "SELECT id FROM jobs WHERE idempotency_key = $1",
                idempotency_key
            )
            if existing:
                logger.warning(f"Job {idempotency_key} already exists")
                return existing
            
            # P1-3: Insert job with ON CONFLICT for idempotency (idempotency_key is UNIQUE)
            job_id = await conn.fetchval("""
                INSERT INTO jobs (user_id, model_id, category, input_json, price_rub, 
                                 status, idempotency_key)
                VALUES ($1, $2, $3, $4, $5, 'draft', $6)
                ON CONFLICT (idempotency_key) DO UPDATE SET
                    updated_at = NOW()
                RETURNING id
            """, user_id, model_id, category, input_json, price_rub, idempotency_key)
            
            logger.info(f"Created job {job_id} for user {user_id}")
            return job_id
    
    async def get(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        async with self.db.transaction() as conn:
            job = await conn.fetchrow(
                "SELECT * FROM jobs WHERE id = $1",
                job_id
            )
            return dict(job) if job else None
    
    async def update_status(self, job_id: int, status: str, 
                           kie_task_id: str = None, kie_status: str = None,
                           result_json: Dict = None, error_text: str = None):
        """Update job status."""
        async with self.db.transaction() as conn:
            await conn.execute("""
                UPDATE jobs
                SET status = $2,
                    kie_task_id = COALESCE($3, kie_task_id),
                    kie_status = COALESCE($4, kie_status),
                    result_json = COALESCE($5, result_json),
                    error_text = COALESCE($6, error_text),
                    updated_at = NOW(),
                    finished_at = CASE WHEN $2 IN ('done', 'failed', 'canceled') 
                                      THEN NOW() ELSE finished_at END
                WHERE id = $1
            """, job_id, status, kie_task_id, kie_status, result_json, error_text)
    
    async def list_user_jobs(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get user's jobs."""
        async with self.db.transaction() as conn:
            rows = await conn.fetch("""
                SELECT id, model_id, status, price_rub, created_at, finished_at
                FROM jobs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, user_id, limit)
            return [dict(row) for row in rows]


class UIStateService:
    """UI state management (FSM)."""
    
    def __init__(self, db: DatabaseService):
        self.db = db
    
    async def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get UI state."""
        # CRITICAL: Validate user_id is positive
        if user_id <= 0:
            logger.warning(f"[FSM] Invalid user_id: {user_id} (must be positive)")
            return None
        
        async with self.db.transaction() as conn:
            state = await conn.fetchrow(
                "SELECT state, data FROM ui_state WHERE user_id = $1",
                user_id
            )
            return dict(state) if state else None
    
    async def set(self, user_id: int, state: str, data: Dict = None, 
                 ttl_minutes: int = 60):
        """Set UI state with TTL."""
        # CRITICAL: Validate user_id is positive
        if user_id <= 0:
            logger.warning(f"[FSM] Invalid user_id: {user_id} (must be positive)")
            return
        
        async with self.db.transaction() as conn:
            expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
            await conn.execute("""
                INSERT INTO ui_state (user_id, state, data, expires_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE
                SET state = EXCLUDED.state,
                    data = EXCLUDED.data,
                    updated_at = NOW(),
                    expires_at = EXCLUDED.expires_at
            """, user_id, state, data or {}, expires_at)
    
    async def clear(self, user_id: int):
        """Clear UI state."""
        # CRITICAL: Validate user_id is positive
        if user_id <= 0:
            logger.warning(f"[FSM] Invalid user_id: {user_id} (must be positive)")
            return
        
        async with self.db.transaction() as conn:
            await conn.execute(
                "DELETE FROM ui_state WHERE user_id = $1",
                user_id
            )
    
    async def cleanup_expired(self):
        """Remove expired states."""
        async with self.db.transaction() as conn:
            # CRITICAL: Get count before deletion for logging
            count_before = await conn.fetchval(
                "SELECT COUNT(*) FROM ui_state WHERE expires_at < NOW()"
            )
            
            deleted = await conn.execute(
                "DELETE FROM ui_state WHERE expires_at < NOW()"
            )
            
            # CRITICAL: Log actual count of deleted records for monitoring with correlation ID
            from app.utils.correlation import correlation_tag
            cid = correlation_tag()
            if count_before and count_before > 0:
                logger.info(f"{cid} [FSM_CLEANUP] Cleaned up {count_before} expired UI states")
            elif deleted != "DELETE 0":
                # Fallback: try to extract count from DELETE response
                logger.info(f"{cid} [FSM_CLEANUP] Cleaned up expired UI states: {deleted}")
            else:
                # Log even when no expired states found (for monitoring)
                logger.debug(f"{cid} [FSM_CLEANUP] No expired UI states to clean up")
