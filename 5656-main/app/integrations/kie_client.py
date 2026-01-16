"""
KIE AI API Client - единый async клиент с retry/backoff
"""

import os
import asyncio
import logging
import random
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class KIEClientError(Exception):
    """Базовый класс для ошибок KIE клиента"""
    pass


class KIENetworkError(KIEClientError):
    """Ошибка сети (retry)"""
    pass


class KIEServerError(KIEClientError):
    """Ошибка сервера 5xx (retry)"""
    pass


class KIERateLimitError(KIEClientError):
    """Rate limit 429 (retry с увеличенной задержкой)"""
    pass


class KIEClientError4xx(KIEClientError):
    """Ошибка клиента 4xx (не retry, кроме 429)"""
    pass


class KIEClient:
    """Единый async клиент для KIE AI API с retry/backoff"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp is required for KIEClient")
        
        self.api_key = api_key or os.getenv('KIE_API_KEY')
        self.base_url = (base_url or os.getenv('KIE_API_URL', 'https://api.kie.ai')).rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        self._session: Optional[aiohttp.ClientSession] = None
    
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
        if 400 <= status < 500:
            return False
        
        return False
    
    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Retry с экспоненциальным backoff и jitter"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                # Определяем статус если это HTTP ошибка
                status = 0
                if isinstance(e, aiohttp.ClientResponseError):
                    status = e.status
                elif hasattr(e, 'status'):
                    status = e.status
                
                # Проверяем нужно ли retry
                if attempt < self.max_retries and self._should_retry(status, e):
                    # Экспоненциальный backoff с jitter
                    delay = min(
                        self.base_delay * (2 ** attempt) + random.uniform(0, 1),
                        self.max_delay
                    )
                    
                    # Увеличенная задержка для 429
                    if status == 429:
                        delay *= 2
                    
                    logger.warning(
                        f"[RETRY] Attempt {attempt + 1}/{self.max_retries + 1} failed: {e}, "
                        f"retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Не retry или последняя попытка
                    break
        
        # Все попытки исчерпаны
        if isinstance(last_error, aiohttp.ClientResponseError):
            status = last_error.status
            if status == 429:
                raise KIERateLimitError(f"Rate limit exceeded: {last_error}")
            elif 500 <= status < 600:
                raise KIEServerError(f"Server error {status}: {last_error}")
            elif 400 <= status < 500:
                raise KIEClientError4xx(f"Client error {status}: {last_error}")
        
        if isinstance(last_error, (aiohttp.ClientError, asyncio.TimeoutError)):
            raise KIENetworkError(f"Network error: {last_error}")
        
        raise KIEClientError(f"Request failed: {last_error}")
    
    async def create_task(
        self,
        model_id: str,
        input_data: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создать задачу генерации
        
        Args:
            model_id: ID модели
            input_data: Входные данные
            callback_url: Опциональный callback URL
        
        Returns:
            {
                'ok': bool,
                'taskId': str (если ok),
                'error': str (если не ok)
            }
        """
        if not self.api_key:
            return {
                'ok': False,
                'error': 'KIE_API_KEY not configured'
            }
        
        url = f"{self.base_url}/api/v1/jobs/createTask"
        payload = {
            "model": model_id,
            "input": input_data
        }
        if callback_url:
            payload["callBackUrl"] = callback_url
        
        async def _make_request():
            session = await self._get_session()
            async with session.post(url, headers=self._headers(), json=payload) as resp:
                status = resp.status
                if status == 200:
                    data = await resp.json()
                    task_id = data.get('taskId') or data.get('task_id')
                    if task_id:
                        return {
                            'ok': True,
                            'taskId': task_id
                        }
                    else:
                        return {
                            'ok': False,
                            'error': 'No taskId in response'
                        }
                else:
                    error_text = await resp.text()
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=status,
                        message=error_text
                    )
        
        try:
            return await self._retry_with_backoff(_make_request)
        except KIEClientError4xx as e:
            return {
                'ok': False,
                'error': str(e)
            }
        except (KIENetworkError, KIEServerError, KIERateLimitError) as e:
            logger.error(f"[KIE] Request failed after retries: {e}")
            return {
                'ok': False,
                'error': str(e)
            }
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Получить статус задачи
        
        Args:
            task_id: ID задачи
        
        Returns:
            {
                'ok': bool,
                'state': str ('pending', 'processing', 'completed', 'failed'),
                'resultJson': str (JSON string с результатами),
                'resultUrls': List[str] (если state='completed'),
                'failCode': str (если state='failed'),
                'failMsg': str (если state='failed'),
                'error': str (если ok=False)
            }
        """
        if not self.api_key:
            return {
                'ok': False,
                'error': 'KIE_API_KEY not configured'
            }
        
        url = f"{self.base_url}/api/v1/jobs/recordInfo"
        params = {"taskId": task_id}
        
        async def _make_request():
            session = await self._get_session()
            async with session.get(url, headers=self._headers(), params=params) as resp:
                status = resp.status
                if status == 200:
                    data = await resp.json()
                    
                    # Парсим resultJson если есть
                    result_urls = []
                    if 'resultJson' in data:
                        import json
                        try:
                            result_json = json.loads(data['resultJson'])
                            if isinstance(result_json, dict):
                                # Ищем URLs в разных форматах
                                if 'urls' in result_json:
                                    result_urls = result_json['urls']
                                elif 'url' in result_json:
                                    result_urls = [result_json['url']]
                                elif 'resultUrls' in result_json:
                                    result_urls = result_json['resultUrls']
                        except json.JSONDecodeError:
                            pass
                    
                    return {
                        'ok': True,
                        'state': data.get('state', 'pending'),
                        'resultJson': data.get('resultJson'),
                        'resultUrls': result_urls or data.get('resultUrls', []),
                        'failCode': data.get('failCode'),
                        'failMsg': data.get('failMsg')
                    }
                else:
                    error_text = await resp.text()
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=status,
                        message=error_text
                    )
        
        try:
            return await self._retry_with_backoff(_make_request)
        except KIEClientError4xx as e:
            return {
                'ok': False,
                'state': 'failed',
                'error': str(e)
            }
        except (KIENetworkError, KIEServerError, KIERateLimitError) as e:
            logger.error(f"[KIE] Get status failed after retries: {e}")
            return {
                'ok': False,
                'state': 'pending',  # Возможно временная ошибка
                'error': str(e)
            }
    
    async def wait_for_task(
        self,
        task_id: str,
        timeout: int = 900,
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """
        Ждать завершения задачи с polling
        
        Args:
            task_id: ID задачи
            timeout: Максимальное время ожидания (секунды)
            poll_interval: Интервал polling (секунды)
        
        Returns:
            Результат get_task_status() когда задача завершена
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return {
                    'ok': False,
                    'state': 'timeout',
                    'error': f'Task timeout after {timeout}s'
                }
            
            status = await self.get_task_status(task_id)
            
            if not status.get('ok'):
                # Ошибка получения статуса - продолжаем polling
                await asyncio.sleep(poll_interval)
                continue
            
            state = status.get('state', 'pending')
            
            if state in ('completed', 'failed'):
                return status
            
            # pending или processing - продолжаем polling
            await asyncio.sleep(poll_interval)


def get_kie_client() -> KIEClient:
    """Получить KIE клиент (singleton)"""
    # TODO: можно добавить singleton если нужно
    return KIEClient()


