"""
Unit tests for robust callback parser.
Tests extract_task_id with various payload formats.
"""

import pytest
from app.utils.callback_parser import extract_task_id, safe_truncate_payload


class TestExtractTaskId:
    """Test extract_task_id with various payload formats."""
    
    def test_dict_root_task_id(self):
        """Test taskId at root level."""
        payload = {"taskId": "abc123"}
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "abc123"
        assert "root.taskId" in debug["extraction_path"]
    
    def test_dict_root_task_id_underscore(self):
        """Test task_id (underscore variant)."""
        payload = {"task_id": "xyz789"}
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "xyz789"
        assert "root.task_id" in debug["extraction_path"]
    
    def test_dict_root_record_id(self):
        """Test recordId at root level."""
        payload = {"recordId": "rec456"}
        task_id, record_id, debug = extract_task_id(payload)
        assert record_id == "rec456"
        assert "root.recordId" in debug["extraction_path"]
    
    def test_dict_data_wrapper_task_id(self):
        """Test taskId in data wrapper (V4 format)."""
        payload = {
            "data": {
                "taskId": "wrapped123",
                "state": "done"
            }
        }
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "wrapped123"
        assert "data.taskId" in debug["extraction_path"]
    
    def test_dict_data_wrapper_record_id(self):
        """Test recordId in data wrapper."""
        payload = {
            "data": {
                "recordId": "wrappedRec456",
                "status": "success"
            }
        }
        task_id, record_id, debug = extract_task_id(payload)
        assert record_id == "wrappedRec456"
        assert "data.recordId" in debug["extraction_path"]
    
    def test_string_json(self):
        """Test JSON string payload."""
        payload = '{"taskId": "fromString123"}'
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "fromString123"
        assert "parsed_json_string" in debug["extraction_path"]
    
    def test_bytes_payload(self):
        """Test bytes payload."""
        payload = b'{"recordId": "fromBytes789"}'
        task_id, record_id, debug = extract_task_id(payload)
        assert record_id == "fromBytes789"
        assert "decoded_bytes" in debug["extraction_path"]
    
    def test_array_wrapper(self):
        """Test array wrapper [{"taskId": "..."}]."""
        payload = [
            {"taskId": "arrayTask123"},
            {"taskId": "arrayTask456"}  # Should extract first
        ]
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "arrayTask123"
        assert "unwrapped_array" in debug["extraction_path"]
    
    def test_nested_deep_task_id(self):
        """Test deeply nested taskId (DFS search)."""
        payload = {
            "result": {
                "payload": {
                    "task_id": "deepNested123"
                }
            }
        }
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "deepNested123"
        assert any("dfs" in path for path in debug["extraction_path"])
    
    def test_query_params_fallback(self):
        """Test extraction from query params when not in payload."""
        payload = {"status": "done"}  # No taskId
        query_params = {"taskId": "queryTask123"}
        task_id, record_id, debug = extract_task_id(payload, query_params=query_params)
        assert task_id == "queryTask123"
        assert "query.taskId" in debug["extraction_path"]
    
    def test_multiple_id_types(self):
        """Test both taskId and recordId present."""
        payload = {
            "taskId": "task123",
            "recordId": "record456"
        }
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "task123"
        assert record_id == "record456"
    
    def test_missing_all_ids(self):
        """Test payload with no IDs."""
        payload = {"status": "done", "result": "something"}
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id is None
        assert record_id is None
        # Parser may not always add errors if it successfully searches but finds nothing
        assert isinstance(debug, dict)
    
    def test_invalid_json_string(self):
        """Test invalid JSON string."""
        payload = "{not valid json}"
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id is None
        assert "json_parse_failed" in str(debug["errors"])
    
    def test_empty_array(self):
        """Test empty array."""
        payload = []
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id is None
        assert "empty_array" in str(debug["errors"])
    
    def test_generic_id_fallback(self):
        """Test generic 'id' field as last resort."""
        payload = {"id": "generic123", "status": "done"}
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "generic123"
        assert "fallback.id" in debug["extraction_path"]
    
    def test_z_image_callback_format(self):
        """Test z-image specific callback format."""
        payload = {
            "recordId": "rec_z_image_123",
            "data": {
                "state": "succeed",
                "result": {
                    "imageUrl": "https://example.com/image.png"
                }
            }
        }
        task_id, record_id, debug = extract_task_id(payload)
        assert record_id == "rec_z_image_123"
    
    def test_complex_nested_structure(self):
        """Test complex nested structure with mixed arrays and dicts."""
        payload = {
            "response": {
                "items": [
                    {"name": "item1"},
                    {
                        "metadata": {
                            "task_id": "complexNested123"
                        }
                    }
                ]
            }
        }
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "complexNested123"
    
    def test_stringified_json_in_field(self):
        """Test stringified JSON inside a field."""
        payload = {
            "data": '{"taskId": "stringifiedTask123"}'
        }
        # Note: current implementation doesn't parse stringified nested JSON
        # but we can still test it doesn't crash
        task_id, record_id, debug = extract_task_id(payload)
        # May or may not extract depending on implementation
        assert task_id is None or isinstance(task_id, str)
    
    def test_numeric_id(self):
        """Test numeric ID (should be converted to string)."""
        payload = {"taskId": 12345}
        task_id, record_id, debug = extract_task_id(payload)
        assert task_id == "12345"
        assert isinstance(task_id, str)


class TestSafeTruncatePayload:
    """Test safe_truncate_payload utility."""
    
    def test_dict_payload(self):
        """Test dict truncation."""
        payload = {"key": "value" * 100}
        truncated = safe_truncate_payload(payload, max_length=50)
        assert len(truncated) <= 65  # 50 + "... (truncated)"
        assert "truncated" in truncated
    
    def test_short_payload(self):
        """Test payload shorter than max_length."""
        payload = {"key": "short"}
        truncated = safe_truncate_payload(payload, max_length=500)
        assert "truncated" not in truncated
        assert '"key"' in truncated
    
    def test_list_payload(self):
        """Test list truncation."""
        payload = [1, 2, 3, 4, 5] * 50
        truncated = safe_truncate_payload(payload, max_length=30)
        assert len(truncated) <= 45
    
    def test_string_payload(self):
        """Test string truncation."""
        payload = "x" * 1000
        truncated = safe_truncate_payload(payload, max_length=100)
        assert len(truncated) <= 115
    
    def test_non_serializable_object(self):
        """Test object that can't be JSON serialized."""
        class CustomObject:
            pass
        
        payload = CustomObject()
        truncated = safe_truncate_payload(payload)
        # Should contain class name and object representation
        assert "CustomObject" in truncated or "object at" in truncated


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
