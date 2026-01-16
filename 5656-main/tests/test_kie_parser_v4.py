"""
Tests for KIE parser V4 compatibility.
Tests robustness to various recordInfo response formats.
"""
import json
import pytest
from app.kie.parser import parse_record_info


class TestParserV4Compatibility:
    """Test parser handling of V4 API responses."""
    
    def test_parse_record_info_with_data_wrapper(self):
        """Test parsing when state/status is inside 'data' field."""
        record_info = {
            "data": {
                "state": "success",
                "resultUrls": ["https://example.com/image1.jpg"],
                "taskId": "task123"
            }
        }
        
        result = parse_record_info(record_info)
        assert result['state'] == 'done'
        assert result['is_done'] is True
        assert result['result_urls'] == ["https://example.com/image1.jpg"]
        assert "✅" in result['message']
    
    def test_parse_record_info_state_normalization(self):
        """Test normalization of various state names."""
        test_cases = [
            ("success", "done"),
            ("succeed", "done"),
            ("done", "done"),
            ("completed", "done"),
            ("finished", "done"),
            ("fail", "fail"),
            ("failed", "fail"),
            ("error", "fail"),
            ("waiting", "pending"),
            ("pending", "pending"),
            ("processing", "pending"),
            ("running", "pending"),
        ]
        
        for state_input, expected_normalized in test_cases:
            record_info = {"state": state_input}
            result = parse_record_info(record_info)
            assert result['state'] == expected_normalized, f"State {state_input} should normalize to {expected_normalized}, got {result['state']}"
    
    def test_parse_record_info_status_field(self):
        """Test using 'status' field instead of 'state'."""
        record_info = {
            "status": "success",
            "resultUrls": ["https://example.com/result.png"]
        }
        
        result = parse_record_info(record_info)
        assert result['state'] == 'done'
        assert result['result_urls'] == ["https://example.com/result.png"]
    
    def test_parse_record_info_data_with_status(self):
        """Test parsing data field with status instead of state."""
        record_info = {
            "data": {
                "status": "completed",
                "resultJson": '{"resultUrls": ["https://example.com/img.jpg"]}'
            }
        }
        
        result = parse_record_info(record_info)
        assert result['state'] == 'done'
        assert result['result_urls'] == ["https://example.com/img.jpg"]
    
    def test_parse_record_info_pending_with_progress(self):
        """Test pending state with progress information."""
        record_info = {
            "data": {
                "state": "processing",
                "progress": 45,
                "eta": 30
            }
        }
        
        result = parse_record_info(record_info)
        assert result['state'] == 'pending'
        assert result['progress'] == 45
        assert result['eta'] == 30
        assert "45%" in result['message']
    
    def test_parse_record_info_fail_with_code(self):
        """Test fail state with error code and message."""
        record_info = {
            "data": {
                "status": "failed",
                "failCode": "INVALID_INPUT",
                "failMsg": "Image resolution too low"
            }
        }
        
        result = parse_record_info(record_info)
        assert result['state'] == 'fail'
        assert result['is_failed'] is True
        assert result['error_code'] == "INVALID_INPUT"
        assert result['error_message'] == "Image resolution too low"
        assert "❌" in result['message']
        assert "INVALID_INPUT" in result['message']
    
    def test_parse_record_info_result_json_string(self):
        """Test parsing resultJson as JSON string."""
        result_data = {
            "resultUrls": [
                "https://example.com/output1.jpg",
                "https://example.com/output2.jpg"
            ]
        }
        
        record_info = {
            "state": "success",
            "resultJson": json.dumps(result_data)
        }
        
        result = parse_record_info(record_info)
        assert result['state'] == 'done'
        assert len(result['result_urls']) == 2
        assert result['result_object'] == result_data
    
    def test_parse_record_info_direct_url_in_result_json(self):
        """Test when resultJson contains a single URL string."""
        record_info = {
            "state": "done",
            "resultJson": '"https://example.com/final.jpg"'
        }
        
        result = parse_record_info(record_info)
        assert result['state'] == 'done'
        assert result['result_urls'] == ["https://example.com/final.jpg"]
    
    def test_parse_record_info_urls_in_various_fields(self):
        """Test URL extraction from different field names."""
        test_cases = [
            ({"result_urls": ["https://ex.com/1.jpg"]}, ["https://ex.com/1.jpg"]),
            ({"urls": ["https://ex.com/2.jpg"]}, ["https://ex.com/2.jpg"]),
            ({"results": ["https://ex.com/3.jpg"]}, ["https://ex.com/3.jpg"]),
            ({"output": ["https://ex.com/4.jpg"]}, ["https://ex.com/4.jpg"]),
            ({"files": ["https://ex.com/5.jpg"]}, ["https://ex.com/5.jpg"]),
        ]
        
        for result_json_content, expected_urls in test_cases:
            record_info = {
                "state": "success",
                "resultJson": json.dumps(result_json_content)
            }
            
            result = parse_record_info(record_info)
            assert result['result_urls'] == expected_urls
    
    def test_parse_record_info_empty_result_urls(self):
        """Test success state without result URLs."""
        record_info = {
            "state": "success"
        }
        
        result = parse_record_info(record_info)
        assert result['state'] == 'done'
        assert result['result_urls'] == []
        assert "✅" in result['message']
        assert "успешно" in result['message'].lower()
    
    def test_parse_record_info_is_done_flag(self):
        """Test is_done and is_failed flags."""
        # Test done
        result_done = parse_record_info({"state": "success"})
        assert result_done['is_done'] is True
        assert result_done['is_failed'] is False
        
        # Test failed
        result_fail = parse_record_info({"state": "failed"})
        assert result_fail['is_done'] is False
        assert result_fail['is_failed'] is True
        
        # Test pending
        result_pending = parse_record_info({"state": "processing"})
        assert result_pending['is_done'] is False
        assert result_pending['is_failed'] is False


