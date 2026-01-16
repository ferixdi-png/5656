"""
Unit tests for observability events DB logging.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from app.observability.events_db import (
    log_event,
    log_update_received,
    log_callback_received,
    log_dispatch_ok,
    log_dispatch_fail,
    log_passive_reject,
    init_events_db,
)


class TestObservabilityEvents(unittest.TestCase):
    """Unit tests for observability events."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_pool = AsyncMock()
        self.mock_conn = AsyncMock()
        self.mock_pool.acquire.return_value.__aenter__.return_value = self.mock_conn
        self.mock_pool.acquire.return_value.__aexit__.return_value = None
    
    def test_init_events_db(self):
        """Test events DB initialization."""
        init_events_db(self.mock_pool)
        # Should not raise
    
    @patch('app.observability.events_db._db_pool', None)
    def test_log_event_no_pool(self):
        """Test log_event when pool is not initialized."""
        async def run_test():
            result = await log_event("INFO", "TEST_EVENT")
            self.assertFalse(result)  # Should return False when pool is None
        
        asyncio.run(run_test())
    
    def test_log_event_success(self):
        """Test successful event logging."""
        init_events_db(self.mock_pool)
        
        async def run_test():
            result = await log_event(
                level="INFO",
                event="TEST_EVENT",
                cid="test-cid-123",
                user_id=12345,
            )
            self.assertTrue(result)
            self.mock_conn.execute.assert_called_once()
        
        asyncio.run(run_test())
    
    def test_log_event_with_error(self):
        """Test event logging with exception."""
        init_events_db(self.mock_pool)
        self.mock_conn.execute.side_effect = Exception("DB error")
        
        async def run_test():
            # Should not raise, should return False
            result = await log_event("ERROR", "TEST_EVENT", error=ValueError("test error"))
            self.assertFalse(result)
        
        asyncio.run(run_test())
    
    def test_log_update_received(self):
        """Test log_update_received convenience function."""
        init_events_db(self.mock_pool)
        
        async def run_test():
            result = await log_update_received(update_id=123, cid="cid-123", update_type="message")
            self.assertTrue(result)
            # Verify correct parameters passed
            call_args = self.mock_conn.execute.call_args
            self.assertIn("UPDATE_RECEIVED", str(call_args))
        
        asyncio.run(run_test())
    
    def test_log_callback_received(self):
        """Test log_callback_received convenience function."""
        init_events_db(self.mock_pool)
        
        async def run_test():
            result = await log_callback_received(
                cid="cid-123",
                callback_data="cat:image",
                user_id=12345,
                update_id=456
            )
            self.assertTrue(result)
        
        asyncio.run(run_test())
    
    def test_log_dispatch_ok(self):
        """Test log_dispatch_ok convenience function."""
        init_events_db(self.mock_pool)
        
        async def run_test():
            result = await log_dispatch_ok(cid="cid-123", handler="test_handler", user_id=12345)
            self.assertTrue(result)
        
        asyncio.run(run_test())
    
    def test_log_dispatch_fail(self):
        """Test log_dispatch_fail convenience function."""
        init_events_db(self.mock_pool)
        
        async def run_test():
            error = ValueError("Test error")
            result = await log_dispatch_fail(
                cid="cid-123",
                handler="test_handler",
                error=error,
                user_id=12345
            )
            self.assertTrue(result)
            # Verify error stack trace is included
            call_args = self.mock_conn.execute.call_args
            self.assertIsNotNone(call_args)
        
        asyncio.run(run_test())
    
    def test_log_passive_reject(self):
        """Test log_passive_reject convenience function."""
        init_events_db(self.mock_pool)
        
        async def run_test():
            result = await log_passive_reject(cid="cid-123", update_id=456, update_type="callback_query")
            self.assertTrue(result)
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()


