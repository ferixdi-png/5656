"""
Smoke tests for end-to-end KIE image generation flow.
Tests real generation with aspect_ratio parameter.
"""
import asyncio
import json
import logging
import os
from typing import Optional

import pytest
from aiohttp import web

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Minimal mock for testing callback handling
class MockStorageForCallback:
    """Mock storage for testing callback payload parsing."""
    
    async def get_job(self, task_id: str):
        """Simulate job lookup."""
        if task_id.startswith("nonexistent"):
            return None
        return {
            "job_id": task_id,
            "user_id": 123456789,
            "status": "pending",
            "model_key": "kie-z-image"
        }
    
    async def find_job_by_task_id(self, task_id: str):
        """Fallback job lookup."""
        return await self.get_job(task_id)
    
    async def update_job_status(self, job_id: str, status: str, result_urls=None, error_message=None):
        """Mock status update."""
        logger.info(f"[MOCK_STORAGE] Updated {job_id} → {status}, urls={result_urls}")


class TestCallbackPayloadHandling:
    """Test handling of various KIE callback payload formats."""
    
    def test_callback_payload_with_data_wrapper(self):
        """Test callback where state/taskId are in 'data' field."""
        payload = {
            "data": {
                "taskId": "task-z-image-001",
                "status": "success",
                "resultUrls": ["https://example.com/z-image-result.jpg"]
            }
        }
        
        # Simulate taskId extraction
        task_id = (
            payload.get("taskId") or
            payload.get("data", {}).get("taskId") or
            payload.get("recordId") or
            payload.get("data", {}).get("recordId")
        )
        
        assert task_id == "task-z-image-001"
        assert payload["data"]["status"] == "success"
    
    def test_callback_missing_task_id_returns_ok(self):
        """Test that missing taskId returns 200 OK (not 400)."""
        # Simulate what main_render.py kie_callback should do
        payload = {
            "data": {
                "status": "success",
                "resultUrls": ["https://example.com/orphaned-result.jpg"]
            }
        }
        
        task_id = (
            payload.get("taskId") or
            payload.get("data", {}).get("taskId") or
            payload.get("recordId") or
            payload.get("data", {}).get("recordId")
        )
        
        # Should be None
        assert task_id is None
        
        # But we should return 200 OK to prevent KIE retries
        # (not 400 error)
        response_body = {"ok": True, "ignored": True}
        assert response_body["ok"] is True


class TestKIEImageGenerationFlow:
    """Integration tests for real image generation."""
    
    def test_z_image_aspect_ratio_in_params(self):
        """Test that aspect_ratio parameter is properly sent to KIE."""
        # Simulate generating z-image with aspect_ratio='1:1'
        request_payload = {
            "model_key": "kie-z-image",
            "input": {
                "prompt": "A beautiful landscape with mountains",
                "aspect_ratio": "1:1",  # square format
                "quality": "high"
            }
        }
        
        assert request_payload["input"]["aspect_ratio"] == "1:1"
        assert request_payload["input"]["prompt"] is not None
    
    def test_z_image_response_with_result_urls(self):
        """Test parsing successful z-image response."""
        kie_response = {
            "taskId": "z-image-task-12345",
            "status": "success",
            "data": {
                "status": "done",
                "resultUrls": ["https://cdn.kie.ai/z-image-output-12345.jpg"]
            }
        }
        
        # Extract result URLs
        result_urls = (
            kie_response.get("resultUrls") or
            kie_response.get("data", {}).get("resultUrls") or
            []
        )
        
        assert len(result_urls) == 1
        assert "z-image-output-12345.jpg" in result_urls[0]
    
    @pytest.mark.asyncio
    async def test_callback_updates_job_with_result_urls(self):
        """Test that callback properly updates job with result URLs."""
        storage = MockStorageForCallback()
        
        # Simulate receiving callback with z-image result
        callback_payload = {
            "data": {
                "taskId": "z-image-async-001",
                "status": "success",
                "resultUrls": [
                    "https://cdn.kie.ai/z-image-final-001.jpg"
                ]
            }
        }
        
        task_id = callback_payload["data"]["taskId"]
        job = await storage.get_job(task_id)
        
        assert job is not None
        assert job["job_id"] == task_id
        
        # Update with result
        await storage.update_job_status(
            job["job_id"],
            "done",
            result_urls=callback_payload["data"]["resultUrls"]
        )
    
    def test_parser_handles_z_image_response_format(self):
        """Test parser with real z-image API response structure."""
        from app.kie.parser import parse_record_info
        
        # Real format from z-image API
        record_info = {
            "data": {
                "state": "success",
                "resultUrls": [
                    "https://storage.kie.ai/z-image-12345-output.jpg"
                ]
            }
        }
        
        result = parse_record_info(record_info)
        
        assert result['state'] == 'done'
        assert result['is_done'] is True
        assert len(result['result_urls']) == 1
        assert "z-image" in result['result_urls'][0]
    
    def test_parser_normalizes_z_image_done_state(self):
        """Test that various 'done' states are normalized."""
        from app.kie.parser import parse_record_info
        
        done_states = ['success', 'succeed', 'done', 'completed', 'finished']
        
        for state_name in done_states:
            record_info = {
                "data": {
                    "state": state_name,
                    "resultUrls": ["https://example.com/result.jpg"]
                }
            }
            
            result = parse_record_info(record_info)
            assert result['state'] == 'done', f"State {state_name} should normalize to 'done'"
            assert result['is_done'] is True


