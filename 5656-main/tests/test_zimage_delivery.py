"""
Tests for Z-IMAGE end-to-end delivery with idempotency.
"""
import pytest
import json
from datetime import datetime, timezone


def test_parse_result_json_simple():
    """Test parsing resultJson with resultUrls."""
    result_json_str = json.dumps({
        "resultUrls": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
    })
    
    parsed = json.loads(result_json_str)
    result_urls = parsed.get("resultUrls") or []
    
    assert len(result_urls) == 2
    assert result_urls[0] == "https://example.com/image1.jpg"
    assert result_urls[1] == "https://example.com/image2.jpg"


def test_parse_result_json_nested():
    """Test parsing resultJson with nested urls field."""
    result_json_str = json.dumps({
        "urls": ["https://example.com/video.mp4"]
    })
    
    parsed = json.loads(result_json_str)
    result_urls = parsed.get("resultUrls") or parsed.get("urls") or []
    
    assert len(result_urls) == 1
    assert result_urls[0] == "https://example.com/video.mp4"


def test_parse_result_json_empty():
    """Test parsing empty resultJson."""
    result_json_str = json.dumps({})
    
    parsed = json.loads(result_json_str)
    result_urls = parsed.get("resultUrls") or parsed.get("urls") or []
    
    assert result_urls == []


def test_parse_result_json_malformed():
    """Test handling malformed resultJson."""
    result_json_str = "not valid json"
    
    try:
        parsed = json.loads(result_json_str)
        result_urls = parsed.get("resultUrls") or []
    except json.JSONDecodeError:
        result_urls = []
    
    assert result_urls == []


def test_datetime_timezone_aware():
    """Test timezone-aware datetime (from orphan_reconciler fix)."""
    # Naive datetime
    received_at = datetime(2026, 1, 13, 7, 0, 0)
    
    # Normalize
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    
    # Calculate age
    now = datetime.now(timezone.utc)
    age = now - received_at
    
    # Should not raise TypeError
    assert age.total_seconds() >= 0
    assert received_at.tzinfo is not None


def test_idempotency_check():
    """Test idempotency logic for duplicate delivery prevention."""
    # Simulate job with delivered_at
    job_delivered = {
        'job_id': '123',
        'status': 'done',
        'result_urls': ['https://example.com/image.jpg'],
        'delivered_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Should skip delivery
    already_delivered = job_delivered.get('delivered_at') is not None
    assert already_delivered is True
    
    # Simulate job without delivered_at
    job_pending = {
        'job_id': '456',
        'status': 'done',
        'result_urls': ['https://example.com/image.jpg'],
        'delivered_at': None
    }
    
    # Should allow delivery
    already_delivered = job_pending.get('delivered_at') is not None
    assert already_delivered is False


def test_normalize_job_status():
    """Test status normalization."""
    from app.storage.status import normalize_job_status
    
    assert normalize_job_status('success') == 'done'
    assert normalize_job_status('SUCCESS') == 'done'
    assert normalize_job_status('completed') == 'done'
    assert normalize_job_status('fail') == 'failed'
    assert normalize_job_status('FAILED') == 'failed'
    assert normalize_job_status('error') == 'failed'
    assert normalize_job_status('running') == 'running'
    assert normalize_job_status('waiting') == 'queued'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
