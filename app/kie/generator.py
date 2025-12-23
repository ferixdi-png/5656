"""
End-to-end generator for Kie.ai models with heartbeat and error handling.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import os

from app.kie.builder import build_payload, load_source_of_truth
from app.kie.validator import ModelContractError
from app.kie.parser import parse_record_info, get_human_readable_error

logger = logging.getLogger(__name__)

# Test mode flag
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
KIE_STUB = os.getenv('KIE_STUB', 'false').lower() == 'true'

# Smoke test configuration
SMOKE_TEST_ON_START = os.getenv('SMOKE_TEST_ON_START', '0') == '1'
SMOKE_TEST_MODEL_ID = os.getenv('SMOKE_TEST_MODEL_ID', '')
SMOKE_TEST_INPUT_JSON = os.getenv('SMOKE_TEST_INPUT_JSON', '')


async def run_smoke_test() -> Dict[str, Any]:
    """
    Run a smoke test of Kie.ai generation.
    
    Returns:
        Test result dictionary
    """
    if not SMOKE_TEST_MODEL_ID:
        return {
            'success': False,
            'message': 'SMOKE_TEST_MODEL_ID not configured',
            'error': 'MISSING_CONFIG'
        }
    
    try:
        # Parse input JSON
        import json
        user_inputs = json.loads(SMOKE_TEST_INPUT_JSON) if SMOKE_TEST_INPUT_JSON else {}
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'message': f'Invalid SMOKE_TEST_INPUT_JSON: {e}',
            'error': 'INVALID_JSON'
        }
    
    logger.info(f"🧪 Running smoke test: model={SMOKE_TEST_MODEL_ID}, inputs={user_inputs}")
    
    # Run generation with timeout
    generator = KieGenerator()
    start_time = datetime.now()
    
    try:
        result = await asyncio.wait_for(
            generator.generate(
                model_id=SMOKE_TEST_MODEL_ID,
                user_inputs=user_inputs,
                timeout=120,  # 2 min timeout for smoke test
                correlation_id="smoke_test"
            ),
            timeout=130  # Extra 10s buffer
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if result.get('success'):
            logger.info(f"✅ Smoke test PASSED in {elapsed:.1f}s")
            return {
                'success': True,
                'message': f'Smoke test passed in {elapsed:.1f}s',
                'elapsed_seconds': elapsed,
                'result': result
            }
        else:
            logger.error(f"❌ Smoke test FAILED: {result.get('message')}")
            return {
                'success': False,
                'message': f"Smoke test failed: {result.get('message')}",
                'elapsed_seconds': elapsed,
                'error_code': result.get('error_code'),
                'error_message': result.get('error_message'),
                'result': result
            }
    
    except asyncio.TimeoutError:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Smoke test TIMEOUT after {elapsed:.1f}s")
        return {
            'success': False,
            'message': f'Smoke test timeout after {elapsed:.1f}s',
            'elapsed_seconds': elapsed,
            'error': 'TIMEOUT'
        }
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Smoke test ERROR: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Smoke test error: {e}',
            'elapsed_seconds': elapsed,
            'error': str(e)
        }


class KieGenerator:
    """Universal generator for Kie.ai models."""
    
    def __init__(self, api_client: Optional[Any] = None):
        """
        Initialize generator.
        
        Args:
            api_client: Optional API client (for dependency injection in tests)
        """
        self.api_client = api_client
        self.source_of_truth = None
        self._heartbeat_interval = 12  # 10-15 seconds, use 12 as middle
        
    def _get_api_client(self):
        """Get API client (real or stub)."""
        if self.api_client:
            return self.api_client

        if TEST_MODE or KIE_STUB:
            return self._get_stub_client()
        
        # Import real client - explicit, no fallback
        from app.api.kie_client import KieApiClient
        return KieApiClient()
    
    def _get_stub_client(self):
        """Get stub client for testing."""
        class StubClient:
            async def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
                """Stub create_task."""
                model = payload.get('model', 'unknown')
                return {
                    'taskId': f"stub_task_{model}",
                    'status': 'waiting'
                }
            
            async def get_record_info(self, task_id: str) -> Dict[str, Any]:
                """Stub get_record_info."""
                # Simulate different states for testing
                if 'text' in task_id or 'test_text' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/result1.txt']
                        })
                    }
                elif 'image' in task_id or 'test_image' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/result1.jpg']
                        })
                    }
                elif 'video' in task_id or 'test_video' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/result1.mp4']
                        })
                    }
                elif 'audio' in task_id or 'test_audio' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/result1.mp3']
                        })
                    }
                elif 'url' in task_id or 'test_url' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/processed.jpg']
                        })
                    }
                elif 'file' in task_id or 'test_file' in task_id:
                    return {
                        'state': 'success',
                        'resultJson': json.dumps({
                            'resultUrls': ['https://example.com/processed_file.pdf']
                        })
                    }
                elif 'fail' in task_id:
                    return {
                        'state': 'fail',
                        'failCode': 'TEST_ERROR',
                        'failMsg': 'Test error message'
                    }
                else:
                    return {'state': 'waiting'}
        
        return StubClient()
    
    async def generate(
        self,
        model_id: str,
        user_inputs: Dict[str, Any],
        progress_callback: Optional[Callable[[str], None]] = None,
        timeout: int = 300,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate content using Kie.ai model.
        
        Args:
            model_id: Model identifier
            user_inputs: User inputs (text, url, file, etc.)
            progress_callback: Optional callback for progress updates
            timeout: Maximum wait time in seconds
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            Result dictionary with:
            - success: bool
            - message: str
            - result_urls: List[str]
            - result_object: Any
            - error_code: Optional[str]
            - error_message: Optional[str]
        """
        correlation_id = correlation_id or f"gen_{model_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"[{correlation_id}] Starting generation for model={model_id}")
        
        try:
            # Build payload
            if not self.source_of_truth:
                self.source_of_truth = load_source_of_truth()
            
            payload = build_payload(model_id, user_inputs, self.source_of_truth)
            
            # Create task
            api_client = self._get_api_client()
            logger.info(f"[{correlation_id}] Creating task with payload: {payload.get('model', 'unknown')}")
            create_response = await api_client.create_task(payload)
            task_id = create_response.get('taskId')
            
            if not task_id:
                logger.error(f"[{correlation_id}] No task_id returned from createTask")
                return {
                    'success': False,
                    'message': '❌ Не удалось создать задачу',
                    'result_urls': [],
                    'result_object': None,
                    'error_code': 'NO_TASK_ID',
                    'error_message': 'Task ID not returned',
                    'task_id': None
                }
            
            # Wait for completion with heartbeat
            logger.info(f"[{correlation_id}] Task created: {task_id}, waiting for completion (timeout={timeout}s)")
            start_time = datetime.now()
            last_heartbeat = datetime.now()
            
            while True:
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    return {
                        'success': False,
                        'message': f'⏱️ Превышено время ожидания ({timeout} сек)',
                        'result_urls': [],
                        'result_object': None,
                        'error_code': 'TIMEOUT',
                        'error_message': f'Task timeout after {timeout} seconds',
                        'task_id': task_id
                    }
                
                # Get record info
                record_info = await api_client.get_record_info(task_id)
                parsed = parse_record_info(record_info)
                
                state = parsed['state']
                
                if state == 'success':
                    logger.info(f"[{correlation_id}] Generation SUCCESS for task={task_id}")
                    return {
                        'success': True,
                        'message': parsed['message'],
                        'result_urls': parsed['result_urls'],
                        'result_object': parsed['result_object'],
                        'error_code': None,
                        'error_message': None,
                        'task_id': task_id
                    }
                
                elif state == 'fail':
                    logger.error(f"[{correlation_id}] Generation FAILED for task={task_id}, code={parsed['error_code']}, msg={parsed['error_message']}")
                    error_msg = get_human_readable_error(
                        parsed['error_code'],
                        parsed['error_message']
                    )
                    return {
                        'success': False,
                        'message': f"❌ {error_msg}\n\nНажмите /start для возврата в меню.",
                        'result_urls': [],
                        'result_object': None,
                        'error_code': parsed['error_code'],
                        'error_message': parsed['error_message'],
                        'task_id': task_id
                    }
                
                elif state == 'waiting':
                    # Send heartbeat if needed
                    time_since_heartbeat = (datetime.now() - last_heartbeat).total_seconds()
                    if time_since_heartbeat >= self._heartbeat_interval:
                        if progress_callback:
                            # Estimate remaining time (rough estimate)
                            estimated_total = min(timeout, 60)  # Assume max 60s for estimate
                            remaining = max(0, estimated_total - elapsed)
                            progress_callback(
                                f"⏳ Обрабатываю... (примерно {int(remaining)} сек осталось)\n"
                                f"Пожалуйста, подождите."
                            )
                        last_heartbeat = datetime.now()
                    
                    # Wait before next check
                    await asyncio.sleep(2)  # Check every 2 seconds
                    continue
                
                else:
                    # Unknown state
                    await asyncio.sleep(2)
                    continue
        
        except (ValueError, ModelContractError) as e:
            # Payload building error
            logger.error(f"[{correlation_id}] Payload building error: {e}")
            return {
                'success': False,
                'message': f"❌ Ошибка в параметрах: {str(e)}\n\nНажмите /start для возврата в меню.",
                'result_urls': [],
                'result_object': None,
                'error_code': 'INVALID_INPUT',
                'error_message': str(e),
                'task_id': None
            }
        
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error in generate: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"❌ Произошла ошибка: {str(e)}\n\nНажмите /start для возврата в меню.",
                'result_urls': [],
                'result_object': None,
                'error_code': 'UNKNOWN_ERROR',
                'error_message': str(e),
                'task_id': None
            }


# Convenience functions
async def generate_from_text(
    model_id: str,
    text: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate from text input."""
    generator = KieGenerator()
    user_inputs = {'text': text, 'prompt': text, **kwargs}
    return await generator.generate(model_id, user_inputs, progress_callback)


async def generate_from_url(
    model_id: str,
    url: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate from URL input."""
    generator = KieGenerator()
    user_inputs = {'url': url, **kwargs}
    return await generator.generate(model_id, user_inputs, progress_callback)


async def generate_from_file(
    model_id: str,
    file_id: str,
    progress_callback: Optional[Callable[[str], None]] = None,
    **kwargs
) -> Dict[str, Any]:
    """Generate from file input."""
    generator = KieGenerator()
    user_inputs = {'file': file_id, 'file_id': file_id, **kwargs}
    return await generator.generate(model_id, user_inputs, progress_callback)
