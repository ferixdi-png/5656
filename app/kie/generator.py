"""
End-to-end generator for Kie.ai models with heartbeat and error handling.
"""
import asyncio
import logging
import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import os

from app.kie.builder import load_source_of_truth
from app.kie.contract import build_create_task_payload, parse_failure, parse_result
from app.kie.validator import ModelContractError
from app.kie.parser import parse_record_info

logger = logging.getLogger(__name__)

# Test mode flag
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
KIE_STUB = os.getenv('KIE_STUB', 'false').lower() == 'true'


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
        self._heartbeat_interval = 15
        
    def _get_api_client(self):
        """Get API client (real or stub)."""
        if self.api_client:
            return self.api_client

        if TEST_MODE or KIE_STUB:
            if not self.source_of_truth:
                self.source_of_truth = load_source_of_truth()
            return self._get_stub_client(self.source_of_truth)
        
        # Import real client - explicit, no fallback
        from app.api.kie_client import KieApiClient
        return KieApiClient()
    
    def _get_stub_client(self, source_of_truth: Dict[str, Any]):
        """Get stub client for testing."""
        model_index = {model.get("model_id"): model for model in source_of_truth.get("models", [])}

        def infer_result_urls(model_id: str) -> list[str]:
            model_schema = model_index.get(model_id, {})
            output_type = model_schema.get("output_type")
            category = model_schema.get("category", "unknown")

            if output_type == "text":
                return ["https://example.com/result.txt"]
            if output_type == "url":
                return ["https://example.com/result.jpg"]
            if output_type == "video":
                return ["https://example.com/result.mp4"]
            if output_type == "audio":
                return ["https://example.com/result.mp3"]

            if category in {"t2i", "i2i", "upscale", "bg_remove", "watermark_remove"}:
                return ["https://example.com/result.jpg"]
            if category in {"t2v", "i2v", "v2v", "lip_sync"}:
                return ["https://example.com/result.mp4"]
            if category in {"music", "sfx", "tts", "audio_isolation"}:
                return ["https://example.com/result.mp3"]
            if category in {"stt", "general"}:
                return ["https://example.com/result.txt"]

            logger.warning("KIE_STUB: unknown category/output for model %s", model_id)
            return ["https://example.com/result.bin"]

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
                if 'fail' in task_id:
                    return {
                        'state': 'fail',
                        'failCode': 'TEST_ERROR',
                        'failMsg': 'Test error message'
                    }
                if 'timeout' in task_id:
                    return {'state': 'waiting'}

                model_id = task_id.replace("stub_task_", "")
                result_urls = infer_result_urls(model_id)
                return {
                    'state': 'success',
                    'resultJson': json.dumps({
                        'resultUrls': result_urls
                    })
                }
        
        return StubClient()
    
    async def generate(
        self,
        model_id: str,
        user_inputs: Dict[str, Any],
        progress_callback: Optional[Callable[[str], None]] = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Generate content using Kie.ai model.
        
        Args:
            model_id: Model identifier
            user_inputs: User inputs (text, url, file, etc.)
            progress_callback: Optional callback for progress updates
            timeout: Maximum wait time in seconds
            
        Returns:
            Result dictionary with:
            - success: bool
            - message: str
            - result_urls: List[str]
            - result_object: Any
            - error_code: Optional[str]
            - error_message: Optional[str]
        """
        try:
            # Build payload
            if not self.source_of_truth:
                self.source_of_truth = load_source_of_truth()
            
            model_spec = next(
                (model for model in self.source_of_truth.get("models", []) if model.get("model_id") == model_id),
                None,
            )
            if not model_spec:
                raise ValueError(f"Model {model_id} not found in source of truth")

            payload = build_create_task_payload(model_spec, user_inputs)
            
            # Create task
            api_client = self._get_api_client()
            payload.setdefault("requestId", f"{model_id}_{datetime.now().timestamp()}")
            create_response = await api_client.create_task(payload)
            task_id = create_response.get('taskId')
            logger.info("KIE createTask model=%s task_id=%s keys=%s", model_id, task_id, list(payload.keys()))
            
            if not task_id:
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
                logger.info("KIE recordInfo model=%s task_id=%s state=%s", model_id, task_id, state)

                if state == 'success':
                    result = parse_result(record_info)
                    return {
                        'success': True,
                        'message': parsed['message'],
                        'result_urls': result['result_urls'],
                        'result_object': result['result_object'],
                        'error_code': None,
                        'error_message': None,
                        'task_id': task_id
                    }
                
                elif state == 'fail':
                    error_code, error_msg = parse_failure(record_info)
                    logger.error("KIE fail model=%s task_id=%s code=%s msg=%s", model_id, task_id, error_code, error_msg)
                    return {
                        'success': False,
                        'message': f"❌ {error_msg}\n\nНажмите /start для возврата в меню.",
                        'result_urls': [],
                        'result_object': None,
                        'error_code': error_code,
                        'error_message': error_msg,
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
                    await asyncio.sleep(3)
                    continue
                
                else:
                    # Unknown state
                    await asyncio.sleep(3)
                    continue
        
        except (ValueError, ModelContractError) as e:
            # Payload building error
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
            logger.error(f"Error in generate: {e}", exc_info=True)
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
