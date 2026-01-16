"""
Fast-ack webhook update queue with background workers.

This module provides instant HTTP responses to Telegram webhook calls
while processing updates asynchronously in background workers.

Key features:
- Instant 200 OK response (< 200ms target)
- Bounded queue to prevent memory overflow
- Multiple concurrent workers for throughput
- Graceful degradation (drop updates when overloaded, but still ack)
- Metrics for monitoring
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


def _is_allowed_in_passive(update) -> bool:
    """
    Проверяет, разрешен ли update в PASSIVE режиме.
    
    Разрешены:
    - /start команда
    - main_menu, back_to_menu callback
    - help, menu:* callback
    
    Запрещены:
    - Генерации (gen:*, flow:*, generate:*)
    - Платежи (pay:*, payment:*, topup:*)
    - Редактирование параметров (param:*, edit:*)
    - Любые другие опасные действия
    """
    # Команда /start всегда разрешена
    if hasattr(update, 'message') and update.message:
        msg = update.message
        if msg.text and msg.text.startswith('/start'):
            return True
    
    # Проверяем callback_query
    if hasattr(update, 'callback_query') and update.callback_query:
        data = update.callback_query.data or ""
        
        # Разрешенные префиксы/значения
        allowed = [
            'main_menu',
            'back_to_menu',
            'help',
            'menu:',
        ]
        
        for pattern in allowed:
            if data == pattern or data.startswith(pattern):
                return True
    
    # По умолчанию запрещаем
    return False


@dataclass
class QueueMetrics:
    """Metrics for monitoring queue health."""
    total_received: int = 0
    total_processed: int = 0
    total_dropped: int = 0
    total_errors: int = 0
    total_held: int = 0  # Held in PASSIVE mode
    total_requeued: int = 0  # Put back to queue
    total_processed_degraded: int = 0  # Processed despite PASSIVE (degraded mode)
    workers_active: int = 0
    queue_depth_current: int = 0
    last_drop_time: Optional[float] = None


@dataclass
class UpdateQueueManager:
    """
    Manages async queue for Telegram updates with background workers.
    
    Architecture:
    - Webhook handler calls enqueue() and immediately returns 200 OK
    - N worker tasks read from queue and call dp.feed_update()
    - If queue full: drop update, log warning, but still ack HTTP 200
    - Metrics exposed for /health endpoint
    """
    
    max_size: int = 100  # Max queued updates before dropping
    num_workers: int = 3  # Concurrent worker tasks
    
    _queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue())
    _workers: list = field(default_factory=list)
    _metrics: QueueMetrics = field(default_factory=QueueMetrics)
    _running: bool = False
    _dp = None  # Dispatcher instance
    _bot = None  # Bot instance
    _active_state = None  # Active state for lock checking
    
    def configure(self, dp, bot, active_state=None):
        """Configure dispatcher, bot, and active state."""
        self._dp = dp
        self._bot = bot
        self._active_state = active_state
        logger.info("[QUEUE] Configured with dp=%s bot=%s", 
                   type(dp).__name__, type(bot).__name__)
    
    def get_bot(self):
        """Get configured bot instance."""
        return self._bot
    
    async def start(self):
        """Start background workers."""
        if self._running:
            logger.warning("[QUEUE] Already running")
            return
        
        if not self._dp or not self._bot:
            raise RuntimeError("Must call configure() before start()")
        
        self._running = True
        self._queue = asyncio.Queue(maxsize=self.max_size)
        
        # Spawn worker tasks
        for i in range(self.num_workers):
            worker = asyncio.create_task(
                self._worker_loop(worker_id=i),
                name=f"update_worker_{i}"
            )
            self._workers.append(worker)
        
        logger.info("[QUEUE] Started %d workers (queue_max=%d)", 
                   self.num_workers, self.max_size)
    
    async def stop(self):
        """Stop workers gracefully."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        # Wait for cancellation
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        logger.info("[QUEUE] Stopped workers")
    
    def enqueue(self, update, update_id: int = 0) -> bool:
        """
        Enqueue update for background processing.
        
        BATCH 48.16: Added queue utilization monitoring and alerts.
        
        Returns:
            True if enqueued, False if dropped (queue full)
        
        This method is synchronous and returns immediately.
        Webhook handler should always return 200 OK regardless.
        """
        self._metrics.total_received += 1
        
        # Wrap update with metadata for PASSIVE handling
        item = {
            "update": update,
            "update_id": update_id,
            "attempt": 0,
            "first_seen": time.time(),
        }
        
        try:
            # Try to put without blocking
            self._queue.put_nowait(item)
            queue_size = self._queue.qsize()
            self._metrics.queue_depth_current = queue_size
            
            # BATCH 48.16: Alert if queue utilization > 80%
            utilization = (queue_size / self.max_size) * 100 if self.max_size > 0 else 0
            if utilization > 80:
                logger.warning(
                    "[QUEUE] ⚠️ HIGH UTILIZATION: queue_depth=%d/%d (%.1f%%) - "
                    "consider increasing max_size or workers",
                    queue_size, self.max_size, utilization
                )
            
            return True
        except asyncio.QueueFull:
            # Queue overloaded - drop update but log
            self._metrics.total_dropped += 1
            self._metrics.last_drop_time = time.time()
            logger.warning(
                "[QUEUE] DROPPED update_id=%s (queue full: %d/%d)",
                update_id, self._queue.qsize(), self.max_size
            )
            return False
    
    def should_reject_for_backpressure(self) -> bool:
        """
        Check if queue is under backpressure (utilization > 80%).
        
        BATCH 48.16: Added for monitoring and alerting.
        
        Returns:
            True if queue utilization > 80%
        """
        queue_size = self._queue.qsize()
        utilization = (queue_size / self.max_size) * 100 if self.max_size > 0 else 0
        return utilization > 80

    # P0 FIX #8: Removed _is_passive_allowed() - no longer needed after removing PASSIVE checks
    
    async def _worker_loop(self, worker_id: int):
        """Background worker that processes updates from queue."""
        import os
        import time
        
        logger.info("[WORKER_%d] Started", worker_id)
        
        last_passive_log = 0.0  # Rate-limit PASSIVE_WAIT logging
        active_enter_logged = False  # Track first ACTIVE enter
        
        while self._running:
            try:
                # Pull update from queue (with timeout to check active state regularly)
                item = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                # Extract item metadata
                update = item["update"]
                update_id = item["update_id"]
                
                # P0 FIX #8: REMOVED PASSIVE CHECK from workers (same as FIX #7 for webhook)
                # All workers process all updates - no more PASSIVE_REJECT
                # This fixes callback handlers that were being rejected
                logger.debug(
                    "[WORKER_%d] ✅ Processing update_id=%s",
                    worker_id, update_id
                )
                
                self._metrics.workers_active += 1
                self._metrics.queue_depth_current = self._queue.qsize()
                
                try:
                    # P0 FIX #8 (continued): Removed second PASSIVE check
                    # All updates are now processed immediately by all workers
                    
                    # ACTIVE: Log first entry (simplified - no PASSIVE concept)
                    if not active_enter_logged:
                        logger.info("[WORKER_%d] ✅ ACTIVE_ENTER active=True", worker_id)
                        active_enter_logged = True

                    # OBSERVABILITY V2: WORKER_PICK
                    from app.observability.v2 import log_worker_pick
                    from app.utils.correlation import get_correlation_id
                    cid = get_correlation_id() or "unknown"
                    log_worker_pick(cid=cid, update_id=update_id, worker_id=worker_id)
                    
                    # 🔐 STEP 1: Check persistent dedup BEFORE processing (FAIL-OPEN)
                    if update_id:
                        from app.storage.factory import get_storage
                        storage = get_storage()
                        
                        try:
                            # Check if already processed using storage method
                            if await storage.is_update_processed(update_id):
                                logger.warning(
                                    "[WORKER_%d] ⏭️ DEDUP_SKIP update_id=%s (already processed)",
                                    worker_id, update_id
                                )
                                self._metrics.total_dropped += 1
                                # Skip processing - task_done() in finally
                                continue
                            
                            # Mark as processing
                            await storage.mark_update_processed(
                                update_id,
                                worker_id=f"worker_{worker_id}",
                                update_type="message" if getattr(update, "message", None) else "callback_query"
                            )
                            logger.debug("[WORKER_%d] ✅ DEDUP_OK update_id=%s marked as processing", worker_id, update_id)
                            
                        except Exception as e:
                            # FAIL-OPEN: Log and continue processing without dedup
                            # This prevents worker deadlock when DB is unavailable
                            logger.warning(
                                "[WORKER_%d] ⚠️ DEDUP_FAIL_OPEN update_id=%s: %s - continuing without dedup",
                                worker_id, update_id, str(e)
                            )
                    
                    # STEP 2: Process update (feed to dispatcher)
                    # OBSERVABILITY V2: DISPATCH_START
                    from app.observability.v2 import log_dispatch_start
                    from app.utils.correlation import get_correlation_id
                    cid = get_correlation_id() or "unknown"
                    handler_name = None  # Will be determined by dispatcher
                    log_dispatch_start(cid=cid, update_id=update_id, handler_name=handler_name)
                    
                    # P0 FIX #8 (continued): Simplified metrics - no PASSIVE concept
                    self._metrics.total_processed += 1
                    
                    start_time = time.monotonic()
                    # P0 FIX: Increase timeout for long-running generations (30s → 120s)
                    await asyncio.wait_for(
                        self._dp.feed_update(self._bot, update),
                        timeout=120.0  # Allow up to 2 minutes for generation handlers
                    )
                    elapsed = time.monotonic() - start_time
                    duration_ms = elapsed * 1000
                    
                    # OBSERVABILITY V2: DISPATCH_OK
                    from app.observability.v2 import log_dispatch_ok
                    log_dispatch_ok(
                        cid=cid,
                        update_id=update_id,
                        handler_name=handler_name,
                        duration_ms=duration_ms,
                    )
                    
                    # Log to DB (best-effort, non-blocking)
                    try:
                        from app.observability.events_db import log_dispatch_ok
                        from app.telemetry.telemetry_helpers import get_event_ids
                        event_ids = get_event_ids(update, {})
                        await log_dispatch_ok(
                            cid=event_ids.get("cid", ""),
                            handler="update_queue_worker",
                            user_id=event_ids.get("user_id")
                        )
                    except Exception:
                        pass  # Swallow errors
                
                except asyncio.TimeoutError:
                    # OBSERVABILITY V2: DISPATCH_FAIL (timeout)
                    from app.observability.v2 import log_dispatch_fail
                    from app.utils.correlation import get_correlation_id
                    cid = get_correlation_id() or "unknown"
                    elapsed = time.monotonic() - start_time if 'start_time' in locals() else 0
                    log_dispatch_fail(
                        cid=cid,
                        update_id=update_id,
                        handler_name=handler_name,
                        error_type="TimeoutError",
                        safe_message="Handler execution timeout (120s exceeded)",
                        file_line=f"update_queue._worker_loop:worker_{worker_id}",
                        duration_ms=elapsed * 1000,
                        next_step="Check handler performance or increase timeout further",
                    )
                    self._metrics.total_errors += 1
                
                except Exception as exc:
                    # OBSERVABILITY V2: DISPATCH_FAIL (exception)
                    from app.observability.v2 import log_dispatch_fail
                    from app.utils.correlation import get_correlation_id
                    cid = get_correlation_id() or "unknown"
                    elapsed = time.monotonic() - start_time if 'start_time' in locals() else 0
                    error_type = type(exc).__name__
                    safe_message = str(exc)[:200]  # Truncate long messages
                    log_dispatch_fail(
                        cid=cid,
                        update_id=update_id,
                        handler_name=handler_name,
                        error_type=error_type,
                        safe_message=safe_message,
                        file_line=f"update_queue._worker_loop:worker_{worker_id}",
                        duration_ms=elapsed * 1000,
                        next_step="Check handler code and dependencies",
                    )
                    logger.exception(
                        "[WORKER_%d] Error processing update_id=%s: %s",
                        worker_id, update_id, exc
                    )
                    self._metrics.total_errors += 1
                    
                    # Log to DB (best-effort, non-blocking)
                    try:
                        from app.observability.events_db import log_dispatch_fail
                        from app.telemetry.telemetry_helpers import get_event_ids
                        event_ids = get_event_ids(update, {})
                        await log_dispatch_fail(
                            cid=event_ids.get("cid", ""),
                            handler="update_queue_worker",
                            error=exc,
                            user_id=event_ids.get("user_id")
                        )
                    except Exception:
                        pass  # Swallow errors
                
                finally:
                    self._metrics.workers_active -= 1
                    self._queue.task_done()
            
            except asyncio.TimeoutError:
                # No updates available, continue loop
                continue
            
            except asyncio.CancelledError:
                logger.info("[WORKER_%d] Cancelled", worker_id)
                break
            
            except Exception as exc:
                logger.exception("[WORKER_%d] Unexpected error: %s", worker_id, exc)
        
        logger.info("[WORKER_%d] Stopped", worker_id)
    
    def get_metrics(self) -> dict:
        """Get current metrics for /health endpoint."""
        queue_utilization = (self._metrics.queue_depth_current / max(self.max_size, 1)) * 100
        return {
            "total_received": self._metrics.total_received,
            "total_processed": self._metrics.total_processed,
            "total_processed_degraded": self._metrics.total_processed_degraded,
            "total_held": self._metrics.total_held,
            "total_requeued": self._metrics.total_requeued,
            "total_dropped": self._metrics.total_dropped,
            "total_errors": self._metrics.total_errors,
            "workers_active": self._metrics.workers_active,
            "queue_depth": self._metrics.queue_depth_current,
            "queue_max": self.max_size,
            "queue_utilization_percent": round(queue_utilization, 2),
            "drop_rate_percent": round(
                (self._metrics.total_dropped / max(self._metrics.total_received, 1)) * 100,
                2
            ),
            "last_drop_time": self._metrics.last_drop_time,
            "backpressure_active": queue_utilization > 80.0,
        }
    
    def should_reject_for_backpressure(self) -> bool:
        """
        Check if queue is under backpressure (should reject new updates).
        
        Returns:
            True if queue utilization > 80% (backpressure threshold)
        """
        queue_utilization = (self._metrics.queue_depth_current / max(self.max_size, 1)) * 100
        return queue_utilization > 80.0


# Global singleton
_queue_manager: Optional[UpdateQueueManager] = None


def get_queue_manager() -> UpdateQueueManager:
    """Get or create global queue manager."""
    global _queue_manager
    if _queue_manager is None:
        import os
        max_size = int(os.getenv("UPDATE_QUEUE_SIZE", "100"))
        num_workers = int(os.getenv("UPDATE_QUEUE_WORKERS", "3"))
        _queue_manager = UpdateQueueManager(max_size=max_size, num_workers=num_workers)
    return _queue_manager
