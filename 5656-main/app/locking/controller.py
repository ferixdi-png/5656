"""
Single-instance lock controller with state machine.
Ensures only ONE lock watcher and atomic PASSIVE/ACTIVE transitions.
"""
import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class LockState(Enum):
    """Lock acquisition state"""
    PASSIVE = "PASSIVE"
    ACTIVE = "ACTIVE"


@dataclass
class ControllerState:
    """Thread-safe state for lock controller"""
    state: LockState = LockState.PASSIVE
    lock_acquired_at: Optional[datetime] = None
    last_user_notice_at: Optional[datetime] = None
    watcher_task: Optional[asyncio.Task] = None
    instance_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    watcher_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    _mutex: asyncio.Lock = field(default_factory=asyncio.Lock)
    first_activation: bool = True  # Track if this is first PASSIVE→ACTIVE


class SingletonLockController:
    """
    Unified lock controller with single watcher and atomic state transitions.
    
    Features:
    - Single background watcher task (no duplicates)
    - Atomic PASSIVE → ACTIVE transitions
    - Throttled user notifications (max 1 per 60s)
    - Auto-stops retry loop after ACTIVE
    - Callback on PASSIVE→ACTIVE transition
    """
    
    def __init__(self, lock_wrapper, bot=None, on_active_callback=None, active_state=None):
        """
        Args:
            lock_wrapper: SingletonLock instance with acquire()/release()
            bot: Telegram Bot instance for passive notifications
            on_active_callback: async callable to run when transitioning to ACTIVE
            active_state: ActiveState instance for synchronization with workers
        """
        self.lock = lock_wrapper
        self.bot = bot
        self.on_active_callback = on_active_callback
        self.active_state = active_state  # NEW: unified state sync
        self.state = ControllerState()
        self._stop_event = asyncio.Event()
        
        logger.info(
            "[LOCK_CONTROLLER] Initialized | instance=%s watcher=%s active_state=%s",
            self.state.instance_id,
            self.state.watcher_id,
            active_state
        )
    
    def should_process_updates(self) -> bool:
        """Check if instance should process Telegram updates"""
        return self.state.state == LockState.ACTIVE
    
    async def _set_state(self, new_state: LockState) -> None:
        """Atomic state transition (thread-safe) + sync active_state"""
        logger.info(f"[LOCK_CONTROLLER] 🔧 _set_state called: new_state={new_state.value}")
        try:
            logger.info(f"[LOCK_CONTROLLER] 🔒 Acquiring mutex for state transition...")
            async with self.state._mutex:
                logger.info(f"[LOCK_CONTROLLER] 🔓 Mutex acquired, proceeding with transition")
                old_state = self.state.state
                logger.info(f"[LOCK_CONTROLLER] 🔍 State transition: {old_state.value} → {new_state.value}")
                self.state.state = new_state
                
                # CRITICAL: Sync active_state for workers
                if self.active_state:
                    logger.info(f"[LOCK_CONTROLLER] 🔄 Syncing active_state (current: {self.active_state.active})")
                    if new_state == LockState.ACTIVE:
                        self.active_state.set(True, reason="lock_acquired")
                        logger.info(f"[LOCK_CONTROLLER] ✅ active_state synced: {self.active_state.active}")
                    elif new_state == LockState.PASSIVE:
                        self.active_state.set(False, reason="lock_lost")
                        logger.info(f"[LOCK_CONTROLLER] ⏸️ active_state synced: {self.active_state.active}")
                else:
                    logger.error("[LOCK_CONTROLLER] ❌ active_state is None! Cannot sync!")
                
                if new_state == LockState.ACTIVE:
                    logger.info("[LOCK_CONTROLLER] ✅ Setting ACTIVE state...")
                    self.state.lock_acquired_at = datetime.now()
                    logger.info(f"[LOCK_CONTROLLER] 🔍 Checking callback: old_state={old_state.value}, has_callback={self.on_active_callback is not None}, first_activation={self.state.first_activation}")
                    
                    # Call callback on FIRST activation OR when transitioning from PASSIVE
                    should_call_callback = (
                        (old_state == LockState.PASSIVE or self.state.first_activation)
                        and self.on_active_callback is not None
                    )
                    
                    if should_call_callback:
                        logger.info(
                            "[LOCK_CONTROLLER] %s → %s | instance=%s held_since=%s",
                            old_state.value,
                            new_state.value,
                            self.state.instance_id,
                            self.state.lock_acquired_at.isoformat()
                        )
                        # CRITICAL: Call on_active_callback when transitioning to ACTIVE
                        try:
                            logger.info("[LOCK_CONTROLLER] 🔥 Calling on_active_callback...")
                            await self.on_active_callback()
                            logger.info("[LOCK_CONTROLLER] ✅ on_active_callback completed")
                            self.state.first_activation = False  # Mark as activated
                        except Exception as e:
                            logger.exception("[LOCK_CONTROLLER] ❌ on_active_callback failed: %s", e)
                    else:
                        if self.on_active_callback is None:
                            logger.warning("[LOCK_CONTROLLER] ⚠️ on_active_callback is None!")
                        else:
                            logger.info(f"[LOCK_CONTROLLER] ℹ️ Callback skipped: old_state={old_state.value}, first_activation={self.state.first_activation}")
                
                if new_state == LockState.PASSIVE:
                    self.state.lock_acquired_at = None
                    if old_state == LockState.ACTIVE:
                        logger.warning(
                            "[LOCK_CONTROLLER] %s → %s (lock lost) | instance=%s",
                            old_state.value,
                            new_state.value,
                            self.state.instance_id
                        )
        except Exception as e:
            logger.exception(f"[LOCK_CONTROLLER] ❌❌ _set_state EXCEPTION: {e}")
            raise
    
    async def _should_send_passive_notice(self, chat_id: int) -> bool:
        """Check if we should send 'updating' message (throttled)"""
        if self.state.state == LockState.ACTIVE:
            return False  # Never send in ACTIVE mode
        
        async with self.state._mutex:
            now = datetime.now()
            if self.state.last_user_notice_at is None:
                self.state.last_user_notice_at = now
                return True
            
            # Throttle: max 1 per 60 seconds
            time_since_last = now - self.state.last_user_notice_at
            if time_since_last > timedelta(seconds=60):
                self.state.last_user_notice_at = now
                return True
            
            return False
    
    async def send_passive_notice_if_needed(self, chat_id: int) -> bool:
        """
        Send 'updating' message if in PASSIVE and throttle allows.
        
        Returns:
            True if message sent, False otherwise
        """
        if not self.bot or not await self._should_send_passive_notice(chat_id):
            return False
        
        try:
            await self.bot.send_message(
                chat_id,
                "🔄 Бот обновляется, попробуйте через минуту"
            )
            logger.info(
                "[LOCK_CONTROLLER] Sent throttled passive notice | chat=%s instance=%s",
                chat_id,
                self.state.instance_id
            )
            return True
        except Exception as e:
            logger.warning(
                "[LOCK_CONTROLLER] Failed to send passive notice | chat=%s error=%s",
                chat_id,
                e
            )
            return False
    
    async def _watcher_loop(self):
        """Background watcher: attempt lock acquisition with exponential backoff"""
        logger.info(
            "[LOCK_CONTROLLER] Watcher started | watcher=%s instance=%s",
            self.state.watcher_id,
            self.state.instance_id
        )
        
        attempt = 0
        base_interval = 10  # Start with 10s
        max_interval = 60   # Cap at 60s
        
        while not self._stop_event.is_set():
            attempt += 1
            
            try:
                # Fast non-blocking acquire attempt (0.5s timeout)
                got_lock = await self.lock.acquire(timeout=0.5)
                
                if got_lock:
                    await self._set_state(LockState.ACTIVE)
                    logger.info(
                        "[LOCK_CONTROLLER] ✅ Lock acquired | attempt=%d instance=%s",
                        attempt,
                        self.state.instance_id
                    )
                    # Stop watcher - we're ACTIVE now
                    break
                else:
                    # Still PASSIVE
                    if attempt == 1:
                        logger.info(
                            "[LOCK_CONTROLLER] Lock not available (another instance active) | instance=%s",
                            self.state.instance_id
                        )
            except Exception as e:
                logger.exception(
                    "[LOCK_CONTROLLER] Watcher error | attempt=%d error=%s",
                    attempt,
                    e
                )
            
            # Exponential backoff
            wait_time = min(base_interval * (1.5 ** (attempt - 1)), max_interval)
            logger.debug(
                "[LOCK_CONTROLLER] Retry in %.1fs | attempt=%d instance=%s",
                wait_time,
                attempt,
                self.state.instance_id
            )
            
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=wait_time
                )
                break  # Stop event set
            except asyncio.TimeoutError:
                continue  # Retry
        
        logger.info(
            "[LOCK_CONTROLLER] Watcher stopped | watcher=%s instance=%s state=%s",
            self.state.watcher_id,
            self.state.instance_id,
            self.state.state.value
        )
    
    async def start(self) -> None:
        """Start lock controller (single watcher task)"""
        # Check if already running (without holding mutex during lock acquire)
        if self.state.watcher_task is not None:
            logger.warning(
                "[LOCK_CONTROLLER] Watcher already running | watcher=%s",
                self.state.watcher_id
            )
            return
        
        # Try immediate acquire first (fast path) - DON'T hold mutex during this
        logger.info("[LOCK_CONTROLLER] 🔍 Attempting immediate acquire (timeout=0.5s)...")
        try:
            got_lock = await self.lock.acquire(timeout=0.5)
            logger.info(f"[LOCK_CONTROLLER] Immediate acquire returned: {got_lock}")
            if got_lock:
                # SUCCESS: Call _set_state (which has its own mutex)
                await self._set_state(LockState.ACTIVE)
                logger.info(
                    "[LOCK_CONTROLLER] ✅ Lock acquired immediately | instance=%s",
                    self.state.instance_id
                )
                return  # No need for watcher
            else:
                logger.warning("[LOCK_CONTROLLER] ⏸️ Immediate acquire FAILED - lock held by another instance")
        except Exception as e:
            logger.debug(
                "[LOCK_CONTROLLER] Immediate acquire failed: %s | instance=%s",
                e,
                self.state.instance_id
            )
        
        # Start background watcher
        await self._set_state(LockState.PASSIVE)
        async with self.state._mutex:
            self.state.watcher_task = asyncio.create_task(self._watcher_loop())
            logger.info(
                "[LOCK_CONTROLLER] Started background watcher | watcher=%s instance=%s",
                self.state.watcher_id,
                self.state.instance_id
            )
    
    async def stop(self) -> None:
        """Stop lock controller and release lock"""
        self._stop_event.set()
        
        async with self.state._mutex:
            if self.state.watcher_task is not None:
                self.state.watcher_task.cancel()
                try:
                    await self.state.watcher_task
                except asyncio.CancelledError:
                    pass
                self.state.watcher_task = None
        
        if self.state.state == LockState.ACTIVE:
            try:
                await self.lock.release()
                logger.info(
                    "[LOCK_CONTROLLER] Lock released | instance=%s",
                    self.state.instance_id
                )
            except Exception as e:
                logger.warning(
                    "[LOCK_CONTROLLER] Failed to release lock: %s",
                    e
                )
        
        await self._set_state(LockState.PASSIVE)
        logger.info(
            "[LOCK_CONTROLLER] Stopped | instance=%s",
            self.state.instance_id
        )
