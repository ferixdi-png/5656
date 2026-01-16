"""
Lock contention tests - verify WAIT_THEN_PASSIVE behavior during Render deploy overlap
"""

import pytest
import time
import os
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_pool():
    """Mock PostgreSQL connection pool"""
    pool = MagicMock()
    
    # Track connections
    pool._connections = []
    
    def getconn():
        conn = MagicMock()
        pool._connections.append(conn)
        return conn
    
    def putconn(conn):
        if conn in pool._connections:
            pool._connections.remove(conn)
    
    pool.getconn = getconn
    pool.putconn = putconn
    
    return pool


@pytest.fixture
def held_lock(mock_pool):
    """Simulates lock already held by another instance"""
    # First connection acquires lock
    conn_a = mock_pool.getconn()
    cursor_a = MagicMock()
    cursor_a.fetchone.return_value = [True]  # Lock acquired
    conn_a.cursor.return_value.__enter__.return_value = cursor_a
    
    # Keep connection A alive (simulates old instance)
    return conn_a


def test_wait_then_passive_on_contention(mock_pool, held_lock):
    """
    Test that new instance enters PASSIVE mode when lock is held by old instance.
    Simulates Render deploy overlap.
    """
    from app.locking.single_instance import acquire_single_instance_lock
    
    # Mock environment
    with patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://test',
        'LOCK_MODE': 'wait_then_passive',
        'LOCK_WAIT_SECONDS': '2',  # Short wait for test
    }):
        # Mock database pool
        with patch('app.locking.single_instance.get_connection_pool', return_value=mock_pool):
            # New connection tries to acquire lock (should fail - already held)
            with patch('render_singleton_lock.acquire_lock_session') as mock_acquire:
                # Simulate lock already held (returns None)
                mock_acquire.return_value = None
                
                start = time.time()
                result = acquire_single_instance_lock()
                elapsed = time.time() - start
                
                # Should return False (PASSIVE mode)
                assert result is False, "Should enter PASSIVE mode when lock held"
                
                # Should have waited approximately LOCK_WAIT_SECONDS
                assert elapsed >= 1.5, f"Should wait ~2s, got {elapsed:.1f}s"
                
                # Should have made multiple attempts (exponential backoff)
                assert mock_acquire.call_count > 1, "Should retry with backoff"


def test_wait_then_force_on_contention(mock_pool, held_lock):
    """
    Test FORCE ACTIVE mode (risky - for single-instance Render only)
    """
    from app.locking.single_instance import acquire_single_instance_lock
    
    with patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://test',
        'LOCK_MODE': 'wait_then_force',
        'LOCK_WAIT_SECONDS': '1',
    }):
        with patch('app.locking.single_instance.get_connection_pool', return_value=mock_pool):
            with patch('render_singleton_lock.acquire_lock_session', return_value=None):
                result = acquire_single_instance_lock()
                
                # Should return True (FORCE ACTIVE despite no lock)
                assert result is True, "wait_then_force should return True"


def test_passive_to_active_transition(mock_pool):
    """
    Test that instance transitions from PASSIVE to ACTIVE when lock becomes available
    """
    from app.locking.single_instance import _acquire_postgres_lock, _is_active
    
    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test'}):
        with patch('app.locking.single_instance.get_connection_pool', return_value=mock_pool):
            # First attempt: lock not available
            with patch('render_singleton_lock.acquire_lock_session', return_value=None):
                lock1 = _acquire_postgres_lock()
                assert lock1 is None, "Lock should not be acquired"
            
            # Second attempt: lock becomes available (old instance released)
            mock_lock_data = {
                'connection': MagicMock(),
                'pool': mock_pool,
                'lock_key': 12345
            }
            with patch('render_singleton_lock.acquire_lock_session', return_value=mock_lock_data):
                lock2 = _acquire_postgres_lock()
                assert lock2 is not None, "Lock should be acquired on retry"
                assert lock2 == mock_lock_data


def test_no_stale_release_attempts():
    """
    Verify that dangerous _force_release_stale_lock() has been removed
    """
    import app.locking.single_instance as lock_module
    
    # Should NOT have this function anymore
    assert not hasattr(lock_module, '_force_release_stale_lock'), \
        "Stale release function should be removed (cannot unlock cross-session)"
    
    # Check source code for safety
    import inspect
    source = inspect.getsource(lock_module.acquire_single_instance_lock)
    assert '_force_release_stale_lock' not in source, \
        "acquire should not call stale release"


def test_exponential_backoff():
    """
    Verify exponential backoff is used during retry wait
    """
    from app.locking.single_instance import (
        LOCK_RETRY_BACKOFF_BASE,
        LOCK_RETRY_BACKOFF_MAX
    )
    
    # Config should exist
    assert LOCK_RETRY_BACKOFF_BASE == 0.5, "Base backoff should be 0.5s"
    assert LOCK_RETRY_BACKOFF_MAX == 5.0, "Max backoff should be 5s"


@pytest.mark.asyncio
async def test_background_retry_task():
    """
    Test background task that retries lock acquisition in PASSIVE mode
    """
    from app.locking.single_instance import start_background_lock_retry, _is_active
    
    # Should start background task when in passive mode
    with patch('app.locking.single_instance._is_active', False):
        with patch('app.locking.single_instance.asyncio.create_task') as mock_create:
            await start_background_lock_retry()
            
            # Should create background task
            assert mock_create.called, "Should create background retry task"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
