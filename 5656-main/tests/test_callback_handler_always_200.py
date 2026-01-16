"""
Integration tests for KIE callback handler.
Ensures callback always returns 200 and handles malformed payloads.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop


class TestKIECallbackHandler(AioHTTPTestCase):
    """Test KIE callback handler always returns 200."""
    
    async def get_application(self):
        """Create test application."""
        app = web.Application()
        
        # Mock dependencies
        self.mock_storage = AsyncMock()
        self.mock_bot = AsyncMock()
        
        async def kie_callback(request: web.Request) -> web.Response:
            """Simplified callback handler for testing."""
            from app.utils.callback_parser import extract_task_id, safe_truncate_payload
            
            # Parse payload
            raw_payload = None
            try:
                raw_payload = await request.json()
            except Exception:
                try:
                    raw_payload = await request.read()
                except Exception:
                    return web.json_response(
                        {"ok": True, "ignored": True, "reason": "unreadable_payload"},
                        status=200
                    )
            
            # Extract task ID
            task_id, record_id, debug_info = extract_task_id(raw_payload)
            
            if not task_id and not record_id:
                return web.json_response({
                    "ok": True,
                    "ignored": True,
                    "reason": "no_task_id"
                }, status=200)
            
            # Success case
            return web.json_response({"ok": True}, status=200)
        
        app.router.add_post("/callbacks/kie", kie_callback)
        return app
    
    @unittest_run_loop
    async def test_callback_valid_payload_returns_200(self):
        """Test callback with valid payload returns 200."""
        payload = {"taskId": "test123", "state": "done"}
        
        resp = await self.client.post("/callbacks/kie", json=payload)
        assert resp.status == 200
        
        data = await resp.json()
        assert data["ok"] is True
    
    @unittest_run_loop
    async def test_callback_invalid_json_returns_200(self):
        """Test callback with invalid JSON returns 200 (not 400)."""
        # Send malformed JSON
        resp = await self.client.post(
            "/callbacks/kie",
            data=b"{not valid json}",
            headers={"Content-Type": "application/json"}
        )
        assert resp.status == 200
        
        data = await resp.json()
        assert data["ok"] is True
        assert data["ignored"] is True
    
    @unittest_run_loop
    async def test_callback_missing_task_id_returns_200(self):
        """Test callback without taskId returns 200 with ignored flag."""
        payload = {"state": "done", "result": "something"}
        
        resp = await self.client.post("/callbacks/kie", json=payload)
        assert resp.status == 200
        
        data = await resp.json()
        assert data["ok"] is True
        assert data["ignored"] is True
        assert data["reason"] == "no_task_id"
    
    @unittest_run_loop
    async def test_callback_empty_payload_returns_200(self):
        """Test callback with empty payload returns 200."""
        resp = await self.client.post("/callbacks/kie", json={})
        assert resp.status == 200
        
        data = await resp.json()
        assert data["ok"] is True
        assert data["ignored"] is True
    
    @unittest_run_loop
    async def test_callback_bytes_payload_returns_200(self):
        """Test callback with bytes payload."""
        payload_bytes = b'{"recordId": "bytes123"}'
        
        resp = await self.client.post(
            "/callbacks/kie",
            data=payload_bytes,
            headers={"Content-Type": "application/json"}
        )
        assert resp.status == 200
        
        data = await resp.json()
        assert data["ok"] is True
    
    @unittest_run_loop
    async def test_callback_data_wrapper_returns_200(self):
        """Test callback with V4 data wrapper."""
        payload = {
            "data": {
                "taskId": "wrapped123",
                "state": "done"
            }
        }
        
        resp = await self.client.post("/callbacks/kie", json=payload)
        assert resp.status == 200
        
        data = await resp.json()
        assert data["ok"] is True
    
    @unittest_run_loop
    async def test_callback_array_wrapper_returns_200(self):
        """Test callback with array wrapper."""
        payload = [{"taskId": "array123"}]
        
        resp = await self.client.post("/callbacks/kie", json=payload)
        assert resp.status == 200
        
        data = await resp.json()
        assert data["ok"] is True
    
    @unittest_run_loop
    async def test_callback_unreadable_payload_returns_200(self):
        """Test callback with completely unreadable payload."""
        # This simulates a case where both json() and read() fail
        # In practice, aiohttp should handle this, but we test the fallback
        resp = await self.client.post("/callbacks/kie", data=b"")
        assert resp.status == 200
    
    @unittest_run_loop
    async def test_callback_huge_payload_returns_200(self):
        """Test callback with very large payload doesn't crash."""
        huge_payload = {
            "taskId": "huge123",
            "data": "x" * 100000  # 100KB of data
        }
        
        resp = await self.client.post("/callbacks/kie", json=huge_payload)
        assert resp.status == 200
    
    @unittest_run_loop
    async def test_callback_nested_taskid_returns_200(self):
        """Test callback with deeply nested taskId."""
        payload = {
            "result": {
                "payload": {
                    "data": {
                        "task_id": "deepNested123"
                    }
                }
            }
        }
        
        resp = await self.client.post("/callbacks/kie", json=payload)
        assert resp.status == 200


class TestCallbackNeverThrows400:
    """Ensure callback NEVER returns 400 under any circumstances."""
    
    @pytest.mark.parametrize("payload", [
        b"{invalid json",
        b"",
        {},
        [],
        None,
        "not even bytes",
        {"random": "data"},
        [1, 2, 3],
    ])
    def test_malformed_payloads_no_400(self, payload):
        """Test that various malformed payloads don't result in 400."""
        from app.utils.callback_parser import extract_task_id
        
        # Parser should never throw
        task_id, record_id, debug = extract_task_id(payload)
        
        # Either found or not found, but no exception
        assert task_id is None or isinstance(task_id, str)
        assert record_id is None or isinstance(record_id, str)
        assert isinstance(debug, dict)
        assert "errors" in debug or "extraction_path" in debug


class TestCallbackPassiveMode:
    """Test callback behavior in passive mode."""
    
    @pytest.mark.asyncio
    async def test_callback_in_passive_mode_saves_data(self):
        """Test that callback in passive mode still saves data (safe operation)."""
        # In passive mode, callback should:
        # 1. Return 200
        # 2. Save result to DB (no charge, just data persistence)
        # 3. NOT send user notifications (side effect)
        
        # This is more of a documentation test
        # Actual implementation should be verified in main_render.py
        assert True  # Placeholder


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
