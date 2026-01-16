"""
Orphan Callback Reconciler
===========================

Background task that processes orphan callbacks - callbacks that arrived
before the job record was created in the database (race condition).

Flow:
1. Periodically check orphan_callbacks table for unprocessed entries
2. For each orphan, try to find matching job by task_id
3. If job found: update status, send result, mark orphan as processed
4. If job not found after timeout: mark as error

This ensures no results are lost even with race conditions.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class OrphanCallbackReconciler:
    """Background reconciler for orphan callbacks"""
    
    def __init__(self, storage, bot, check_interval: int = 10, max_age_minutes: int = 30):
        """
        Initialize reconciler
        
        Args:
            storage: Storage instance (must have orphan callback methods)
            bot: Telegram bot instance for sending results
            check_interval: How often to check for orphans (seconds)
            max_age_minutes: Max age before giving up on orphan (minutes)
        """
        self.storage = storage
        self.bot = bot
        self.check_interval = check_interval
        self.max_age_minutes = max_age_minutes
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start background reconciliation loop"""
        if self._running:
            logger.warning("[RECONCILER] Already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._reconciliation_loop())
        logger.info(f"[RECONCILER] Started (interval={self.check_interval}s, max_age={self.max_age_minutes}min)")
    
    async def stop(self):
        """Stop background reconciliation"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[RECONCILER] Stopped")
    
    async def _reconciliation_loop(self):
        """Main reconciliation loop"""
        while self._running:
            try:
                await self._process_orphans()
            except Exception as e:
                logger.exception(f"[RECONCILER] Error in reconciliation: {e}")
            
            # Wait before next check
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
    
    async def _process_orphans(self):
        """Process all unprocessed orphan callbacks"""
        # Get unprocessed orphans
        try:
            orphans = await self.storage._get_unprocessed_orphans(limit=100)
        except AttributeError:
            # Storage doesn't support orphan callbacks (e.g., JSON mode)
            return
        except Exception as e:
            logger.error(f"[RECONCILER] Failed to get orphans: {e}")
            return
        
        if not orphans:
            return
        
        logger.info(f"[RECONCILER] Processing {len(orphans)} orphan callback(s)")
        
        for orphan in orphans:
            try:
                await self._process_single_orphan(orphan)
            except Exception as e:
                logger.exception(f"[RECONCILER] Failed to process orphan {orphan.get('task_id')}: {e}")
    
    async def _process_single_orphan(self, orphan: dict):
        """Process a single orphan callback"""
        task_id = orphan['task_id']
        payload = orphan['payload']
        received_at = orphan['received_at']
        
        # Parse payload (it's stored as JSONB or JSON string)
        if isinstance(payload, str):
            import json
            payload = json.loads(payload)
        
        # Check if job exists now
        job = None
        try:
            job = await self.storage.find_job_by_task_id(task_id)
        except Exception as e:
            logger.warning(f"[RECONCILER] Failed to find job for task_id={task_id}: {e}")
        
        if job:
            # Job found! Process the orphan callback
            logger.info(f"[RECONCILER] ✅ Job found for orphan task_id={task_id}, updating status")
            
            # Extract data from orphan payload
            state = payload.get('state') or payload.get('normalized_status') or 'running'
            result_urls = payload.get('result_urls') or []
            error_text = payload.get('error_text')
            
            # Update job status
            job_id = job.get('job_id') or job.get('id') or task_id
            try:
                await self.storage.update_job_status(
                    job_id,
                    state,
                    result_urls=result_urls or None,
                    error_message=error_text
                )
                logger.info(f"[RECONCILER] Updated job {job_id} status={state}")
            except Exception as e:
                logger.exception(f"[RECONCILER] Failed to update job {job_id}: {e}")
                await self.storage._mark_orphan_processed(task_id, error=str(e))
                return
            
            # Send result to Telegram
            user_id = job.get('user_id')
            chat_id = user_id  # Default
            if job.get('params'):
                import json as json_module
                job_params = job.get('params')
                if isinstance(job_params, dict):
                    chat_id = job_params.get('chat_id') or user_id
                elif isinstance(job_params, str):
                    try:
                        params_dict = json_module.loads(job_params)
                        chat_id = params_dict.get('chat_id') or user_id
                    except Exception:
                        pass
            
            if user_id and chat_id and state == 'done' and result_urls:
                try:
                    # Import datetime
                    from datetime import datetime as dt_class
                    # Send result
                    text = f"✅ Генерация готова (восстановлено)\nID: {task_id}\n\n" + "\n".join(result_urls[:5])
                    await self.bot.send_message(chat_id, text)
                    logger.info(f"[RECONCILER] ✅ Sent result to chat_id={chat_id} (orphan reconciled)")
                except Exception as e:
                    logger.exception(f"[RECONCILER] Failed to send to chat {chat_id}: {e}")
            
            # Mark orphan as processed
            await self.storage._mark_orphan_processed(task_id)
            logger.info(f"[RECONCILER] Marked orphan task_id={task_id} as processed")
        
        else:
            # Job still not found - check age
            from datetime import datetime, timezone
            
            # Normalize received_at to timezone-aware UTC
            if received_at.tzinfo is None:
                # Naive datetime - assume UTC
                received_at = received_at.replace(tzinfo=timezone.utc)
            
            # Calculate age using timezone-aware now
            now = datetime.now(timezone.utc)
            age = now - received_at
            if age.total_seconds() > self.max_age_minutes * 60:
                # Too old - give up
                error_msg = f"Orphan timeout: no job found after {self.max_age_minutes} minutes"
                await self.storage._mark_orphan_processed(task_id, error=error_msg)
                logger.warning(f"[RECONCILER] ⏰ Orphan task_id={task_id} timed out, marked as error")
            else:
                # Still within timeout - wait for next iteration
                logger.debug(f"[RECONCILER] Orphan task_id={task_id} waiting (age={age.total_seconds():.0f}s)")
