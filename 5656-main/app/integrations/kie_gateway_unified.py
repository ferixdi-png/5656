"""
Unified KIE Gateway - единая реализация createTask + recordInfo.

Использует ТОЛЬКО модели из registry.
Добавлены таймауты, ретраи, backoff+jitter, семафор параллелизма.
"""

import os
import asyncio
import logging
import random
from typing import Any, Dict, Optional
from datetime import datetime

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from app.kie.spec_registry import get_registry
from app.kie.model_enforcer import enforce_model_from_registry, get_model_or_fail

logger = logging.getLogger(__name__)


class KIEGatewayError(Exception):
    """Базовый класс для ошибок KIE Gateway"""
    pass


class KIEModelNotFoundError(KIEGatewayError):
    """Модель не найдена в registry"""
    pass


class KIENetworkError(KIEGatewayError):
    """Ошибка сети"""
    pass


class KIERateLimitError(KIEGatewayError):
    """Rate limit 429"""
    pass


class UnifiedKIEGateway:
    """
    Единый gateway для KIE AI API.
    
    - Использует ТОЛЬКО модели из registry
    - Таймауты, ретраи, backoff+jitter
    - Семафор параллелизма
    - Нормализация ответов
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.kie.ai",
        timeout: int = 30,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_concurrent: int = 10
    ):
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp is required for UnifiedKIEGateway")
        
        self.api_key = api_key or os.getenv('KIE_API_KEY')
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        # Семафор для ограничения параллелизма
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._registry = None  # Lazy load
    
    def _get_registry(self):
        """Получает registry (lazy load)."""
        if self._registry is None:
            self._registry = get_registry()
        return self._registry
    
    def _headers(self) -> Dict[str, str]:
        """Получить заголовки для запроса"""
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать сессию"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session
    
    async def close(self):
        """Закрыть сессию"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _should_retry(self, status: int, error: Optional[Exception] = None) -> bool:
        """Определить нужно ли retry"""
        if error:
            # Network errors - retry
            if isinstance(error, (aiohttp.ClientError, asyncio.TimeoutError)):
                return True
        
        # 5xx - retry
        if 500 <= status < 600:
            return True
        
        # 429 - retry с увеличенной задержкой
        if status == 429:
            return True
        
        # 4xx (кроме 429) - не retry
        return False
    
    def _calculate_delay(self, attempt: int, is_rate_limit: bool = False) -> float:
        """Вычисляет задержку для retry с exponential backoff + jitter"""
        if is_rate_limit:
            # Для rate limit используем более длинную задержку
            base = self.base_delay * 5
        else:
            base = self.base_delay
        
        delay = base * (2 ** attempt)
        delay = min(delay, self.max_delay)
        
        # Добавляем jitter (0-20% от delay)
        jitter = delay * 0.2 * random.random()
        delay = delay + jitter
        
        return delay
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет запрос с retry логикой.
        
        Args:
            method: HTTP метод (GET, POST)
            url: URL для запроса
            json_data: JSON данные для POST
            params: Query параметры для GET
        
        Returns:
            Dict с ответом API
        
        Raises:
            KIENetworkError: ошибка сети после всех retry
            KIERateLimitError: rate limit после всех retry
            KIEGatewayError: другие ошибки
        """
        session = await self._get_session()
        headers = self._headers()
        
        last_error = None
        last_status = None
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self._semaphore:  # Ограничение параллелизма
                    async with session.request(
                        method,
                        url,
                        headers=headers,
                        json=json_data,
                        params=params
                    ) as response:
                        last_status = response.status
                        response_data = await response.json()
                        
                        # Проверяем статус
                        if response.status == 200:
                            return response_data
                        
                        # Определяем нужно ли retry
                        is_rate_limit = response.status == 429
                        should_retry = self._should_retry(response.status)
                        
                        if should_retry and attempt < self.max_retries:
                            delay = self._calculate_delay(attempt, is_rate_limit)
                            logger.warning(
                                f"Request failed with status {response.status}, "
                                f"retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries + 1})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        
                        # Не retry или закончились попытки
                        error_msg = response_data.get('msg', f'HTTP {response.status}')
                        
                        if response.status == 429:
                            raise KIERateLimitError(f"Rate limit exceeded: {error_msg}")
                        elif 400 <= response.status < 500:
                            raise KIEGatewayError(f"Client error {response.status}: {error_msg}")
                        else:
                            raise KIEGatewayError(f"Server error {response.status}: {error_msg}")
            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Network error: {e}, retrying in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{self.max_retries + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise KIENetworkError(f"Network error after {self.max_retries + 1} attempts: {e}")
        
        # Если дошли сюда - все попытки исчерпаны
        if last_status == 429:
            raise KIERateLimitError("Rate limit exceeded after all retries")
        elif last_error:
            raise KIENetworkError(f"Network error after all retries: {last_error}")
        else:
            raise KIEGatewayError(f"Request failed after all retries: status {last_status}")
    
    async def create_task(
        self,
        model_id: str,
        input_params: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создает задачу генерации.
        
        ВАЖНО: Проверяет что model_id есть в registry.
        
        Args:
            model_id: ID модели (должен быть в registry)
            input_params: Параметры input
            callback_url: Опциональный callback URL
        
        Returns:
            {
                "ok": True,
                "taskId": "...",
                "status": "created"
            } или {
                "ok": False,
                "error": "..."
            }
        
        Raises:
            KIEModelNotFoundError: если модель не найдена в registry
        """
        # ENFORCEMENT: Проверяем что модель есть в registry
        is_valid, error_msg = enforce_model_from_registry(model_id)
        if not is_valid:
            logger.error(f"[GATEWAY] Model not in registry: {model_id}")
            return {
                "ok": False,
                "error": error_msg
            }
        
        # Получаем спецификацию модели из registry
        model_spec = get_model_or_fail(model_id)
        
        # Формируем payload строго по схеме
        payload = {
            "model": model_id,
            "input": input_params
        }
        
        if callback_url:
            payload["callBackUrl"] = callback_url
        
        # Логируем (без секретов)
        logger.info(
            f"[GATEWAY] Creating task: model={model_id}, "
            f"input_keys={list(input_params.keys())}, callback_url={callback_url is not None}"
        )
        
        try:
            # Выполняем запрос
            response = await self._request_with_retry(
                "POST",
                f"{self.base_url}/api/v1/jobs/createTask",
                json_data=payload
            )
            
            # Нормализуем ответ
            if response.get("code") == 200 and response.get("msg") == "success":
                task_id = response.get("data", {}).get("taskId")
                if not task_id:
                    return {
                        "ok": False,
                        "error": "No taskId in response"
                    }
                
                return {
                    "ok": True,
                    "taskId": task_id,
                    "status": "created"
                }
            else:
                error_msg = response.get("msg", "Unknown error")
                return {
                    "ok": False,
                    "error": error_msg
                }
        
        except KIEModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"[GATEWAY] Error creating task: {e}", exc_info=True)
            return {
                "ok": False,
                "error": str(e)
            }
    
    async def record_info(
        self,
        task_id: str
    ) -> Dict[str, Any]:
        """
        Получает информацию о задаче.
        
        Args:
            task_id: ID задачи
        
        Returns:
            {
                "ok": True,
                "state": "waiting|success|fail",
                "resultJson": {...},
                "failCode": ...,
                "failMsg": ...
            } или {
                "ok": False,
                "error": "..."
            }
        """
        try:
            response = await self._request_with_retry(
                "GET",
                f"{self.base_url}/api/v1/jobs/recordInfo",
                params={"taskId": task_id}
            )
            
            # Нормализуем ответ
            if response.get("code") == 200 and response.get("msg") == "success":
                data = response.get("data", {})
                
                state = data.get("state", "waiting")
                result_json_str = data.get("resultJson")
                fail_code = data.get("failCode")
                fail_msg = data.get("failMsg")
                
                # Парсим resultJson
                result_json = None
                if result_json_str:
                    try:
                        import json
                        result_json = json.loads(result_json_str)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse resultJson: {result_json_str}: {e}")
                
                return {
                    "ok": True,
                    "state": state,
                    "resultJson": result_json,
                    "failCode": fail_code,
                    "failMsg": fail_msg
                }
            else:
                error_msg = response.get("msg", "Unknown error")
                return {
                    "ok": False,
                    "error": error_msg
                }
        
        except Exception as e:
            logger.error(f"[GATEWAY] Error getting record info: {e}", exc_info=True)
            return {
                "ok": False,
                "error": str(e)
            }


# Singleton instance
_gateway_instance: Optional[UnifiedKIEGateway] = None


def get_unified_gateway() -> UnifiedKIEGateway:
    """
    Получает singleton instance UnifiedKIEGateway.
    
    Returns:
        UnifiedKIEGateway
    """
    global _gateway_instance
    
    if _gateway_instance is None:
        _gateway_instance = UnifiedKIEGateway()
    
    return _gateway_instance







