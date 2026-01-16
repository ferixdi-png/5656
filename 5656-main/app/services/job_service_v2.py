"""
Job Service - атомарные операции с jobs table (unified schema)

CRITICAL INVARIANTS:
1. Users MUST exist before jobs
2. Jobs created with idempotency_key (duplicate-safe)
3. Balance operations atomic with job creation
4. Callbacks never lost (orphan reconciliation)
5. Telegram delivery guaranteed (retry logic)
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

from app.storage.status import normalize_job_status

logger = logging.getLogger(__name__)


class JobServiceV2:
    """
    Production-ready job service following felores/kie-ai-mcp-server patterns.
    
    Key features:
    - Atomic job creation (user check → balance hold → job insert → KIE task)
    - Idempotent operations (duplicate requests handled gracefully)
    - No orphan jobs (strict lifecycle management)
    - Guaranteed delivery (chat_id + retry logic)
    """
    
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def create_job_atomic(
        self,
        user_id: int,
        model_id: str,
        category: str,
        input_params: Dict[str, Any],
        price_rub: Decimal,
        chat_id: Optional[int] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Atomic job creation following STRICT lifecycle:
        1. Validate user exists (FK enforcement)
        2. Check idempotency (duplicate safety)
        3. Hold balance (if price > 0)
        4. Insert job (status='pending')
        5. Return job for KIE task creation
        
        CRITICAL: Job created BEFORE calling KIE API to avoid orphan callbacks.
        
        Returns:
            {
                'id': int,
                'user_id': int,
                'model_id': str,
                'idempotency_key': str,
                'status': 'pending',
                ...
            }
        
        Raises:
            ValueError: User not found, invalid input
            InsufficientFundsError: Balance too low
        """
        # CRITICAL: Validate inputs
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id} (must be positive integer)")
        if not model_id or not isinstance(model_id, str):
            raise ValueError(f"Invalid model_id: {model_id} (must be non-empty string)")
        if not category or not isinstance(category, str):
            raise ValueError(f"Invalid category: {category} (must be non-empty string)")
        if not isinstance(input_params, dict):
            raise ValueError(f"Invalid input_params: {input_params} (must be dict)")
        if not isinstance(price_rub, (int, float, Decimal)) or price_rub < 0:
            raise ValueError(f"Invalid price_rub: {price_rub} (must be non-negative number)")
        
        if not idempotency_key:
            idempotency_key = f"job:{user_id}:{uuid.uuid4()}"
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # PHASE 1: Check if already exists (idempotency)
                existing = await conn.fetchrow(
                    "SELECT * FROM jobs WHERE idempotency_key = $1",
                    idempotency_key
                )
                if existing:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.info(f"{cid} [JOB] Idempotent duplicate: key={idempotency_key} id={existing['id']}")
                    return dict(existing)
                
                # PHASE 2: Validate user exists (enforces FK)
                user = await conn.fetchrow(
                    "SELECT user_id FROM users WHERE user_id = $1",
                    user_id
                )
                if not user:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(f"{cid} [JOB] User {user_id} not found - create user first")
                    raise ValueError(f"User {user_id} not found - create user first")
                
                # PHASE 3: Check balance if paid model
                if price_rub > 0:
                    # CRITICAL: Use FOR UPDATE to prevent race conditions on balance check
                    wallet = await conn.fetchrow(
                        "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                        user_id
                    )
                    if not wallet:
                        # Auto-create wallet if missing
                        await conn.execute(
                            "INSERT INTO wallets (user_id, balance_rub) VALUES ($1, 0.00)",
                            user_id
                        )
                        wallet = {'balance_rub': Decimal('0.00'), 'hold_rub': Decimal('0.00')}
                    
                    # CRITICAL: Check available balance (balance_rub - hold_rub must be >= price_rub)
                    available = wallet['balance_rub'] - wallet['hold_rub']
                    if available < price_rub:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.warning(
                            f"{cid} [JOB] Insufficient funds: user={user_id} "
                            f"available={available} required={price_rub} "
                            f"balance_rub={wallet['balance_rub']} hold_rub={wallet['hold_rub']}"
                        )
                        raise InsufficientFundsError(
                            f"Insufficient funds: need {price_rub} RUB, have {available} RUB"
                        )
                    
                    # CRITICAL: Prevent negative balance after hold
                    if wallet['balance_rub'] < price_rub:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.error(
                            f"{cid} [JOB] Balance would become negative: user={user_id} "
                            f"balance_rub={wallet['balance_rub']} price_rub={price_rub}"
                        )
                        raise InsufficientFundsError(
                            f"Insufficient funds: need {price_rub} RUB, have {wallet['balance_rub']} RUB"
                        )
                    
                    # PHASE 4: Hold balance (prevents double-spend)
                    await conn.execute("""
                        UPDATE wallets
                        SET hold_rub = hold_rub + $2,
                            updated_at = NOW()
                        WHERE user_id = $1
                    """, user_id, price_rub)
                    
                    # Record hold in ledger (for audit trail) - idempotent via UNIQUE index
                    await conn.execute("""
                        INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                        VALUES ($1, 'hold', $2, 'done', $3, $4)
                        ON CONFLICT (ref) DO NOTHING
                    """, user_id, price_rub, idempotency_key, {
                        'model_id': model_id,
                        'category': category
                    })
                
                # PHASE 5: Validate and serialize input_params (prevent DoS via large JSON)
                import json
                try:
                    input_json = json.dumps(input_params, ensure_ascii=False)
                    # CRITICAL: Limit JSON size to prevent DoS (10MB max)
                    MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB
                    if len(input_json.encode('utf-8')) > MAX_JSON_SIZE:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.error(f"{cid} [JOB] Input params JSON too large: {len(input_json.encode('utf-8'))} bytes (max {MAX_JSON_SIZE})")
                        raise ValueError(f"Input params JSON too large: {len(input_json.encode('utf-8'))} bytes (max {MAX_JSON_SIZE})")
                except (TypeError, ValueError) as e:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.error(f"{cid} [JOB] Invalid input_params for job: {e}")
                    raise ValueError(f"Invalid job input_params: {e}")
                
                # PHASE 6: Create job (status='pending')
                # P1-3: ON CONFLICT for idempotency (idempotency_key is UNIQUE)
                job = await conn.fetchrow("""
                    INSERT INTO jobs (
                        user_id, model_id, category, input_json, price_rub,
                        status, idempotency_key, chat_id, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, 'pending', $6, $7, NOW())
                    ON CONFLICT (idempotency_key) DO UPDATE SET
                        updated_at = NOW()
                    RETURNING *
                """, user_id, model_id, category, input_json, price_rub,
                     idempotency_key, chat_id)
                
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.info(
                    f"{cid} [JOB_CREATE] id={job['id']} user={user_id} model={model_id} "
                    f"price={price_rub} status=pending idempotency_key={idempotency_key}"
                )
                
                return dict(job)
    
    async def update_with_kie_task(
        self,
        job_id: int,
        kie_task_id: str,
        status: str = 'running'
    ) -> None:
        """
        Update job with KIE task_id after successful API call.
        
        Lifecycle: pending → running
        
        CRITICAL: Only update if job is in non-terminal status.
        """
        # CRITICAL: Validate inputs
        if not isinstance(job_id, int) or job_id <= 0:
            raise ValueError(f"Invalid job_id: {job_id} (must be positive integer)")
        if not kie_task_id or not isinstance(kie_task_id, str):
            raise ValueError(f"Invalid kie_task_id: {kie_task_id} (must be non-empty string)")
        if not status or not isinstance(status, str):
            raise ValueError(f"Invalid status: {status} (must be non-empty string)")
        
        from app.storage.status import is_terminal_status
        
        normalized_status = normalize_job_status(status)
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Check current status (with lock to prevent race)
                current_job = await conn.fetchrow(
                    "SELECT status FROM jobs WHERE id = $1 FOR UPDATE",
                    job_id
                )
                
                if not current_job:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(f"{cid} [JOB_UPDATE] Job {job_id} not found for task update")
                    return
                
                current_status = current_job['status']
                
                # Prevent updating terminal jobs
                if is_terminal_status(current_status):
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(
                        f"{cid} [JOB_UPDATE] Ignoring task update for job {job_id}: already in terminal status {current_status}"
                    )
                    return
                
                # Update job
                await conn.execute("""
                    UPDATE jobs
                    SET kie_task_id = $2,
                        status = $3,
                        updated_at = NOW()
                    WHERE id = $1
                """, job_id, kie_task_id, normalized_status)
                
                logger.info(f"[JOB_UPDATE] id={job_id} task={kie_task_id} status={normalized_status} (from {current_status})")
    
    async def update_from_callback(
        self,
        job_id: int,
        status: str,
        result_json: Optional[Dict[str, Any]] = None,
        error_text: Optional[str] = None,
        kie_status: Optional[str] = None
    ) -> None:
        """
        Update job from KIE callback.
        
        Lifecycle: running → done/failed
        
        CRITICAL: If status='done', also release held balance.
        """
        from app.storage.status import is_terminal_status
        
        normalized_status = normalize_job_status(status)
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # CRITICAL: Check job exists and get current status (with lock to prevent race)
                job = await conn.fetchrow(
                    "SELECT user_id, price_rub, idempotency_key, status FROM jobs WHERE id = $1 FOR UPDATE",
                    job_id
                )
                if not job:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(f"{cid} [JOB_UPDATE] Job {job_id} not found")
                    return
                
                current_status = job['status']
                
                # CRITICAL: Prevent invalid transitions from terminal statuses
                if is_terminal_status(current_status):
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(
                        f"{cid} [JOB_UPDATE] Ignoring callback for job {job_id}: already in terminal status {current_status}, "
                        f"attempted transition to {normalized_status}"
                    )
                    return
                
                # Update job (only if not already terminal)
                await conn.execute("""
                    UPDATE jobs
                    SET status = $2,
                        kie_status = $3,
                        result_json = $4,
                        error_text = $5,
                        finished_at = CASE WHEN $2 IN ('done', 'failed', 'canceled') THEN NOW() ELSE finished_at END,
                        updated_at = NOW()
                    WHERE id = $1
                """, job_id, normalized_status, kie_status, result_json, error_text)
                
                # Get job data (already fetched above)
                user_id = job['user_id']
                price_rub = job['price_rub']
                
                # CRITICAL: DO NOT charge balance here - wait for successful delivery
                # Balance will be charged in mark_delivered() after result is successfully sent to user
                # This ensures user only pays when they actually receive the result
                
                # If job failed or canceled, release held balance
                if normalized_status in ('failed', 'canceled') and price_rub > 0:
                    # CRITICAL FIX: Use FOR UPDATE to prevent race conditions on balance release
                    wallet_before = await conn.fetchrow(
                        "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                        user_id
                    )
                    if not wallet_before:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.warning(f"{cid} [JOB_REFUND] Wallet not found for user {user_id}, skipping release")
                        # Continue with job update even if wallet not found
                    else:
                        balance_before = wallet_before['balance_rub']
                        hold_before = wallet_before['hold_rub']
                        
                        # CRITICAL FIX: Verify hold_rub is sufficient before release
                        # If hold is less than price, release only what we have (partial release)
                        actual_release_amount = min(price_rub, hold_before)
                        if actual_release_amount <= 0:
                            from app.utils.correlation import correlation_tag
                            cid = correlation_tag()
                            logger.info(f"{cid} [JOB_REFUND] No hold to release: user={user_id} job={job_id} hold_rub={hold_before}")
                        else:
                            # FAILURE: Release hold (no charge)
                            # CRITICAL: Use direct SQL within transaction for atomicity with job update
                            # Note: WalletService.release would require separate transaction, breaking atomicity
                            # This is safe because we're already in a transaction with FOR UPDATE lock
                            ref = f"job:{job_id}:refund"
                            
                            # Check idempotency: if release already exists in ledger, skip
                            existing_release = await conn.fetchval(
                                "SELECT id FROM ledger WHERE ref = $1 AND kind = 'release' AND status = 'done'",
                                ref
                            )
                            if existing_release:
                                from app.utils.correlation import correlation_tag
                                cid = correlation_tag()
                                logger.info(f"{cid} [JOB_REFUND] Release {ref} already processed (idempotent)")
                            else:
                                # Release hold (only the amount we actually have)
                                await conn.execute("""
                                    UPDATE wallets
                                    SET hold_rub = hold_rub - $2,
                                        updated_at = NOW()
                                    WHERE user_id = $1
                                """, user_id, actual_release_amount)
                                
                                # Record release in ledger for idempotency - idempotent via UNIQUE index
                                await conn.execute("""
                                    INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                                    VALUES ($1, 'release', $2, 'done', $3, $4)
                                    ON CONFLICT (ref) DO NOTHING
                                """, user_id, actual_release_amount, ref, {
                                    'job_id': job_id,
                                    'reason': 'job_failed',
                                    'original_price': float(price_rub),
                                    'actual_release': float(actual_release_amount)
                                })
                                
                                # Get balance AFTER release (for logging)
                                wallet_after = await conn.fetchrow(
                                    "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1",
                                    user_id
                                )
                                if not wallet_after:
                                    from app.utils.correlation import correlation_tag
                                    cid = correlation_tag()
                                    logger.error(f"{cid} [JOB_REFUND] Wallet disappeared after release: user={user_id}")
                                    raise ValueError(f"Wallet disappeared after release: user={user_id}")
                                
                                balance_after = wallet_after['balance_rub']
                                hold_after = wallet_after['hold_rub']
                                
                                # CRITICAL FIX: Verify hold didn't become negative (defense-in-depth)
                                if hold_after < 0:
                                    from app.utils.correlation import correlation_tag
                                    cid = correlation_tag()
                                    logger.error(
                                        f"{cid} [JOB_REFUND] CRITICAL: Hold became negative after release: "
                                        f"user={user_id} job={job_id} hold_after={hold_after}"
                                    )
                                    # Transaction will rollback automatically
                                    raise ValueError(f"Hold became negative: {hold_after}")
                                
                                logger.info(
                                    f"[BALANCE_REFUND] user={user_id} job={job_id} price={price_rub} "
                                    f"actual_release={actual_release_amount} "
                                    f"balance_before={balance_before} balance_after={balance_after} "
                                    f"hold_before={hold_before} hold_after={hold_after}"
                                )
                
                logger.info(f"[JOB_CALLBACK] id={job_id} status={normalized_status}")
    
    async def mark_delivered(self, job_id: int) -> None:
        """
        Mark job result as delivered to Telegram.
        
        CRITICAL: Charge balance ONLY after successful delivery.
        This ensures user only pays when they actually receive the result.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Get job data with lock
                job = await conn.fetchrow(
                    "SELECT user_id, price_rub, idempotency_key, status, delivered_at FROM jobs WHERE id = $1 FOR UPDATE",
                    job_id
                )
                if not job:
                    logger.warning(f"[MARK_DELIVERED] Job {job_id} not found")
                    return
                
                # Check if already delivered (idempotency)
                if job['delivered_at']:
                    logger.info(f"[MARK_DELIVERED] Job {job_id} already marked as delivered (idempotent)")
                    return
                
                # Mark as delivered
                await conn.execute("""
                    UPDATE jobs
                    SET delivered_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                """, job_id)
                
                # CRITICAL: Charge balance ONLY after successful delivery
                user_id = job['user_id']
                price_rub = job['price_rub']
                
                if price_rub > 0 and job['status'] == 'done':
                    # CRITICAL FIX: Check idempotency BEFORE any balance operations
                    charge_ref = f"job:{job_id}:delivered"
                    existing_charge = await conn.fetchval(
                        "SELECT id FROM ledger WHERE ref = $1 AND kind = 'charge' AND status = 'done'",
                        charge_ref
                    )
                    if existing_charge:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.info(f"{cid} [MARK_DELIVERED] Charge {charge_ref} already processed (idempotent)")
                        return
                    
                    # CRITICAL FIX: Use FOR UPDATE to prevent race conditions on balance check
                    wallet_before = await conn.fetchrow(
                        "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1 FOR UPDATE",
                        user_id
                    )
                    if not wallet_before:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.error(f"{cid} [MARK_DELIVERED] Wallet not found for user {user_id}")
                        return
                    
                    balance_before = wallet_before['balance_rub']
                    hold_before = wallet_before['hold_rub']
                    
                    # CRITICAL FIX: Verify hold_rub is sufficient before charging
                    if hold_before < price_rub:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.error(
                            f"{cid} [MARK_DELIVERED] Insufficient hold: user={user_id} job={job_id} "
                            f"hold_rub={hold_before} required={price_rub}"
                        )
                        return
                    
                    # CRITICAL FIX: Verify balance won't become negative after charge
                    if balance_before < price_rub:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.error(
                            f"{cid} [MARK_DELIVERED] Balance would become negative: user={user_id} job={job_id} "
                            f"balance_rub={balance_before} price_rub={price_rub}"
                        )
                        return
                    
                    # SUCCESS: Release hold + charge balance (ONLY after delivery)
                    await conn.execute("""
                        UPDATE wallets
                        SET balance_rub = balance_rub - $2,
                            hold_rub = hold_rub - $2,
                            updated_at = NOW()
                        WHERE user_id = $1
                    """, user_id, price_rub)
                    
                    # Get balance AFTER charge (for logging)
                    wallet_after = await conn.fetchrow(
                        "SELECT balance_rub, hold_rub FROM wallets WHERE user_id = $1",
                        user_id
                    )
                    if not wallet_after:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.error(f"{cid} [MARK_DELIVERED] Wallet disappeared after charge: user={user_id}")
                        raise ValueError(f"Wallet disappeared after charge: user={user_id}")
                    
                    balance_after = wallet_after['balance_rub']
                    hold_after = wallet_after['hold_rub']
                    
                    # CRITICAL FIX: Verify balance didn't become negative (defense-in-depth)
                    if balance_after < 0:
                        from app.utils.correlation import correlation_tag
                        cid = correlation_tag()
                        logger.error(
                            f"{cid} [MARK_DELIVERED] CRITICAL: Balance became negative after charge: "
                            f"user={user_id} job={job_id} balance_after={balance_after}"
                        )
                        # Transaction will rollback automatically
                        raise ValueError(f"Balance became negative: {balance_after}")
                    
                    # Record charge in ledger (idempotency already checked above, but use ON CONFLICT for safety)
                    # UNIQUE INDEX idx_ledger_idempotency on ledger(ref) WHERE ref IS NOT NULL AND status = 'done'
                    await conn.execute("""
                        INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                        VALUES ($1, 'charge', $2, 'done', $3, $4)
                        ON CONFLICT (ref) DO NOTHING
                    """, user_id, price_rub, charge_ref, {
                        'job_id': job_id,
                        'idempotency_key': job['idempotency_key'],
                        'charged_after_delivery': True
                    })
                    
                    logger.info(
                        f"[BALANCE_CHARGE_AFTER_DELIVERY] user={user_id} job={job_id} price={price_rub} "
                        f"balance_before={balance_before} balance_after={balance_after} "
                        f"hold_before={hold_before} hold_after={hold_after}"
                    )
                elif price_rub > 0 and job['status'] != 'done':
                    logger.warning(
                        f"[MARK_DELIVERED_WARN] Job {job_id} marked as delivered but status={job['status']}, "
                        f"not charging balance (job may have failed)"
                    )
                
                logger.info(f"[TELEGRAM_DELIVERY] job={job_id} delivered=True")
    
    async def get_by_id(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID (integer)
            
        Returns:
            Job dict or None if not found
        """
        # CRITICAL: Validate input
        if not isinstance(job_id, int) or job_id <= 0:
            logger.warning(f"[JOB_SERVICE] Invalid job_id in get_by_id: {job_id}")
            return None
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)
                return dict(row) if row else None
        except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
            # Database connection errors
            logger.error(f"[JOB_SERVICE] Database connection error getting job by id {job_id}: {e}", exc_info=True)
            return None
        except asyncpg.PostgresError as e:
            # Database query errors
            logger.error(f"[JOB_SERVICE] Database error getting job by id {job_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            # Unexpected errors
            logger.error(f"[JOB_SERVICE] Unexpected error getting job by id {job_id}: {e}", exc_info=True)
            return None
    
    async def get_by_task_id(self, kie_task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job by KIE task_id (for callbacks).
        
        Args:
            kie_task_id: KIE task ID (string)
            
        Returns:
            Job dict or None if not found
        """
        # CRITICAL: Validate input
        if not kie_task_id or not isinstance(kie_task_id, str):
            logger.warning(f"[JOB_SERVICE] Invalid kie_task_id in get_by_task_id: {kie_task_id}")
            return None
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM jobs WHERE kie_task_id = $1", kie_task_id)
                return dict(row) if row else None
        except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
            # Database connection errors
            logger.error(f"[JOB_SERVICE] Database connection error getting job by task_id {kie_task_id}: {e}", exc_info=True)
            return None
        except asyncpg.PostgresError as e:
            # Database query errors
            logger.error(f"[JOB_SERVICE] Database error getting job by task_id {kie_task_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            # Unexpected errors
            logger.error(f"[JOB_SERVICE] Unexpected error getting job by task_id {kie_task_id}: {e}", exc_info=True)
            return None
    
    async def get_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get job by idempotency_key.
        
        Args:
            key: Idempotency key (string)
            
        Returns:
            Job dict or None if not found
        """
        # CRITICAL: Validate input
        if not key or not isinstance(key, str):
            logger.warning(f"[JOB_SERVICE] Invalid idempotency_key in get_by_idempotency_key: {key}")
            return None
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM jobs WHERE idempotency_key = $1", key)
                return dict(row) if row else None
        except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
            # Database connection errors
            logger.error(f"[JOB_SERVICE] Database connection error getting job by idempotency_key {key}: {e}", exc_info=True)
            return None
        except asyncpg.PostgresError as e:
            # Database query errors
            logger.error(f"[JOB_SERVICE] Database error getting job by idempotency_key {key}: {e}", exc_info=True)
            return None
        except Exception as e:
            # Unexpected errors
            logger.error(f"[JOB_SERVICE] Unexpected error getting job by idempotency_key {key}: {e}", exc_info=True)
            return None
    
    async def cleanup_stale_jobs(self, stale_minutes: int = 30) -> int:
        """
        Cleanup stale jobs (running for more than stale_minutes).
        
        CRITICAL: Marks stale jobs as 'failed' and releases held balance.
        This prevents jobs from hanging forever if callback is lost.
        
        Returns:
            Number of jobs cleaned up
        """
        from app.storage.status import normalize_job_status
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Find stale running jobs
                # CRITICAL: Use index idx_jobs_status_updated_at for optimal performance
                stale_jobs = await conn.fetch("""
                    SELECT id, user_id, price_rub, idempotency_key
                    FROM jobs
                    WHERE status = 'running'
                      AND updated_at < NOW() - INTERVAL '%s minutes'
                    FOR UPDATE
                """, stale_minutes)
                
                if not stale_jobs:
                    return 0
                
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.warning(
                    f"{cid} [JOB_CLEANUP] Found {len(stale_jobs)} stale jobs "
                    f"(running >{stale_minutes}min) - marking as failed and releasing holds"
                )
                
                cleaned_count = 0
                for job in stale_jobs:
                    job_id = job['id']
                    user_id = job['user_id']
                    price_rub = job['price_rub']
                    idempotency_key = job.get('idempotency_key', 'unknown')
                    
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.info(
                        f"{cid} [JOB_CLEANUP] Cleaning stale job: id={job_id} user={user_id} "
                        f"price={price_rub} idempotency={idempotency_key}"
                    )
                    
                    # Mark as failed
                    await conn.execute("""
                        UPDATE jobs
                        SET status = 'failed',
                            error_text = 'Job timeout: no callback received after ' || $2 || ' minutes',
                            finished_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $1
                    """, job_id, stale_minutes)
                    
                    # Release held balance (if any)
                    if price_rub > 0:
                        # Check if hold exists for this job
                        hold_ref = f"job:{job_id}"
                        hold_exists = await conn.fetchval(
                            "SELECT 1 FROM ledger WHERE ref = $1 AND kind = 'hold' AND status = 'done'",
                            hold_ref
                        )
                        
                        if hold_exists:
                            # Release hold back to balance
                            await conn.execute("""
                                UPDATE wallets
                                SET balance_rub = balance_rub + $2,
                                    hold_rub = hold_rub - $2,
                                    updated_at = NOW()
                                WHERE user_id = $1
                            """, user_id, price_rub)
                            
                            # Record release in ledger - idempotent via UNIQUE index
                            await conn.execute("""
                                INSERT INTO ledger (user_id, kind, amount_rub, status, ref, meta)
                                VALUES ($1, 'release', $2, 'done', $3, $4)
                                ON CONFLICT (ref) DO NOTHING
                            """, user_id, price_rub, hold_ref, {'reason': 'stale_job_cleanup', 'job_id': job_id})
                            
                            logger.info(
                                f"[JOB_CLEANUP] Released hold for stale job {job_id}: "
                                f"user={user_id} amount={price_rub}"
                            )
                    
                    cleaned_count += 1
                
                logger.info(f"[JOB_CLEANUP] ✅ Cleaned up {cleaned_count} stale jobs")
                return cleaned_count
    
    async def list_user_jobs(
        self,
        user_id: int,
        limit: int = 20,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List user's jobs (for history).
        
        Args:
            user_id: User ID
            limit: Maximum number of jobs to return
            status: Optional status filter
            
        Returns:
            List of job dicts
        """
        # CRITICAL: Validate inputs
        if not isinstance(user_id, int) or user_id <= 0:
            logger.warning(f"[JOB_SERVICE] Invalid user_id in list_user_jobs: {user_id}")
            return []
        
        if not isinstance(limit, int) or limit <= 0:
            logger.warning(f"[JOB_SERVICE] Invalid limit in list_user_jobs: {limit}, using default 20")
            limit = 20
        
        if limit > 100:  # Prevent excessive queries
            logger.warning(f"[JOB_SERVICE] Limit too high in list_user_jobs: {limit}, capping at 100")
            limit = 100
        
        try:
            async with self.pool.acquire() as conn:
                if status:
                    normalized_status = normalize_job_status(status)
                    rows = await conn.fetch("""
                        SELECT * FROM jobs
                        WHERE user_id = $1 AND status = $2
                        ORDER BY created_at DESC
                        LIMIT $3
                    """, user_id, normalized_status, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM jobs
                        WHERE user_id = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                    """, user_id, limit)
                
                return [dict(row) for row in rows]
        except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
            # Database connection errors
            logger.error(f"[JOB_SERVICE] Database connection error listing jobs for user {user_id}: {e}", exc_info=True)
            return []  # Fail-safe: return empty list on error
        except asyncpg.PostgresError as e:
            # Database query errors
            logger.error(f"[JOB_SERVICE] Database error listing jobs for user {user_id}: {e}", exc_info=True)
            return []  # Fail-safe: return empty list on error
        except Exception as e:
            # Unexpected errors
            logger.error(f"[JOB_SERVICE] Unexpected error listing jobs for user {user_id}: {e}", exc_info=True)
            return []  # Fail-safe: return empty list on error
    
    async def list_undelivered(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get jobs that are done but not delivered (for retry).
        
        Use case: Telegram API was down, retry delivery.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM jobs
                WHERE status = 'done'
                  AND delivered_at IS NULL
                  AND chat_id IS NOT NULL
                  AND finished_at IS NOT NULL
                ORDER BY finished_at ASC
                LIMIT $1
            """, limit)
            
            return [dict(row) for row in rows]


class InsufficientFundsError(Exception):
    """Raised when user doesn't have enough balance."""
    pass
