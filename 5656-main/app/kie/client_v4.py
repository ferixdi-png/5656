"""
Kie.ai API Client V4 - поддержка новой category-specific архитектуры.
Работает параллельно со старым client для совместимости.
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from app.kie.router import (
    get_api_category_for_model,
    get_api_endpoint_for_model,
    get_base_url_for_category,
    load_v4_source_of_truth
)

logger = logging.getLogger(__name__)


class KieApiClientV4:
    """
    API client для новой архитектуры Kie.ai (v4).
    Поддерживает category-specific endpoints.
    """
    
    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or os.getenv("KIE_API_KEY")
        if not self.api_key:
            raise ValueError("KIE_API_KEY environment variable is required")
        
        self.timeout = timeout
        self.source_v4 = load_v4_source_of_truth()
        
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _make_request(self, url: str, payload: Dict[str, Any]) -> requests.Response:
        """
        Make HTTP request with automatic retry.
        
        Retries on:
        - ConnectionError (network issues)
        - Timeout (slow response)
        
        Does NOT retry on:
        - 4xx errors (client errors - bad request)
        - 5xx errors (server errors - will be handled by caller)
        """
        return requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout
        )
    
    async def create_task(
        self, 
        model_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create task using category-specific endpoint.
        
        Args:
            model_id: Model identifier (used to route to correct API)
            payload: Request payload (already formatted for specific category)
        
        Returns:
            Task creation response with taskId
        """
        # CRITICAL: Validate inputs
        if not model_id or not isinstance(model_id, str):
            logger.error(f"[KIE] Invalid model_id in create_task: {model_id} (type: {type(model_id)})")
            return {
                "error": "Invalid model_id",
                "state": "fail",
                "code": 400
            }
        
        if not isinstance(payload, dict):
            logger.error(f"[KIE] Invalid payload type in create_task: {type(payload)}")
            return {
                "error": "Invalid payload (must be dict)",
                "state": "fail",
                "code": 400
            }
        
        category = get_api_category_for_model(model_id, self.source_v4)
        if not category:
            return {
                "error": f"Unknown model category for {model_id}",
                "state": "fail"
            }
        
        base_url = get_base_url_for_category(category, self.source_v4)
        endpoint = get_api_endpoint_for_model(model_id, self.source_v4)
        
        # Полный URL для category-specific API
        url = f"{base_url}{endpoint}"
        
        logger.info(
            f"🚀 CREATE TASK | Model: {model_id} | Category: {category} | "
            f"URL: POST {url} | "
            f"Payload keys: {list(payload.keys())}"
        )
        logger.debug(f"Full payload: {payload}")
        
        try:
            response = await asyncio.to_thread(
                self._make_request,
                url,
                payload
            )
            
            logger.info(
                f"✅ RESPONSE | Status: {response.status_code} | "
                f"Body preview: {response.text[:200]}"
            )
            logger.debug(f"Full response: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            # Проверяем если результат вообще валидный JSON
            if not isinstance(result, dict):
                logger.error(f"❌ Invalid response format: {type(result)}")
                return {"error": "Invalid response format", "state": "fail"}
            
            # Проверяем успешность в коде ответа
            response_code = result.get('code')
            if response_code and response_code >= 400:
                # API вернула ошибку
                error_msg = result.get('msg', 'Unknown error')
                logger.error(f"❌ API Error: Code {response_code} - {error_msg}")
                return {
                    "error": error_msg,
                    "code": response_code,
                    "state": "fail"
                }
            
            # Логируем taskId если есть
            task_id = result.get('data', {}).get('taskId') or result.get('taskId')
            if task_id:
                logger.info(f"📝 Task created successfully | TaskID: {task_id}")
                return result
            
            # Если нет taskId и нет ошибки - это тоже ошибка
            logger.warning(f"⚠️ No taskId in response: {result}")
            return {
                "error": "No taskId in response",
                "response": result,
                "state": "fail"
            }
            
        except requests.RequestException as exc:
            # RequestException includes ConnectionError, Timeout, etc.
            # _make_request already retries these, so if we get here, all retries failed
            error_type = type(exc).__name__
            error_msg = str(exc)
            
            logger.error(
                f"❌ CREATE TASK FAILED (after retries) | Model: {model_id} | "
                f"Error: {error_type}: {error_msg} | "
                f"URL: {url}",
                exc_info=True
            )
            
            # Classify error for better user message
            if isinstance(exc, requests.Timeout):
                user_friendly = "Превышено время ожидания ответа от сервера. Попробуйте позже."
            elif isinstance(exc, requests.ConnectionError):
                user_friendly = "Ошибка подключения к серверу. Проверьте интернет-соединение."
            else:
                user_friendly = f"Ошибка сети: {error_type}"
            
            return {
                "error": error_msg,
                "error_type": error_type,
                "user_friendly": user_friendly,
                "state": "fail"
            }
    
    async def get_record_info(self, task_id: str) -> Dict[str, Any]:
        """
        Get task record info (status checking).
        BATCH 48.41: Aligned with official KIE.ai API documentation.
        
        Official API response format:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "taskId": "...",
                "model": "...",
                "state": "waiting|success|fail",
                "resultJson": "{\"resultUrls\": [...]}",
                "failMsg": "...",
                "failCode": "..."
            }
        }
        
        Args:
            task_id: Task ID from create_task
        
        Returns:
            Task status and results (full response with 'data' field)
        """
        url = "https://api.kie.ai/api/v1/jobs/recordInfo"
        params = {"taskId": task_id}
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    requests.get,
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                # BATCH 48.41: Validate response structure according to official docs
                if not isinstance(result, dict):
                    logger.error(f"[KIE] Invalid recordInfo response format: {type(result)}")
                    return {"error": "Invalid response format", "state": "fail", "code": 500}
                
                # Check API-level code
                api_code = result.get('code')
                if api_code and api_code != 200:
                    api_msg = result.get('msg', 'Unknown error')
                    logger.warning(f"[KIE] recordInfo API error code={api_code}: {api_msg}")
                    return {"error": api_msg, "state": "fail", "code": api_code}
                
                # Return full response (with 'data' field) for proper parsing
                return result
                
            except requests.Timeout as exc:
                logger.warning(f"[KIE] recordInfo attempt {attempt+1}/{max_retries} timeout for task_id={task_id}: {exc}")
                if attempt == max_retries - 1:
                    logger.error(f"[KIE] Get record info timeout after {max_retries} attempts for task_id={task_id}", exc_info=True)
                    return {"error": f"Request timeout: {str(exc)}", "state": "fail", "code": 408, "taskId": task_id}
                await asyncio.sleep(1 * (attempt + 1))
            except requests.RequestException as exc:
                logger.warning(f"[KIE] recordInfo attempt {attempt+1}/{max_retries} failed for task_id={task_id}: {exc}")
                if attempt == max_retries - 1:
                    logger.error(f"[KIE] Get record info failed after {max_retries} attempts for task_id={task_id}: {exc}", exc_info=True)
                    return {"error": str(exc), "state": "fail", "code": 500, "taskId": task_id}
                await asyncio.sleep(1 * (attempt + 1))
            except Exception as exc:
                logger.error(f"[KIE] Unexpected error in get_record_info for task_id={task_id}: {exc}", exc_info=True)
                if attempt == max_retries - 1:
                    return {"error": f"Unexpected error: {str(exc)}", "state": "fail", "code": 500, "taskId": task_id}
                await asyncio.sleep(1 * (attempt + 1))
    
    async def poll_task_until_complete(
        self,
        task_id: str,
        max_wait_seconds: int = 300,
        poll_interval: float = 3.0
    ) -> Dict[str, Any]:
        """
        Poll task until completion.
        
        Args:
            task_id: Task ID
            max_wait_seconds: Maximum wait time
            poll_interval: Seconds between polls
        
        Returns:
            Final task data
        """
        # CRITICAL: Validate inputs
        if not task_id or not isinstance(task_id, str):
            logger.error(f"[KIE] Invalid task_id in poll_task_until_complete: {task_id}")
            return {"error": "Invalid task_id", "state": "fail", "code": 400}
        
        if not isinstance(max_wait_seconds, int) or max_wait_seconds <= 0:
            logger.warning(f"[KIE] Invalid max_wait_seconds: {max_wait_seconds}, using default 300")
            max_wait_seconds = 300
        
        if not isinstance(poll_interval, (int, float)) or poll_interval <= 0:
            logger.warning(f"[KIE] Invalid poll_interval: {poll_interval}, using default 3.0")
            poll_interval = 3.0
        
        start_time = asyncio.get_event_loop().time()
        attempts = 0
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > max_wait_seconds:
                logger.error(f"Task {task_id} timed out after {elapsed:.1f}s")
                return {
                    "error": "Task timeout",
                    "state": "timeout",
                    "taskId": task_id,
                    "elapsed_seconds": elapsed
                }
            
            attempts += 1
            try:
                record = await self.get_record_info(task_id)
                
                # CRITICAL: Validate record structure
                if not isinstance(record, dict):
                    logger.error(f"[KIE] Invalid record format in poll_task_until_complete: {type(record)}")
                    return {"error": "Invalid record format", "state": "fail", "code": 500, "taskId": task_id}
                
                if 'error' in record:
                    logger.warning(f"[KIE] Error in record for task_id={task_id}: {record.get('error')}")
                    return record
            except Exception as e:
                logger.error(f"[KIE] Error getting record info in poll_task_until_complete for task_id={task_id}: {e}", exc_info=True)
                # Continue polling on error (might be transient)
                if attempts >= 3:  # After 3 consecutive errors, give up
                    return {"error": f"Failed to get record info: {str(e)}", "state": "fail", "code": 500, "taskId": task_id}
                await asyncio.sleep(poll_interval)
                continue
            
            # BATCH 48.41: Parse state from 'data' field according to official API docs
            # Official format: {"code": 200, "data": {"state": "waiting|success|fail", ...}}
            data = record.get('data', {})
            if not isinstance(data, dict):
                # Fallback: try direct state field (for backward compatibility)
                data = record
            
            state = data.get('state', '').lower()
            logger.info(f"Poll #{attempts} ({elapsed:.1f}s): task {task_id} state={state}")
            
            if state in ['success', 'completed', 'done']:
                logger.info(f"Task {task_id} completed successfully after {elapsed:.1f}s")
                return record
            
            if state in ['fail', 'failed', 'error']:
                logger.error(f"Task {task_id} failed: {record}")
                return record
            
            # Still processing (waiting, running, pending)
            await asyncio.sleep(poll_interval)