class TestCallbackPayloadExtraction:
    """Test extraction of taskId from various callback payload formats."""
    
    def test_task_id_at_root_level(self):
        """Test taskId at root level of payload."""
        payload = {
            "taskId": "task-123-abc",
            "state": "done",
            "resultUrls": ["https://example.com/result.jpg"]
        }
        
        # Simulate extraction logic from main_render.py
        task_id = (
            payload.get("taskId") or
            payload.get("task_id") or
            payload.get("data", {}).get("taskId") or
            payload.get("recordId") or
            payload.get("data", {}).get("recordId")
        )
        
        assert task_id == "task-123-abc"
    
    def test_task_id_in_data_field(self):
        """Test taskId nested inside data field."""
        payload = {
            "data": {
                "taskId": "task-456-def",
                "status": "success",
                "resultUrls": ["https://example.com/img.png"]
            }
        }
        
        task_id = (
            payload.get("taskId") or
            payload.get("data", {}).get("taskId") or
            payload.get("recordId") or
            payload.get("data", {}).get("recordId")
        )
        
        assert task_id == "task-456-def"
    
    def test_record_id_fallback(self):
        """Test fallback to recordId when taskId not present."""
        payload = {
            "recordId": "rec-789-ghi",
            "data": {
                "status": "completed",
                "resultUrls": ["https://example.com/out.jpg"]
            }
        }
        
        task_id = (
            payload.get("taskId") or
            payload.get("data", {}).get("taskId") or
            payload.get("recordId") or
            payload.get("data", {}).get("recordId")
        )
        
        assert task_id == "rec-789-ghi"
    
    def test_record_id_in_data(self):
        """Test recordId inside data field."""
        payload = {
            "data": {
                "recordId": "rec-xxx-yyy",
                "status": "success",
                "resultUrls": ["https://example.com/final.jpg"]
            }
        }
        
        task_id = (
            payload.get("taskId") or
            payload.get("data", {}).get("taskId") or
            payload.get("recordId") or
            payload.get("data", {}).get("recordId")
        )
        
        assert task_id == "rec-xxx-yyy"
    
    def test_no_task_id_in_payload(self):
        """Test when no taskId or recordId present."""
        payload = {
            "data": {
                "status": "success",
                "resultUrls": ["https://example.com/img.jpg"]
            }
        }
        
        task_id = (
            payload.get("taskId") or
            payload.get("data", {}).get("taskId") or
            payload.get("recordId") or
            payload.get("data", {}).get("recordId")
        )
        
        assert task_id is None
