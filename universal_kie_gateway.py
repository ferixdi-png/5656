"""
Универсальный Gateway для работы с KIE AI API.
Поддерживает createTask + polling и callback_url.
Работает со всеми моделями через единый интерфейс.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from config_runtime import should_use_mock_gateway
from kie_client import get_client, KIEClient

logger = logging.getLogger(__name__)


class UniversalKieGateway(ABC):
    """Универсальный интерфейс для работы с KIE AI."""
    
    @abstractmethod
    async def create_task(
        self,
        model_id: str,
        mode: str,
        input_data: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создает задачу генерации.
        
        Args:
            model_id: Реальный API model string
            mode: ID mode (text_to_video, image_to_image и т.д.)
            input_data: Входные данные согласно input_schema
            callback_url: URL для callback (опционально)
        
        Returns:
            {'ok': True, 'taskId': '...'} или {'ok': False, 'error': '...'}
        """
        pass
    
    @abstractmethod
    async def get_status(self, task_id: str) -> Dict[str, Any]:
        """
        Получает статус задачи через recordInfo.
        
        Args:
            task_id: ID задачи
        
        Returns:
            {'ok': True, 'state': '...', 'resultJson': '...'} или {'ok': False, 'error': '...'}
        """
        pass
    
    @abstractmethod
    def parse_result_urls(self, response: Dict[str, Any]) -> List[str]:
        """
        Парсит resultUrls из ответа API.
        
        Args:
            response: Ответ от get_status
        
        Returns:
            Список URL результатов
        """
        pass


class RealUniversalKieGateway(UniversalKieGateway):
    """Реальный gateway для работы с KIE AI API."""
    
    def __init__(self):
        self.client: KIEClient = get_client()
    
    async def create_task(
        self,
        model_id: str,
        mode: str,
        input_data: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создает задачу через KIE API."""
        try:
            # Используем create_task из kie_client с поддержкой callback_url
            result = await self.client.create_task(model_id, input_data, callback_url)
            
            if result.get('ok'):
                logger.info(f"✅ Задача создана: {result.get('taskId')} для модели {model_id} (mode: {mode})")
            else:
                logger.error(f"❌ Ошибка создания задачи: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Исключение при создании задачи: {e}", exc_info=True)
            return {
                'ok': False,
                'error': str(e)
            }
    
    async def get_status(self, task_id: str) -> Dict[str, Any]:
        """Получает статус через recordInfo."""
        try:
            result = await self.client.get_task_status(task_id)
            return result
            
        except Exception as e:
            logger.error(f"❌ Исключение при получении статуса: {e}", exc_info=True)
            return {
                'ok': False,
                'error': str(e),
                'state': 'fail'
            }
    
    def parse_result_urls(self, response: Dict[str, Any]) -> List[str]:
        """Парсит resultUrls из ответа."""
        try:
            if not response.get('ok'):
                return []
            
            # Пробуем разные форматы ответа
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


class MockUniversalKieGateway(UniversalKieGateway):
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
        await asyncio.sleep(0.1)  # Симуляция задержки
        
        self._task_counter += 1
        task_id = f"mock_{self._task_counter}_{hash(model_id) % 10000}"
        
        self._tasks[task_id] = {
            'task_id': task_id,
            'model_id': model_id,
            'mode': mode,
            'input_data': input_data,
            'status': 'waiting',
            'created_at': asyncio.get_event_loop().time()
        }
        
        logger.info(f"🔧 MOCK: Создана задача {task_id} для {model_id} (mode: {mode})")
        
        return {
            'ok': True,
            'taskId': task_id
        }
    
    async def get_status(self, task_id: str) -> Dict[str, Any]:
        """Получает mock статус."""
        if task_id not in self._tasks:
            return {
                'ok': False,
                'error': f'Task {task_id} not found',
                'state': 'fail'
            }
        
        task = self._tasks[task_id]
        elapsed = asyncio.get_event_loop().time() - task['created_at']
        
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


def get_universal_gateway() -> UniversalKieGateway:
    """Получает универсальный gateway (реальный или mock)."""
    if should_use_mock_gateway():
        return MockUniversalKieGateway()
    else:
        return RealUniversalKieGateway()