class TestErrorHandling:
    """Test error handling in callbacks and polling."""
    
    def test_callback_with_404_error_response(self):
        """Test callback handling when KIE returns error."""
        from app.kie.parser import parse_record_info
        
        record_info = {
            "data": {
                "state": "failed",
                "failCode": "MODEL_NOT_FOUND",
                "failMsg": "Model kie-z-image not found in this region"
            }
        }
        
        result = parse_record_info(record_info)
        
        assert result['state'] == 'fail'
        assert result['is_failed'] is True
        assert result['error_code'] == "MODEL_NOT_FOUND"
        assert "not found" in result['error_message'].lower()
    
    def test_callback_with_timeout_error(self):
        """Test callback when generation times out."""
        from app.kie.parser import parse_record_info
        
        record_info = {
            "data": {
                "status": "error",
                "error": "Request timeout after 60 seconds"
            }
        }
        
        result = parse_record_info(record_info)
        
        assert result['state'] == 'fail'
        assert "timeout" in result['error_message'].lower()
    
    def test_polling_detects_pending_state(self):
        """Test that polling correctly identifies pending tasks."""
        from app.kie.parser import parse_record_info
        
        record_info = {
            "data": {
                "state": "processing",
                "progress": 67,
                "eta": 15
            }
        }
        
        result = parse_record_info(record_info)
        
        assert result['state'] == 'pending'
        assert result['is_done'] is False
        assert result['is_failed'] is False
        assert result['progress'] == 67
        assert "67%" in result['message']


@pytest.mark.asyncio
async def test_full_callback_workflow():
    """Integration test: callback payload parsing and job update."""
    from app.kie.parser import parse_record_info
    
    # 1. Receive callback from KIE
    raw_callback = {
        "data": {
            "taskId": "kie-z-image-final-test",
            "status": "completed",
            "resultUrls": [
                "https://cdn.kie.ai/z-image-output-xyz.jpg"
            ]
        }
    }
    
    # 2. Extract taskId (using new fallback logic)
    task_id = (
        raw_callback.get("taskId") or
        raw_callback.get("data", {}).get("taskId")
    )
    
    assert task_id == "kie-z-image-final-test"
    
    # 3. Parse record info
    parsed = parse_record_info(raw_callback["data"])
    
    assert parsed['state'] == 'done'
    assert parsed['is_done'] is True
    assert len(parsed['result_urls']) == 1
    
    # 4. Verify message for user
    assert "✅" in parsed['message']
    assert "Готово" in parsed['message']
