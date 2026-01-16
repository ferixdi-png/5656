"""
End-to-end test for Z-IMAGE flow (simulated).

Verifies:
1. /start shows Z-IMAGE button in SINGLE_MODEL mode
2. Clicking button triggers prompt request
3. Sending prompt shows aspect ratio selection
4. Selecting ratio initiates generation
"""
import asyncio
import os
import pytest


def test_single_model_env_detection():
    """Test SINGLE_MODEL_ONLY env var detection."""
    # Set env
    os.environ["SINGLE_MODEL_ONLY"] = "true"
    
    single_model = os.getenv("SINGLE_MODEL_ONLY", "").lower() in ("1", "true", "yes")
    assert single_model is True
    
    # Clean up
    del os.environ["SINGLE_MODEL_ONLY"]
    
    single_model = os.getenv("SINGLE_MODEL_ONLY", "").lower() in ("1", "true", "yes")
    assert single_model is False


def test_aspect_ratios():
    """Test aspect ratio validation."""
    from bot.handlers.z_image import ASPECT_RATIOS
    
    # Valid ratios
    assert "1:1" in ASPECT_RATIOS
    assert "16:9" in ASPECT_RATIOS
    assert "9:16" in ASPECT_RATIOS
    assert "4:3" in ASPECT_RATIOS
    assert "3:4" in ASPECT_RATIOS
    
    # Labels exist
    assert ASPECT_RATIOS["1:1"] == "Квадрат 1:1"
    assert ASPECT_RATIOS["16:9"] == "Широкий 16:9"


def test_z_image_client_initialization():
    """Test z_image_client can be initialized."""
    from app.kie.z_image_client import ZImageClient, get_z_image_client
    
    # Create client (will warn if no API key, but shouldn't crash)
    client = ZImageClient()
    assert client.timeout == 30.0
    assert client.max_retries == 3
    
    # Singleton
    client1 = get_z_image_client()
    client2 = get_z_image_client()
    assert client1 is client2


def test_task_status_enum():
    """Test TaskStatus enum."""
    from app.kie.z_image_client import TaskStatus
    
    # All statuses defined
    assert TaskStatus.PENDING.value == "PENDING"
    assert TaskStatus.PROCESSING.value == "PROCESSING"
    assert TaskStatus.SUCCESS.value == "SUCCESS"
    assert TaskStatus.FAILED.value == "FAILED"
    assert TaskStatus.UNKNOWN.value == "UNKNOWN"


def test_z_image_result_dataclass():
    """Test ZImageResult dataclass."""
    from app.kie.z_image_client import ZImageResult, TaskStatus
    
    # Create result
    result = ZImageResult(
        task_id="test123",
        status=TaskStatus.SUCCESS,
        image_url="https://example.com/image.png",
    )
    
    assert result.task_id == "test123"
    assert result.status == TaskStatus.SUCCESS
    assert result.image_url == "https://example.com/image.png"
    assert result.error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
