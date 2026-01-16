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
from app.kie.router import is_v4_model, build_category_payload
from app.kie.model_defaults import apply_defaults
from app.models.input_schema import validate_inputs

logger = logging.getLogger(__name__)

# Test mode flag
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
KIE_STUB = os.getenv('KIE_STUB', 'false').lower() == 'true'
USE_V4_API = os.getenv('KIE_USE_V4', 'true').lower() == 'true'  # Default to V4

# Import at module level to avoid circular imports and for isinstance check
try:
    from app.kie.client_v4 import KieApiClientV4
except ImportError:
    KieApiClientV4 = None


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
        """Get API client (real or stub) - V4 or V3."""
        if self.api_client:
            return self.api_client

        # Check DRY_RUN mode first (highest priority)
        dry_run = os.getenv("DRY_RUN", "0").lower() in ("true", "1", "yes")
        if dry_run:
            from app.kie.mock_client import MockKieApiClientV4
            logger.info("[GENERATOR] Using MockKieApiClientV4 (DRY_RUN mode)")
            return MockKieApiClientV4()

        if TEST_MODE or KIE_STUB:
            return self._get_stub_client()
        
        # Check if using V4 API (new architecture)
        if USE_V4_API:
            from app.kie.client_v4 import KieApiClientV4
            return KieApiClientV4()
        
        # Fallback to old V3 client (for compatibility)
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
        timeout: Optional[int] = None,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        price: float = 0.0
    ) -> Dict[str, Any]:
        """
        Generate content using Kie.ai model.
        
        Args:
            model_id: Model identifier
            user_inputs: User inputs (text, url, file, etc.)
            progress_callback: Optional callback for progress updates
            timeout: Maximum wait time in seconds
            user_id: User ID for job tracking (REQUIRED for storage)
            chat_id: Telegram chat ID for result delivery
            price: Generation price (for job record)
            
        Returns:
            Result dictionary with:
            - success: bool
            - message: str
            - result_urls: List[str]
            - result_object: Any
            - error_code: Optional[str]
            - error_message: Optional[str]
        """
        from app.utils.correlation import correlation_tag
        from app.kie.timeout_strategy import get_timeout_for_model, get_timeout_description
        import os
        
        # BATCH 39: Category-based timeout (image ≠ video)
        # Get timeout from ENV or use category-based strategy
        if timeout is None:
            env_timeout = os.getenv('GENERATOR_TIMEOUT_SECONDS')
            if env_timeout:
                timeout = int(env_timeout)
            else:
                # Use smart timeout based on model category
                timeout = get_timeout_for_model(model_id)
        
        timeout_desc = get_timeout_description(timeout)
        logger.info(
            f"{correlation_tag()} [GENERATOR] Starting generate for model={model_id} "
            f"timeout={timeout}s ({timeout_desc})"
        )
        
        # КРИТИЧНО: Валидация входных данных для защиты от атак
        try:
            from app.security.input_validation import validate_user_inputs
            is_valid, error = validate_user_inputs(user_inputs)
            if not is_valid:
                logger.error(
                    f"{correlation_tag()} [GENERATOR] Input validation failed: {error}"
                )
                return {
                    'success': False,
                    'message': f'❌ <b>Ошибка валидации</b>\n\n{error}\n\nПожалуйста, проверьте входные данные и попробуйте снова.',
                    'result_urls': [],
                    'result_object': None,
                    'error_code': 'INPUT_VALIDATION_FAILED',
                    'error_message': error,
                    'task_id': None
                }
        except Exception as e:
            logger.warning(f"{correlation_tag()} [GENERATOR] Input validation error: {e}")
            # Продолжить, если валидация не удалась
        
        logger.info(f"{correlation_tag()} [GENERATOR]   - user_inputs keys: {list(user_inputs.keys())}")
        
        try:
            # Load source of truth if needed
            if not self.source_of_truth:
                self.source_of_truth = load_source_of_truth()
            
            # ✅ PHASE A: Apply model defaults for missing required fields
            # Prevents "Missing required field: guidance_scale" errors
            user_inputs = apply_defaults(model_id, user_inputs)
            logger.info(f"{correlation_tag()} [GENERATOR]   - after defaults: {list(user_inputs.keys())}")
            
            # ✅ PHASE B: Validate inputs before creating payload
            # CRITICAL: Check all string fields size to prevent DoS
            max_string_size = 50 * 1024  # 50KB limit for all string fields
            text_fields = ('prompt', 'text', 'input_text', 'message', 'negative_prompt')
            url_fields = ('image_url', 'video_url', 'audio_url', 'image_base64', 'video_base64', 'audio_base64')
            
            # CRITICAL: Validate URL fields are actual URLs (not file_ids)
            for url_field in url_fields:
                if url_field in user_inputs:
                    url_value = user_inputs[url_field]
                    if isinstance(url_value, str):
                        # Check if it looks like a Telegram file_id (starts with specific prefixes)
                        if url_value.startswith(('AgACAgI', 'BAACAgI', 'CQACAgI', 'DQACAgI')) or \
                           (len(url_value) > 20 and not url_value.startswith(('http://', 'https://'))):
                            logger.error(
                                f"{correlation_tag()} [GENERATOR] {url_field} appears to be a Telegram file_id, not a URL: {url_value[:50]}..."
                            )
                            return {
                                'success': False,
                                'message': f'❌ <b>Ошибка обработки файла</b>\n\nПоле {url_field} содержит недопустимое значение.\n\nПожалуйста, загрузите файл заново или используйте прямую ссылку (URL).',
                                'result_urls': [],
                                'result_object': None,
                                'error_code': 'INVALID_URL_FORMAT',
                                'error_message': f'{url_field} is file_id, not URL',
                                'task_id': None
                            }
                        # Validate URL format
                        if not url_value.startswith(('http://', 'https://')):
                            logger.warning(
                                f"{correlation_tag()} [GENERATOR] {url_field} doesn't start with http:// or https://: {url_value[:50]}..."
                            )
            
            for key, value in user_inputs.items():
                if isinstance(value, str):
                    value_size = len(value.encode('utf-8'))
                    
                    # Check text fields (prompts, messages)
                    if key in text_fields:
                        if value_size > max_string_size:
                            logger.error(
                                f"{correlation_tag()} [GENERATOR] {key} too large: {value_size} bytes (max {max_string_size})"
                            )
                            return {
                                'success': False,
                                'message': f'❌ <b>{key} слишком длинный</b>\n\nМаксимальная длина: {max_string_size // 1024} КБ\n\nПожалуйста, сократите текст и попробуйте снова.',
                                'result_urls': [],
                                'result_object': None,
                                'error_code': 'INPUT_TOO_LARGE',
                                'error_message': f'{key} exceeds {max_string_size} bytes',
                                'task_id': None
                            }
                    
                    # Check URL fields (prevent extremely long URLs)
                    if key in url_fields:
                        max_url_size = 2048  # 2KB limit for URLs
                        if value_size > max_url_size:
                            logger.error(
                                f"{correlation_tag()} [GENERATOR] {key} URL too long: {value_size} bytes (max {max_url_size})"
                            )
                            return {
                                'success': False,
                                'message': f'❌ <b>URL слишком длинный</b>\n\nМаксимальная длина: {max_url_size // 1024} КБ\n\nПожалуйста, проверьте {key} и попробуйте снова.',
                                'result_urls': [],
                                'result_object': None,
                                'error_code': 'URL_TOO_LONG',
                                'error_message': f'{key} URL exceeds {max_url_size} bytes',
                                'task_id': None
                            }
            
            try:
                is_valid, validation_errors = validate_inputs(model_id, user_inputs)
                if not is_valid:
                    error_details = "\n".join([f"  • {err}" for err in validation_errors])
                    logger.error(
                        f"{correlation_tag()} [GENERATOR] Input validation failed for {model_id}:\n{error_details}"
                    )
                    # User-friendly error message in Russian
                    user_message = (
                        f"❌ <b>Ошибка в параметрах</b>\n\n"
                        f"Проверьте введенные данные:\n{error_details}\n\n"
                        f"Нажмите /start для возврата в меню."
                    )
                    return {
                        'success': False,
                        'message': user_message,
                        'result_urls': [],
                        'result_object': None,
                        'error_code': 'VALIDATION_ERROR',
                        'error_message': f'Input validation failed: {validation_errors}',
                        'task_id': None
                    }
            except (ModelContractError, ValueError, TypeError) as validation_exc:
                # Catch validation exceptions (ModelContractError, etc.)
                logger.error(
                    f"{correlation_tag()} [GENERATOR] Validation exception for {model_id}: {validation_exc}",
                    exc_info=True
                )
            except Exception as validation_exc:
                # Catch-all for unexpected validation errors
                logger.error(
                    f"{correlation_tag()} [GENERATOR] Unexpected validation error for {model_id}: {validation_exc}",
                    exc_info=True
                )
                user_message = (
                    f"❌ <b>Ошибка проверки параметров</b>\n\n"
                    f"Не удалось проверить введенные данные. "
                    f"Пожалуйста, проверьте формат и попробуйте снова.\n\n"
                    f"Нажмите /start для возврата в меню."
                )
                return {
                    'success': False,
                    'message': user_message,
                    'result_urls': [],
                    'result_object': None,
                    'error_code': 'VALIDATION_EXCEPTION',
                    'error_message': str(validation_exc),
                    'task_id': None
                }
            
            logger.info(f"{correlation_tag()} [GENERATOR] ✅ Input validation passed for {model_id}")
            
            # Check if this is a V4 model (new architecture)
            is_v4 = USE_V4_API and is_v4_model(model_id)
            
            # Build payload using appropriate builder
            if is_v4:
                logger.info(f"Using V4 API for model {model_id}")
                logger.info(f"  - user_inputs to build_category_payload: {user_inputs}")
                logger.info(f"  - user_inputs keys: {list(user_inputs.keys())}")
                payload = build_category_payload(model_id, user_inputs)
                logger.info(f"  - payload built: {payload}")
            else:
                logger.info(f"Using V3 API for model {model_id}")
                payload = build_payload(model_id, user_inputs, self.source_of_truth)
            
            # Build callback URL for async completion notification (like z-image)
            # CRITICAL: For V4 models, build_category_payload already adds callBackUrl (camelCase)
            # For V3 models, we need to add it manually if supported
            callback_url = None
            if not is_v4:
                # V3 API: add callback_url if supported (check payload structure)
                try:
                    from app.utils.webhook import build_kie_callback_url, get_webhook_base_url
                    webhook_base = get_webhook_base_url()
                    if webhook_base:
                        callback_url = build_kie_callback_url(webhook_base, None)
                        if callback_url:
                            logger.info(f"{correlation_tag()} [GENERATOR] V3: Using callback_url={callback_url[:60]}... for model={model_id}")
                            # V3 API may support callback_url or callBackUrl - try both
                            if isinstance(payload, dict):
                                # Try callBackUrl first (camelCase, more common)
                                if 'callBackUrl' not in payload:
                                    payload['callBackUrl'] = callback_url
                                # Also try callback_url (snake_case, fallback)
                                if 'callback_url' not in payload:
                                    payload['callback_url'] = callback_url
                        else:
                            logger.warning(f"{correlation_tag()} [GENERATOR] V3: Failed to build callback URL (will use polling only)")
                except (ValueError, KeyError, AttributeError) as e:
                    # Specific errors for callback URL building
                    logger.warning(f"{correlation_tag()} [GENERATOR] V3: Failed to build callback URL (will use polling only): {e}")
                except Exception as e:
                    # Unexpected errors
                    logger.warning(f"{correlation_tag()} [GENERATOR] V3: Unexpected error building callback URL (will use polling only): {e}")
            else:
                # V4 API: build_category_payload already adds callBackUrl, just log it
                existing_callback = payload.get('callBackUrl') if isinstance(payload, dict) else None
                if existing_callback:
                    logger.info(f"{correlation_tag()} [GENERATOR] V4: callBackUrl already in payload from build_category_payload")
                else:
                    logger.warning(f"{correlation_tag()} [GENERATOR] V4: No callBackUrl in payload (build_category_payload may not support it)")
            
            # Create task
            api_client = self._get_api_client()
            
            # V4 API requires model_id as first argument
            # V3 API (old KieApiClient) only takes payload
            if isinstance(api_client, KieApiClientV4):
                create_response = await api_client.create_task(model_id, payload)
            else:
                create_response = await api_client.create_task(payload)
            
            # Debug: log response
            logger.info(f"Create task response: {create_response}")
            
            # Check if response is None or has error
            if create_response is None:
                from app.utils.correlation import correlation_tag
                cid = correlation_tag()
                logger.error(f"{cid} [GENERATOR] create_task returned None for model={model_id}")
                return {
                    'success': False,
                    'message': '❌ Ошибка API: не получен ответ от сервера',
                    'result_urls': [],
                    'result_object': None,
                    'error_code': 'NO_RESPONSE',
                    'error_message': 'API client returned None',
                    'task_id': None
                }
            
            # Check for error in response (from exception handling)
            if 'error' in create_response:
                error_msg = create_response.get('error', 'Unknown error')
                error_code = create_response.get('code')
                error_type = create_response.get('error_type', 'API_ERROR')
                user_friendly = create_response.get('user_friendly', error_msg)
                
                # Special handling for 400 (bad request - may be callback_url not supported)
                if error_code == 400:
                    # Check if error mentions callback_url/callBackUrl
                    error_lower = error_msg.lower()
                    if 'callback' in error_lower or 'callBackUrl' in error_lower or 'callback_url' in error_lower:
                        logger.warning(
                            f"{correlation_tag()} [GENERATOR] API 400: callback URL may not be supported for {model_id}. "
                            f"Retrying without callback URL..."
                        )
                        # Remove callback URLs from payload and retry once
                        if isinstance(payload, dict):
                            payload.pop('callBackUrl', None)
                            payload.pop('callback_url', None)
                        
                        # Retry create_task without callback URL
                        try:
                            if isinstance(api_client, KieApiClientV4):
                                create_response = await api_client.create_task(model_id, payload)
                            else:
                                create_response = await api_client.create_task(payload)
                            
                            # Check if retry succeeded
                            if 'error' not in create_response and create_response.get('taskId'):
                                logger.info(f"{correlation_tag()} [GENERATOR] Retry without callback URL succeeded")
                                # Continue with normal flow
                            else:
                                # Retry also failed, return error
                                logger.error(f"{correlation_tag()} [GENERATOR] Retry without callback URL also failed")
                                # Use error mapper for user-friendly message
                                from app.kie.error_mapper import map_kie_error
                                title, details = map_kie_error(400, error_msg)
                                return {
                                    'success': False,
                                    'message': f"{title}\n\n{details}",
                                    'result_urls': [],
                                    'result_object': None,
                                    'error_code': 'API_ERROR_400',
                                    'error_message': error_msg,
                                    'task_id': None
                                }
                        except (ValueError, KeyError, AttributeError) as retry_exc:
                            # Specific errors during retry
                            logger.error(f"{correlation_tag()} [GENERATOR] Retry failed: {retry_exc}")
                        except Exception as retry_exc:
                            # Unexpected errors during retry
                            logger.error(f"{correlation_tag()} [GENERATOR] Unexpected error during retry: {retry_exc}")
                            from app.kie.error_mapper import map_kie_error
                            title, details = map_kie_error(400, error_msg)
                            return {
                                'success': False,
                                'message': f"{title}\n\n{details}",
                                'result_urls': [],
                                'result_object': None,
                                'error_code': 'API_ERROR_400',
                                'error_message': error_msg,
                                'task_id': None
                            }
                    else:
                        # 400 error but not related to callback - return as normal error
                        logger.error(f"{correlation_tag()} [GENERATOR] API 400 (not callback-related): {error_msg}")
                        from app.kie.error_mapper import map_kie_error
                        title, details = map_kie_error(400, error_msg)
                        return {
                            'success': False,
                            'message': f"{title}\n\n{details}",
                            'result_urls': [],
                            'result_object': None,
                            'error_code': 'API_ERROR_400',
                            'error_message': error_msg,
                            'task_id': None
                        }
                
                # Use error mapper for user-friendly messages
                from app.kie.error_mapper import map_kie_error
                title, details = map_kie_error(error_code, error_msg)
                user_message = f"{title}\n\n{details}"
                
                # Special handling for 402 (insufficient credits)
                if error_code == 402:
                    logger.warning(
                        f"{correlation_tag()} ⚠️ API 402 (insufficient credits): {error_msg}"
                    )
                    # CRITICAL: NEVER return mocked success in PROD
                    # 402 is ALWAYS failure, regardless of DRY_RUN/test mode
                    return {
                        'success': False,
                        'status': 'failed',
                        'mocked': False,
                        'message': user_message,
                        'result_urls': [],
                        'result_object': None,
                        'error_code': 'INSUFFICIENT_CREDITS',
                        'error_message': error_msg,
                        'task_id': None
                    }

                logger.error(f"{correlation_tag()} [GENERATOR] API error in create_task: {error_msg}")
                # CRITICAL: Use error mapper for user-friendly message
                title, details = map_kie_error(error_code, error_msg)
                user_message = f"{title}\n\n{details}"
                return {
                    'success': False,
                    'message': user_message,
                    'result_urls': [],
                    'result_object': None,
                    'error_code': 'API_CONNECTION_ERROR',
                    'error_message': error_msg,
                    'task_id': None
                }
            
            # Extract taskId from response (can be at top level or in data object)
            task_id = create_response.get('taskId')
            if not task_id and create_response.get('data'):
                # data can be dict with taskId
                data = create_response.get('data')
                if isinstance(data, dict):
                    task_id = data.get('taskId')
            
            if not task_id:
                # Check if response has error
                error_code = create_response.get('code')
                error_msg = create_response.get('msg', 'Unknown error')
                
                logger.error(
                    f"❌ NO TASK ID | Model: {model_id} | "
                    f"Response code: {error_code} | "
                    f"Error: {error_msg} | "
                    f"Full response: {create_response}"
                )
                return {
                    'success': False,
                    'message': f'❌ Ошибка API: {error_msg}',
                    'result_urls': [],
                    'result_object': None,
                    'error_code': f'API_ERROR_{error_code}' if error_code else 'NO_TASK_ID',
                    'error_message': f'{error_msg}. Response: {create_response}',
                    'task_id': None
                }
            
            # 🎯 CREATE JOB IN STORAGE (CRITICAL FOR E2E DELIVERY)
            if user_id is not None:
                try:
                    from app.storage import get_storage
                    storage = get_storage()
                    
                    # PHASE 3: ENSURE USER EXISTS BEFORE JOB INSERT (FK FIX)
                    # Prevents: violates foreign key generation_jobs_user_id_fkey
                    await storage.ensure_user(
                        user_id=user_id,
                        username=None,  # Will be filled by bot handler
                        first_name=None,
                        last_name=None
                    )
                    
                    # Create job with all metadata
                    job_params = {
                        'model_id': model_id,
                        'inputs': user_inputs,
                        'chat_id': chat_id,
                        'task_id': task_id
                    }
                    
                    await storage.add_generation_job(
                        user_id=user_id,
                        model_id=model_id,
                        model_name=model_id,  # Can enhance with display name later
                        params=job_params,
                        price=price,
                        task_id=task_id,
                        status='queued'
                    )
                    logger.info(f"✅ JOB CREATED | TaskID: {task_id} | User: {user_id} | Chat: {chat_id}")
                except (AttributeError, TypeError, ValueError) as e:
                    # Specific errors during job creation
                    logger.error(f"❌ Failed to create job in storage (specific error): {e}", exc_info=True)
                    # Continue even if storage fails - callback will handle it
                except Exception as e:
                    # Unexpected errors during job creation
                    logger.error(f"❌ Failed to create job in storage (unexpected error): {e}", exc_info=True)
                    # Continue even if storage fails - callback will handle it
            else:
                logger.warning(f"⚠️ No user_id provided - job not created in storage (task_id: {task_id})")
            
            # Set polling interval
            poll_interval = 2  # Check every 2 seconds
            
            logger.info(f"⏳ POLLING | TaskID: {task_id} | Timeout: {timeout}s | Interval: {poll_interval}s")
            
            # Wait for completion with heartbeat
            start_time = datetime.now()
            last_heartbeat = datetime.now()
            poll_iteration = 0
            
            while True:
                poll_iteration += 1
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    from app.utils.correlation import correlation_tag
                    cid = correlation_tag()
                    logger.warning(f"{cid} [GENERATOR] Task {task_id} timeout after {elapsed:.1f}s (limit: {timeout}s)")
                    return {
                        'success': False,
                        'message': (
                            f'⏱️ <b>Превышено время ожидания</b>\n\n'
                            f'Генерация заняла больше {timeout // 60} минут.\n\n'
                            f'💡 <b>Попробуйте:</b>\n'
                            f'• Повторить запрос через минуту\n'
                            f'• Выбрать другую модель\n'
                            f'• Упростить промпт\n\n'
                            f'Если проблема повторяется, обратитесь в поддержку.'
                        ),
                        'result_urls': [],
                        'result_object': None,
                        'error_code': 'TIMEOUT',
                        'error_message': f'Task timeout after {timeout} seconds',
                        'task_id': task_id
                    }
                
                # 🎯 STORAGE-FIRST CHECK (callback может уже обновить job)
                if user_id is not None:
                    try:
                        from app.storage import get_storage
                        storage = get_storage()
                        current_job = await storage.find_job_by_task_id(task_id)
                        
                        if current_job:
                            job_status = normalize_job_status(current_job.get('status', ''))
                            delivered_at = current_job.get('delivered_at')
                            
                            if job_status == 'done':
                                # Callback уже обновил job - используем данные из storage
                                result_urls = current_job.get('result_urls') or []
                                if isinstance(result_urls, str):
                                    try:
                                        result_urls = json.loads(result_urls)
                                    except Exception:
                                        result_urls = [result_urls]
                                
                                # 🎯 IDEMPOTENCY: If callback already delivered, don't send again
                                if delivered_at:
                                    logger.info(f"✅ STORAGE-FIRST | Already delivered via callback | TaskID: {task_id}")
                                else:
                                    logger.info(f"✅ STORAGE-FIRST | Job done (not yet delivered) | TaskID: {task_id}")
                                
                                return {
                                    'success': True,
                                    'message': '✅ Генерация завершена',
                                    'result_urls': result_urls,
                                    'result_object': None,
                                    'error_code': None,
                                    'error_message': None,
                                    'task_id': task_id,
                                    'already_delivered': delivered_at is not None
                                }
                            
                            elif job_status == 'failed':
                                error_msg = current_job.get('error_message') or 'Unknown error'
                                logger.info(f"❌ STORAGE-FIRST | Job failed via callback | TaskID: {task_id}")
                                return {
                                    'success': False,
                                    'message': f'❌ {error_msg}',
                                    'result_urls': [],
                                    'result_object': None,
                                    'error_code': 'GENERATION_FAILED',
                                    'error_message': error_msg,
                                    'task_id': task_id
                                }
                    except (AttributeError, TypeError, ValueError) as e:
                        # Specific storage errors - продолжаем с API polling
                        logger.warning(f"{correlation_tag()} [GENERATOR] Storage check failed (specific error, continuing with API): {e}", exc_info=True)
                    except Exception as e:
                        # Unexpected storage errors - продолжаем с API polling
                        logger.warning(f"{correlation_tag()} [GENERATOR] Storage check failed (unexpected error, continuing with API): {e}", exc_info=True)
                
                # Get record info from API (fallback)
                # CRITICAL: Handle network errors gracefully
                from app.utils.correlation import correlation_tag
                from aiohttp import ClientError
                import asyncio
                
                try:
                    record_info = await api_client.get_record_info(task_id)
                    logger.info(f"{correlation_tag()} [POLL_TICK] i={poll_iteration} task_id={task_id} http_ok={record_info is not None}")
                except (ClientError, asyncio.TimeoutError, ConnectionError) as network_err:
                    # Network error - retry with exponential backoff
                    if poll_iteration < 5:  # Allow up to 5 network errors before giving up
                        retry_delay = min(2 ** poll_iteration, 30)  # Max 30s
                        logger.warning(
                            f"{correlation_tag()} [POLL_NETWORK_ERROR] task_id={task_id} attempt={poll_iteration+1}/5: {network_err}. "
                            f"Retrying in {retry_delay}s..."
                        )
                        await asyncio.sleep(retry_delay)
                        continue  # Retry polling
                    else:
                        # Too many network errors - fail gracefully
                        logger.error(
                            f"{correlation_tag()} [POLL_NETWORK_FAIL] task_id={task_id} failed after 5 network errors"
                        )
                        return {
                            'success': False,
                            'message': '❌ Ошибка сети при проверке статуса генерации. Попробуйте позже.',
                            'result_urls': [],
                            'result_object': None,
                            'error_code': 'NETWORK_ERROR',
                            'error_message': f'Network error during polling: {network_err}',
                            'task_id': task_id
                        }
                except Exception as api_err:
                    # Other API errors - log and continue polling
                    logger.warning(f"{correlation_tag()} [POLL_API_ERROR] task_id={task_id}: {api_err}")
                    record_info = None
                
                parsed = parse_record_info(record_info)
                
                state = parsed['state']
                logger.info(f"{correlation_tag()} [POLL_STATE] i={poll_iteration} task_id={task_id} state={state}")
                
                # STATE NORMALIZATION: Treat done/completed as success
                from app.delivery import normalize_state, SUCCESS_STATES, FAILURE_STATES
                
                normalized_state = normalize_state(state)
                
                if normalized_state != state:
                    logger.info(f"{correlation_tag()} [POLL_SUCCESS_EQUIV] state={state} normalized_to={normalized_state}")
                
                if normalized_state == 'success':
                    # 🎯 UNIFIED DELIVERY COORDINATOR (platform-wide atomic lock)
                    result_urls = parsed['result_urls']
                    
                    # Determine category from model_id
                    category = 'image'  # default
                    if model_id:
                        if 'video' in model_id.lower():
                            category = 'video'
                        elif 'audio' in model_id.lower() or 'music' in model_id.lower():
                            category = 'audio'
                        elif 'upscale' in model_id.lower() or 'enhance' in model_id.lower():
                            category = 'upscale'
                    
                    # Try to deliver using atomic coordinator
                    if chat_id and result_urls and user_id is not None:
                        try:
                            from app.storage import get_storage
                            from app.utils.update_queue import get_queue_manager
                            from app.delivery import deliver_result_atomic
                            
                            storage = get_storage()
                            queue_manager = get_queue_manager()
                            bot = queue_manager.get_bot()
                            
                            if not bot:
                                logger.warning("[corr=%s] [POLL_DELIVERY_SKIP] Bot not configured in queue manager", correlation_tag())
                                return {
                                    "success": True,
                                    "task_id": task_id,
                                    "result_urls": result_urls,
                                    "delivery_note": "fallback_no_bot"
                                }
                            
                            delivery_result = await deliver_result_atomic(
                                storage=storage,
                                bot=bot,
                                task_id=task_id,
                                chat_id=chat_id,
                                result_urls=result_urls,
                                category=category,
                                corr_id=correlation_tag(),
                                timeout_minutes=5
                            )
                            
                            if delivery_result['already_delivered']:
                                # Lock skipped - someone else (callback or other poll) delivered
                                logger.info(f"{correlation_tag()} [DELIVER_LOCK_SKIP_POLL_EXIT] Stopping poll, already delivered")
                                return {
                                    'success': True,
                                    'message': parsed['message'],
                                    'result_urls': result_urls,
                                    'result_object': parsed['result_object'],
                                    'error_code': None,
                                    'error_message': None,
                                    'task_id': task_id,
                                    'already_delivered': True
                                }
                            
                        except (AttributeError, TypeError, ValueError) as e:
                            # Specific errors during delivery
                            logger.exception(f"{correlation_tag()} [POLL_DELIVERY_ERROR] Specific error: {e}")
                        except Exception as e:
                            # Unexpected errors during delivery
                            logger.exception(f"{correlation_tag()} [POLL_DELIVERY_ERROR] Unexpected error: {e}")
                    
                    return {
                        'success': True,
                        'message': parsed['message'],
                        'result_urls': result_urls,
                        'result_object': parsed['result_object'],
                        'error_code': None,
                        'error_message': None,
                        'task_id': task_id
                    }
                
                elif normalized_state == 'failed':
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
                            # Use real progress from Kie.ai if available
                            # MASTER PROMPT: "7. Прогресс / ETA" - enhanced formatting
                            progress_percent = parsed.get('progress', 0)
                            eta_seconds = parsed.get('eta')
                            
                            if progress_percent and progress_percent > 0:
                                # Show progress bar
                                bar_length = 10
                                filled = int(progress_percent / 10)
                                bar = '█' * filled + '░' * (bar_length - filled)
                                
                                if eta_seconds:
                                    progress_callback(
                                        f"⏳ <b>Генерация</b>\n\n"
                                        f"{bar} {progress_percent}%\n"
                                        f"Осталось: ~{eta_seconds} сек"
                                    )
                                else:
                                    progress_callback(
                                        f"⏳ <b>Генерация</b>\n\n"
                                        f"{bar} {progress_percent}%"
                                    )
                            elif eta_seconds:
                                progress_callback(
                                    f"⏳ <b>Генерация...</b>\n\n"
                                    f"Осталось: ~{eta_seconds} сек"
                                )
                            else:
                                # Fallback: show elapsed time with animation
                                dots = '.' * (int(elapsed) % 4)
                                progress_callback(
                                    f"⏳ <b>Генерация{dots}</b>\n\n"
                                    f"Прошло: {int(elapsed)} сек"
                                )
                        last_heartbeat = datetime.now()
                    
                    # Wait before next check
                    await asyncio.sleep(poll_interval)
                    continue
                
                else:
                    # Unknown state
                    await asyncio.sleep(2)
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
            # MASTER PROMPT: Logging - critical event (generation failed)
            logger.error(f"Generation failed: model={model_id}, error={str(e)}")
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
