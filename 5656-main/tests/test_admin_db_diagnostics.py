"""
Unit tests for admin DB diagnostics endpoints.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from app.admin.db_diagnostics import (
    check_admin_auth,
    db_health_handler,
    db_recent_handler,
)


class TestAdminDBAuth(unittest.TestCase):
    """Test admin authentication."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.request = MagicMock(spec=web.Request)
        self.request.query = {}
        self.request.headers = {}
    
    @patch('app.admin.db_diagnostics.ADMIN_SECRET', 'test-secret')
    def test_check_admin_auth_secret_query(self):
        """Test admin auth with secret in query."""
        self.request.query = {"secret": "test-secret"}
        self.assertTrue(check_admin_auth(self.request))
    
    @patch('app.admin.db_diagnostics.ADMIN_SECRET', 'test-secret')
    def test_check_admin_auth_secret_header(self):
        """Test admin auth with secret in header."""
        self.request.headers = {"X-Admin-Secret": "test-secret"}
        self.assertTrue(check_admin_auth(self.request))
    
    @patch('app.admin.db_diagnostics.ADMIN_ID', '12345')
    def test_check_admin_auth_user_id(self):
        """Test admin auth with user_id."""
        self.request.query = {"user_id": "12345"}
        self.assertTrue(check_admin_auth(self.request))
    
    def test_check_admin_auth_unauthorized(self):
        """Test admin auth failure."""
        self.request.query = {}
        self.request.headers = {}
        self.assertFalse(check_admin_auth(self.request))


class TestAdminDBEndpoints(AioHTTPTestCase):
    """Test admin DB endpoints."""
    
    async def get_application(self):
        """Create aiohttp application for testing."""
        app = web.Application()
        
        # Mock DB pool
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.acquire.return_value.__aexit__.return_value = None
        
        # Mock connection methods
        mock_conn.fetchval = AsyncMock(return_value=1)  # DB up
        mock_conn.fetch = AsyncMock(return_value=[])
        
        app["db_pool"] = mock_pool
        
        app.router.add_get("/admin/db/health", db_health_handler)
        app.router.add_get("/admin/db/recent", db_recent_handler)
        
        return app
    
    @unittest_run_loop
    @patch('app.admin.db_diagnostics.check_admin_auth', return_value=True)
    async def test_db_health_unauthorized(self, mock_auth):
        """Test db_health without auth."""
        mock_auth.return_value = False
        resp = await self.client.request("GET", "/admin/db/health")
        self.assertEqual(resp.status, 401)
    
    @unittest_run_loop
    @patch('app.admin.db_diagnostics.check_admin_auth', return_value=True)
    @patch('app.admin.db_diagnostics.ADMIN_SECRET', 'test-secret')
    async def test_db_health_success(self, mock_auth):
        """Test db_health success."""
        resp = await self.client.request("GET", "/admin/db/health?secret=test-secret")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertIn("db", data)
        self.assertEqual(data["db"], "up")
    
    @unittest_run_loop
    @patch('app.admin.db_diagnostics.check_admin_auth', return_value=True)
    @patch('app.admin.db_diagnostics.ADMIN_SECRET', 'test-secret')
    async def test_db_recent_success(self, mock_auth):
        """Test db_recent success."""
        resp = await self.client.request("GET", "/admin/db/recent?secret=test-secret&minutes=60")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertIn("events", data)
        self.assertIn("count", data)


if __name__ == "__main__":
    unittest.main()


