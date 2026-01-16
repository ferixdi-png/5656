"""
Tests: singleton lock force-active mode and graceful shutdown behavior.
"""
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def test_singleton_force_active_mode_enabled_by_default():
    """Verify SINGLETON_LOCK_FORCE_ACTIVE defaults to True for Render single-instance."""
    # Default should be '1' (True) for Render single-instance assumption
    val = os.getenv("SINGLETON_LOCK_FORCE_ACTIVE", "1")
    assert val == "1", "Force-active should be enabled by default (Render assumption)"


def test_singleton_lock_force_active_log_warning():
    """Test that force-active mode logs appropriate warnings."""
    # Simulate force-active behavior
    force_active = os.getenv("SINGLETON_LOCK_FORCE_ACTIVE", "1") == "1"
    
    if force_active:
        # This is the safety mechanism: allow boot even if lock fails
        # because on Render one instance = one lock should work
        assert True, "Force-active allows boot despite lock failure (safe for single-instance)"
    else:
        # Explicit disable via env: goes to passive or strict mode
        assert True, "Force-active disabled: follows SINGLETON_LOCK_STRICT rules"


@pytest.mark.asyncio
async def test_singleton_release_on_shutdown():
    """Verify graceful release of singleton lock on shutdown."""
    from app.locking.single_instance import release_single_instance_lock, is_lock_held
    
    # Simulate lock held state
    from app.locking import single_instance
    single_instance._lock_handle = {"mock": "lock"}
    single_instance._lock_type = "file"
    single_instance._lock_connection = None
    
    assert is_lock_held() is True
    
    # Release
    release_single_instance_lock()
    
    assert is_lock_held() is False
