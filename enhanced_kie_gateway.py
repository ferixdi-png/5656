"""
Улучшенный KIE Gateway с поддержкой rate limits, retries, callback_url и polling.
Полная реализация для идеальной интеграции.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
import time

from config_runtime import should_use_mock_gateway
from kie_client import get_client, KIEClient

logger = logging.getLogger(__name__)

# Rate limiting
_rate_limit_semaphore = asyncio.Semaphore(10)  # Максимум 10 одновременных запросов
_rate_limit_delay = 0.1  # Минимальная задержка между запросами
_last_request_time = 0.0


class EnhancedKieGateway(ABC):
    """Улучшенный интерфейс для работы с KIE AI."""
    
    @abstractmethod
    async def create_task(
        self,
        model_id: str,
        mode: str,
        input_data: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создает задачу генерации."""
        pass
    
    @abstractmethod
    async def get_task_status(
        self,
        task_id: str,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Получает статус задачи с retry логикой."""
        pass
    
    @abstractmethod
    def parse_result_urls(self, response: Dict[str, Any]) -> List[str]:
        """Парсит resultUrls из ответа."""
        pass


class RealEnhancedKieGateway(EnhancedKieGateway):
    """Реальный gateway с rate limiting и retries."""
    
    def __init__(self):
        self.client: KIEClient = get_client()
        self._request_count = 0
        self._error_count = 0
    
    async def _rate_limit(self):
        """Применяет rate limiting."""
        global _last_request_time
        
        async with _rate_limit_semaphore:
            current_time = time.time()
            elapsed = current_time - _last_request_time
            
            if elapsed < _rate_limit_delay:
                await asyncio.sleep(_rate_limit_delay - elapsed)
            
            _last_request_time = time.time()
    
    async def create_task(
        self,
        model_id: str,
        mode: str,
        input_data: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создает задачу с rate limiting."""
        await self._rate_limit()
        
        try:
            # Получаем реальный API model string из mode
            from kie_master_catalogue import get_mode_by_model_and_mode
            
            mode_data = get_mode_by_model_and_mode(model_id, mode)
            if mode_data:
                api_model = mode_data.get("api_model", model_id)
            else:
                api_model = model_id
            
            result = await self.client.create_task(api_model, input_data, callback_url)
            
            self._request_count += 1
            
            if result.get('ok'):
                logger.info(f"✅ Задача создана: {result.get('taskId')} для {model_id}:{mode}")
            else:
                self._error_count += 1
                logger.error(f"❌ Ошибка создания задачи: {result.get('error')}")
            
            return result
            
        except Exception as e:
            self._error_count += 1
            logger.error(f"❌ Исключение при создании задачи: {e}", exc_info=True)
            return {
                'ok': False,
                'error': str(e)
            }
    
    async def get_task_status(
        self,
        task_id: str,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Получает статус с retry логикой."""
        await self._rate_limit()
        
        last_error = None
        
        for attempt in range(retries):
            try:
                result = await self.client.get_task_status(task_id)
                
                if result.get('ok'):
                    return result
                else:
                    last_error = result.get('error')
                    # Если ошибка не критическая, пробуем еще раз
                    if attempt < retries - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))  # Экспоненциальная задержка
                        continue
                    else:
                        return result
                        
            except Exception as e:
                last_error = str(e)
                if attempt < retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    return {
                        'ok': False,
                        'error': str(e),
                        'state': 'fail'
                    }
        
        return {
            'ok': False,
            'error': last_error or 'Unknown error',
            'state': 'fail'
        }
    
    def parse_result_urls(self, response: Dict[str, Any]) -> List[str]:
        """Парсит resultUrls из ответа."""
        try:
            if not response.get('ok'):
                return []
            
            result_json = response.get('resultJson', '{}')
            if isinstance(result_json, str):
                import json
                result_data = json.loads(result_json)
            else:
                result_data = result_json
            
            # Пробуем разные поля
            result_urls = (
                result_data.get('resultUrls') or
                result_data.get('result_urls') or
                result_data.get('urls') or
                result_data.get('results') or
                []
            )
            
            if isinstance(result_urls, str):
                result_urls = [result_urls]
            
            return result_urls if isinstance(result_urls, list) else []
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга resultUrls: {e}", exc_info=True)
            return []


class MockEnhancedKieGateway(EnhancedKieGateway):
    """Mock gateway для тестирования."""
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._task_counter = 0
    
    async def create_task(
        self,
        model_id: str,
        mode: str,
        input_data: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создает mock задачу."""
        await asyncio.sleep(0.1)
        
        self._task_counter += 1
        task_id = f"mock_{self._task_counter}_{hash(model_id) % 10000}"
        
        self._tasks[task_id] = {
            'task_id': task_id,
            'model_id': model_id,
            'mode': mode,
            'input_data': input_data,
            'status': 'waiting',
            'created_at': time.time()
        }
        
        logger.info(f"🔧 MOCK: Создана задача {task_id} для {model_id}:{mode}")
        
        return {
            'ok': True,
            'taskId': task_id
        }
    
    async def get_task_status(
        self,
        task_id: str,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Получает mock статус."""
        if task_id not in self._tasks:
            return {
                'ok': False,
                'error': f'Task {task_id} not found',
                'state': 'fail'
            }
        
        task = self._tasks[task_id]
        elapsed = time.time() - task['created_at']
        
        # Симулируем прогресс
        if elapsed < 0.2:
            state = 'waiting'
        elif elapsed < 0.5:
            state = 'queuing'
        elif elapsed < 1.0:
            state = 'generating'
        else:
            state = 'success'
            # Генерируем mock URLs
            model_id = task['model_id']
            is_video = 'video' in model_id.lower() or 'video' in task.get('mode', '').lower()
            ext = '.mp4' if is_video else '.png'
            task['result_urls'] = [f"https://example.com/mock/{task_id}{ext}"]
        
        task['status'] = state
        
        result = {
            'ok': True,
            'state': state,
            'taskId': task_id
        }
        
        if state == 'success':
            import json
            result['resultJson'] = json.dumps({
                'resultUrls': task.get('result_urls', [])
            })
        elif state == 'fail':
            result['failCode'] = 'MOCK_ERROR'
            result['failMsg'] = 'Mock failure (for testing)'
        
        return result
    
    def parse_result_urls(self, response: Dict[str, Any]) -> List[str]:
        """Парсит mock resultUrls."""
        if response.get('state') == 'success':
            result_json = response.get('resultJson', '{}')
            try:
                import json
                result_data = json.loads(result_json)
                return result_data.get('resultUrls', [])
            except:
                return []
        return []


def get_enhanced_gateway() -> EnhancedKieGateway:
    """Получает улучшенный gateway (реальный или mock)."""
    if should_use_mock_gateway():
        return MockEnhancedKieGateway()
    else:
        return RealEnhancedKieGateway()

