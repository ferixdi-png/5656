"""
Generation Service V2 - Atomic job creation with KIE integration

CRITICAL LIFECYCLE (following felores/kie-ai-mcp-server):
1. Validate user exists
2. Create job in DB (status='pending') ← BEFORE KIE API call
3. Call KIE API to create task
4. Update job with task_id (status='running')
5. Wait for callback or poll
6. Update job from callback (status='done/failed')
7. Release/charge balance atomically
8. Deliver result to Telegram

INVARIANTS:
- Job ALWAYS created before KIE task (prevents orphan callbacks)
- Balance operations atomic with job lifecycle
- Idempotent (duplicate requests return existing job)
- Never lose callbacks (orphan reconciliation as fallback)
- Guarantee Telegram delivery (retry logic)
"""

import logging
import uuid
from typing import Dict, Any, Optional
from decimal import Decimal

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

from app.services.job_service_v2 import JobServiceV2, InsufficientFundsError
from app.integrations.strict_kie_client import StrictKIEClient, KIEError

logger = logging.getLogger(__name__)


class GenerationServiceV2:
    """
    Production-ready generation service with atomic operations.
    
    Usage:
        service = GenerationServiceV2(db_pool, kie_client, callback_base_url)
        
        job = await service.create_generation(
            user_id=12345,
            model_id='wan/2-5-standard-text-to-video',
            category='video',
            input_params={'prompt': 'test', 'duration': 5},
            price_rub=Decimal('0.00'),  # FREE model
            chat_id=12345
        )
        
        # Job created atomically:
        # - job.id exists in DB
        # - job.kie_task_id set
        # - callback will update job when done
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        kie_client: StrictKIEClient,
        callback_base_url: str
    ):
        self.job_service = JobServiceV2(db_pool)
        self.kie_client = kie_client
        self.callback_base_url = callback_base_url.rstrip('/')
    
    async def create_generation(
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
        Create generation task atomically.
        
        Returns:
            Job dict with 'id', 'kie_task_id', 'status', etc.
        
        Raises:
            ValueError: Invalid input
            InsufficientFundsError: Not enough balance
            KIEError: KIE API error
        """
        if not idempotency_key:
            idempotency_key = f"gen:{user_id}:{uuid.uuid4()}"
        
        # PHASE 1: Create job in DB FIRST (status='pending')
        # This ensures job exists BEFORE callback can arrive
        logger.info(
            f"[GEN_CREATE] user={user_id} model={model_id} price={price_rub} "
            f"key={idempotency_key[:20]}..."
        )
        
        job = await self.job_service.create_job_atomic(
            user_id=user_id,
            model_id=model_id,
            category=category,
            input_params=input_params,
            price_rub=price_rub,
            chat_id=chat_id,
            idempotency_key=idempotency_key
        )
        
        job_id = job['id']
        
        # PHASE 2: Create KIE task
        callback_url = f"{self.callback_base_url}/api/kie-callback?job_id={job_id}"
        
        try:
            task_id = await self.kie_client.create_task(
                model_id=model_id,
                input_params=input_params,
                callback_url=callback_url
            )
        except KIEError as e:
            # KIE API failed - mark job as failed and release balance
            logger.error(f"[GEN_ERROR] job={job_id} KIE API error: {e}")
            
            await self.job_service.update_from_callback(
                job_id=job_id,
                status='failed',
                error_text=f"KIE API error: {str(e)}"
            )
            
            raise
        
        # PHASE 3: Update job with task_id (status='running')
        await self.job_service.update_with_kie_task(
            job_id=job_id,
            kie_task_id=task_id,
            status='running'
        )
        
        logger.info(
            f"[GEN_SUCCESS] job={job_id} task={task_id} model={model_id} "
            f"status=running callback={callback_url}"
        )
        
        # Refresh job to get updated state
        job = await self.job_service.get_by_id(job_id)
        return job
    
    async def handle_callback(
        self,
        task_id: str,
        state: str,
        result_json: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Handle KIE callback.
        
        Lifecycle: running → done/failed
        
        Returns:
            True if callback processed successfully
            False if job not found (orphan callback)
        """
        logger.info(f"[CALLBACK] task={task_id} state={state}")
        
        # Find job by task_id
        job = await self.job_service.get_by_task_id(task_id)
        
        if not job:
            logger.warning(
                f"[CALLBACK_ORPHAN] task={task_id} - job not found, "
                f"will be reconciled later"
            )
            return False
        
        job_id = job['id']
        
        # Parse result_json (with improved error handling)
        result_data = None
        if result_json:
            import json
            try:
                # Handle both string and dict inputs
                if isinstance(result_json, str):
                    result_data = json.loads(result_json)
                elif isinstance(result_json, dict):
                    result_data = result_json
                else:
                    logger.warning(f"[CALLBACK] Unexpected resultJson type: {type(result_json)}")
                    result_data = {'raw': str(result_json)}
            except json.JSONDecodeError as e:
                logger.warning(f"[CALLBACK] JSON decode error for resultJson: {e} (first 200 chars: {str(result_json)[:200]})")
                result_data = {'raw': str(result_json), 'parse_error': str(e)}
            except Exception as e:
                logger.warning(f"[CALLBACK] Unexpected error parsing resultJson: {e} (type: {type(result_json)})")
                result_data = {'raw': str(result_json), 'error': str(e)}
        
        # Update job status
        await self.job_service.update_from_callback(
            job_id=job_id,
            status='done' if state == 'success' else 'failed',
            result_json=result_data,
            error_text=error_message,
            kie_status=state
        )
        
        logger.info(
            f"[CALLBACK_SUCCESS] job={job_id} task={task_id} state={state} "
            f"results={len(result_data.get('resultUrls', [])) if result_data else 0}"
        )
        
        return True
    
    async def deliver_to_telegram(
        self,
        job_id: int,
        bot,  # aiogram.Bot instance
        max_retries: int = 3
    ) -> bool:
        """
        Deliver job result to Telegram with retry.
        
        Returns:
            True if delivered successfully
            False if delivery failed (will retry later)
        """
        job = await self.job_service.get_by_id(job_id)
        if not job:
            logger.error(f"[TELEGRAM] Job {job_id} not found")
            return False
        
        chat_id = job.get('chat_id')
        if not chat_id:
            logger.warning(f"[TELEGRAM] Job {job_id} has no chat_id, cannot deliver")
            return False
        
        if job['delivered_at']:
            logger.info(f"[TELEGRAM] Job {job_id} already delivered")
            return True
        
        result_json = job.get('result_json', {})
        result_urls = result_json.get('resultUrls', []) if result_json else []
        
        if not result_urls:
            logger.warning(f"[TELEGRAM] Job {job_id} has no results to deliver")
            return False
        
        # Retry delivery
        from aiogram.exceptions import TelegramAPIError
        
        for attempt in range(max_retries):
            try:
                # Send result (placeholder - customize based on content type)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Генерация готова!\n\n{result_urls[0]}"
                )
                
                # Mark as delivered
                await self.job_service.mark_delivered(job_id)
                
                logger.info(f"[TELEGRAM_SUCCESS] job={job_id} chat={chat_id} delivered=True")
                return True
            
            except TelegramAPIError as e:
                logger.warning(
                    f"[TELEGRAM_RETRY] job={job_id} attempt={attempt+1}/{max_retries} "
                    f"error={e}"
                )
                
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"[TELEGRAM_FAILED] job={job_id} delivery failed after {max_retries} attempts")
        return False
    
    async def get_user_history(
        self,
        user_id: int,
        limit: int = 20
    ) -> list[Dict[str, Any]]:
        """Get user's generation history."""
        return await self.job_service.list_user_jobs(user_id, limit=limit)
    
    async def retry_undelivered(self, bot, limit: int = 100) -> int:
        """
        Retry delivery for all undelivered jobs.
        
        Returns:
            Number of jobs delivered
        """
        jobs = await self.job_service.list_undelivered(limit=limit)
        
        if not jobs:
            return 0
        
        logger.info(f"[TELEGRAM_RETRY_ALL] Found {len(jobs)} undelivered jobs")
        
        delivered = 0
        for job in jobs:
            success = await self.deliver_to_telegram(job['id'], bot)
            if success:
                delivered += 1
        
        logger.info(f"[TELEGRAM_RETRY_ALL] Delivered {delivered}/{len(jobs)} jobs")
        return delivered
