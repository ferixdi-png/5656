"""Smoke tests for polling logic - ensures no infinite hangs"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.services.generation_service import GenerationService


@pytest.mark.asyncio
async def test_polling_detects_callback_update():
    """Test that polling terminates when callback updates storage to 'done'"""
    # Setup mocks
    mock_storage = AsyncMock()
    mock_kie_client = AsyncMock()
    
    # Simulate: job exists, callback updates it to 'done' after 2 iterations
    call_count = 0
    async def get_job_side_effect(job_id):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return {
                'job_id': job_id,
                'status': 'running',
                'user_id': 123,
                'external_task_id': 'task-abc'
            }
        else:
            return {
                'job_id': job_id,
                'status': 'done',
                'result_urls': ['http://result.png'],
                'user_id': 123,
                'external_task_id': 'task-abc'
            }
    
    mock_storage.get_job.side_effect = get_job_side_effect
    mock_storage.update_job_status = AsyncMock()
    
    # KIE API always returns 'pending' (simulates stuck API)
    mock_kie_client.get_task_status = AsyncMock(return_value={
        'ok': True,
        'state': 'pending',
        'resultUrls': []
    })
    
    # Patch dependencies and asyncio.sleep to speed up test (3s poll_interval -> 0.01s)
    original_sleep = asyncio.sleep
    async def fast_sleep(delay, result=None):
        await original_sleep(min(delay, 0.01), result)  # Cap at 0.01s for tests
    
    with patch('app.services.generation_service.get_kie_client_or_stub', return_value=mock_kie_client), \
         patch('app.services.generation_service.get_storage', return_value=mock_storage), \
         patch('asyncio.sleep', side_effect=fast_sleep):
        
        service = GenerationService()
        
        # Track callbacks
        complete_called = False
        complete_urls = None
        
        async def on_complete(urls):
            nonlocal complete_called, complete_urls
            complete_called = True
            complete_urls = urls
        
        # Start polling
        await service.start_polling(
            'job-123',
            on_complete=on_complete,
            on_error=None,
            on_progress=None
        )
        
        # Wait for polling task to actually complete (task is removed from _polling_tasks)
        for _ in range(50):  # Max 0.5 seconds with fast_sleep
            if 'job-123' not in service._polling_tasks:
                break
            await original_sleep(0.01)
        
        # Assertions
        assert complete_called, "on_complete should be called"
        assert complete_urls == ['http://result.png'], "Should return result URLs from storage"
        assert call_count >= 3, "Should poll at least 3 times before detecting storage update"
        
        # Verify polling terminated (not still in _polling_tasks)
        assert 'job-123' not in service._polling_tasks, "Polling task should be removed after completion"


@pytest.mark.asyncio
async def test_polling_no_infinite_pending_loop():
    """Test that polling doesn't loop infinitely if KIE API stuck on 'pending'"""
    mock_storage = AsyncMock()
    mock_kie_client = AsyncMock()
    
    # Simulate callback updating storage to 'done' immediately
    mock_storage.get_job = AsyncMock(return_value={
        'job_id': 'job-instant',
        'status': 'done',
        'result_urls': ['http://instant.png'],
        'external_task_id': 'task-instant'
    })
    mock_storage.update_job_status = AsyncMock()
    
    # KIE API stuck on 'pending' forever
    mock_kie_client.get_task_status = AsyncMock(return_value={
        'ok': True,
        'state': 'pending'
    })
    
    # Patch dependencies and speed up asyncio.sleep
    original_sleep = asyncio.sleep
    async def fast_sleep(delay, result=None):
        await original_sleep(min(delay, 0.01), result)
    
    with patch('app.services.generation_service.get_kie_client_or_stub', return_value=mock_kie_client), \
         patch('app.services.generation_service.get_storage', return_value=mock_storage), \
         patch('asyncio.sleep', side_effect=fast_sleep):
        
        service = GenerationService()
        
        complete_called = False
        start_time = asyncio.get_event_loop().time()
        
        async def on_complete(urls):
            nonlocal complete_called
            complete_called = True
        
        await service.start_polling('job-instant', on_complete=on_complete)
        
        # Wait for task completion
        for _ in range(50):
            if 'job-instant' not in service._polling_tasks:
                break
            await original_sleep(0.01)
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        # Should complete almost instantly (storage check)
        assert complete_called, "Should complete immediately via storage"
        assert duration < 1.0, f"Should complete in <1s, took {duration:.2f}s"
        
        # Should NOT have called KIE API many times (storage resolved it first)
        assert mock_kie_client.get_task_status.call_count <= 2, \
            f"Should call KIE API max 1-2 times, called {mock_kie_client.get_task_status.call_count}"
