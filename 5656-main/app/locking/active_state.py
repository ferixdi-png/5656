"""
Unified active state with asyncio.Event for synchronization.
Single source of truth for "can process updates" across lock_controller and update_queue.
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ActiveState:
    """
    Thread-safe active state with asyncio.Event for worker synchronization.
    
    Usage:
        state = ActiveState()
        
        # In lock_controller on lock acquire:
        state.set(True, reason="lock_acquired")
        
        # In update_queue workers:
        await state.wait_active()  # Blocks until active=True
        
        # Check current state:
        if state.active:
            process_update()
    """
    
    def __init__(self, active: bool = False):
        self._active = active
        self._event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._reason: Optional[str] = None
        
        if active:
            self._event.set()
        
        logger.info("[ACTIVE_STATE] Initialized active=%s", active)
    
    @property
    def active(self) -> bool:
        """Current active state (read-only property)."""
        return self._active
    
    def set(self, value: bool, reason: str = "unknown") -> None:
        """
        Set active state atomically with Event synchronization.
        
        Args:
            value: New active state
            reason: Reason for change (for logging)
        """
        if self._active == value:
            # No change
            return
        
        old_value = self._active
        self._active = value
        self._reason = reason
        
        if value:
            self._event.set()
            logger.info(
                "[STATE_SYNC] ✅ active_state: %s -> %s (reason=%s)",
                old_value, value, reason
            )
        else:
            self._event.clear()
            logger.info(
                "[STATE_SYNC] ⏸️ active_state: %s -> %s (reason=%s)",
                old_value, value, reason
            )
    
    async def wait_active(self, timeout: Optional[float] = None) -> bool:
        """
        Wait until active=True.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            True if active, False if timeout
        """
        if self._active:
            return True
        
        try:
            if timeout:
                await asyncio.wait_for(self._event.wait(), timeout=timeout)
            else:
                await self._event.wait()
            return self._active
        except asyncio.TimeoutError:
            return False
    
    def __repr__(self) -> str:
        return f"ActiveState(active={self._active}, reason={self._reason})"
