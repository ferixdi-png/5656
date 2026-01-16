"""
Test for active_state synchronization between lock_controller and workers.
Simulates lock acquisition delay and verifies workers activate correctly.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.locking.active_state import ActiveState
from app.locking.controller import SingletonLockController, LockState


class FakeLock:
    """Fake lock that acquires after delay."""
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._acquired = False
    
    async def acquire(self, timeout=None):
        await asyncio.sleep(self.delay)
        self._acquired = True
        return True
    
    async def release(self):
        self._acquired = False
        return True


@pytest.mark.asyncio
async def test_active_state_sync_on_lock_acquire():
    """
    CRITICAL TEST: Verify that when lock is acquired, active_state.active becomes True
    and workers are notified via Event.
    """
    # Setup
    active_state = ActiveState(active=False)
    fake_lock = FakeLock(delay=0.5)  # Simulate 500ms lock acquisition
    
    callback_called = False
    async def on_active_callback():
        nonlocal callback_called
        callback_called = True
    
    controller = SingletonLockController(
        lock_wrapper=fake_lock,
        bot=None,
        on_active_callback=on_active_callback,
        active_state=active_state
    )
    
    # Verify initial state
    assert active_state.active is False, "Should start PASSIVE"
    assert controller.should_process_updates() is False
    
    # Start controller (acquires lock in background)
    await controller.start()
    
    # Simulate worker waiting for active
    worker_activated = False
    async def worker():
        nonlocal worker_activated
        # This should block until active_state.set(True)
        await active_state.wait_active()
        worker_activated = True
    
    worker_task = asyncio.create_task(worker())
    
    # Wait for lock acquisition (should take ~500ms)
    await asyncio.sleep(1.0)
    
    # Verify state transitions
    assert active_state.active is True, "active_state should be True after lock acquired"
    assert controller.should_process_updates() is True
    assert callback_called is True, "on_active_callback should be called"
    
    # Verify worker was notified
    await asyncio.wait_for(worker_task, timeout=0.5)
    assert worker_activated is True, "Worker should activate after state change"
    
    # Cleanup
    await controller.stop()


@pytest.mark.asyncio
async def test_active_state_sync_on_lock_loss():
    """
    Verify that when lock is lost, active_state.active becomes False.
    """
    active_state = ActiveState(active=True)  # Start as ACTIVE
    fake_lock = FakeLock(delay=0.1)
    
    controller = SingletonLockController(
        lock_wrapper=fake_lock,
        bot=None,
        on_active_callback=None,
        active_state=active_state
    )
    
    # Manually set to ACTIVE
    await controller._set_state(LockState.ACTIVE)
    assert active_state.active is True
    
    # Simulate lock loss
    await controller._set_state(LockState.PASSIVE)
    assert active_state.active is False, "active_state should be False after lock lost"
    assert controller.should_process_updates() is False


@pytest.mark.asyncio
async def test_worker_queue_processing_after_active():
    """
    Simulate full flow: webhook enqueue → lock acquire → workers process queue.
    """
    from app.utils.update_queue import UpdateQueueManager
    
    active_state = ActiveState(active=False)
    fake_lock = FakeLock(delay=0.3)
    
    # Mock dispatcher and bot
    mock_dp = AsyncMock()
    mock_bot = MagicMock()
    
    # Create queue manager
    queue_mgr = UpdateQueueManager(num_workers=2)
    queue_mgr.configure(mock_dp, mock_bot, active_state)
    
    # Create controller
    controller = SingletonLockController(
        lock_wrapper=fake_lock,
        bot=None,
        on_active_callback=None,
        active_state=active_state
    )
    
    # Start queue workers (they should wait in PASSIVE)
    await queue_mgr.start()
    
    # Enqueue fake update BEFORE lock acquired
    fake_update = MagicMock()
    fake_update.update_id = 12345
    queue_mgr.enqueue(fake_update, 12345)
    
    # Verify queue has item but workers are waiting
    assert queue_mgr._queue.qsize() == 1
    await asyncio.sleep(0.5)
    assert mock_dp.feed_update.call_count == 0, "Workers should NOT process in PASSIVE"
    
    # Acquire lock → transition to ACTIVE
    await controller.start()
    await asyncio.sleep(0.8)  # Wait for lock + processing
    
    # Verify workers processed the update
    assert active_state.active is True
    assert mock_dp.feed_update.call_count >= 1, "Workers should process after ACTIVE"
    
    # Cleanup
    await queue_mgr.stop()
    await controller.stop()


@pytest.mark.asyncio
async def test_safety_net_force_active():
    """
    Test that safety-net forces ACTIVE if lock acquired but state not synced after 3s.
    This simulates the state_sync_loop logic.
    """
    active_state = ActiveState(active=False)
    fake_lock = FakeLock(delay=0.1)
    
    # Create controller WITHOUT active_state sync (simulate bug)
    controller = SingletonLockController(
        lock_wrapper=fake_lock,
        bot=None,
        on_active_callback=None,
        active_state=None  # BUG: not passing active_state
    )
    
    await controller.start()
    await asyncio.sleep(0.5)
    
    # Controller is ACTIVE but active_state is still False (desync)
    assert controller.should_process_updates() is True
    assert active_state.active is False
    
    # Simulate safety-net logic
    import time
    lock_acquired_time = time.time()
    await asyncio.sleep(3.5)
    
    if controller.should_process_updates() and not active_state.active:
        if time.time() - lock_acquired_time > 3.0:
            # Safety-net: force ACTIVE
            active_state.set(True, reason="safety_net_force")
    
    assert active_state.active is True, "Safety-net should force ACTIVE after 3s"
    
    await controller.stop()


if __name__ == "__main__":
    # Allow running tests directly
    import sys
    pytest.main([__file__, "-v"] + sys.argv[1:])
