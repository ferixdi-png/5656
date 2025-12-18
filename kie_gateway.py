"""
Gateway для работы с KIE API с поддержкой моков для тестирования.
Позволяет переключаться между реальным и моковым клиентом в зависимости от режима.
"""

import asyncio
import hashlib
import logging
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from config_runtime import should_use_mock_gateway
from kie_client import get_client, KIEClient

logger = logging.getLogger(__name__)


class KieGateway(ABC):
    """Абстрактный интерфейс для работы с KIE API."""
    
    @abstractmethod
    async def create_task(self, api_model: str, input: Dict[str, Any], callback_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Создает задачу генерации.
        
        Args:
            api_model: API model ID (например, "wan/2-6-text-to-video")
            input: Входные параметры для генерации
            callback_url: Опциональный URL для callback (если поддерживается)
        
        Returns:
            {
                "ok": bool,
                "taskId": str,
                "status": str
            }
        """
        pass
    
    @abstractmethod
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Получает статус задачи.
        
        Args:
            task_id: ID задачи
        
        Returns:
            {
                "ok": bool,
                "state": str,  # waiting, queuing, generating, success, failed
                "resultJson": str,  # JSON строка с результатами
                "error": str  # если ok=False
            }
        """
        pass
    
    @abstractmethod
    async def list_models(self) -> List[Dict[str, Any]]:
        """Получает список моделей."""
        pass
    
    @abstractmethod
    async def healthcheck(self) -> bool:
        """Проверяет доступность API."""
        pass


class RealKieGateway(KieGateway):
    """Реальный gateway, использующий настоящий KIE API."""
    
    def __init__(self):
        self.client: KIEClient = get_client()
    
    async def create_task(self, api_model: str, input: Dict[str, Any], callback_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Создает задачу через реальный KIE API.
        POST https://api.kie.ai/api/v1/jobs/createTask
        """
        # Используем существующий метод клиента
        result = await self.client.create_task(api_model, input)
        return result
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Получает статус задачи через реальный KIE API.
        GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId=...
        """
        return await self.client.get_task_status(task_id)
    
    # Обратная совместимость
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Алиас для get_task (обратная совместимость)."""
        return await self.get_task(task_id)
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """Получает список моделей через реальный KIE API."""
        return await self.client.list_models()
    
    async def healthcheck(self) -> bool:
        """Проверяет доступность реального API."""
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception as e:
            logger.warning(f"Healthcheck failed: {e}")
            return False


class MockKieGateway(KieGateway):
    """
    Моковый gateway для тестирования.
    НИКОГДА не делает реальных HTTP запросов.
    Возвращает детерминированные результаты.
    """
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._task_counter = 0
    
    def _generate_mock_url(self, model_id: str, task_id: str, index: int = 0) -> str:
        """Генерирует детерминированный mock URL."""
        # Определяем расширение по типу модели
        is_video = any(keyword in model_id.lower() for keyword in [
            'video', 'sora', 'kling', 'wan', 'hailuo', 'bytedance'
        ])
        ext = '.mp4' if is_video else '.png'
        
        # Создаем хеш для детерминированности
        hash_input = f"{model_id}:{task_id}:{index}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        
        return f"https://example.com/mock/{model_id.replace('/', '_')}/{hash_value}{ext}"
    
    async def create_task(self, api_model: str, input: Dict[str, Any], callback_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Создает моковую задачу.
        НИКОГДА не делает реальных HTTP запросов.
        Симулирует задержку 50-150мс для тестирования асинхронности.
        """
        # Симулируем задержку сети
        delay = 0.05 + (hash(api_model) % 100) / 1000  # 50-150ms
        await asyncio.sleep(delay)
        
        self._task_counter += 1
        task_id = f"mock_task_{self._task_counter}_{hash(api_model) % 10000}"
        
        # Сохраняем задачу
        self._tasks[task_id] = {
            'task_id': task_id,
            'api_model': api_model,
            'input': input,
            'callback_url': callback_url,
            'status': 'waiting',
            'created_at': asyncio.get_event_loop().time()
        }
        
        logger.info(f"🔧 MOCK: Created task {task_id} for model {api_model}")
        
        return {
            'ok': True,
            'taskId': task_id,
            'status': 'waiting'
        }
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Получает статус моковой задачи.
        Автоматически переводит задачу в 'success' через небольшую задержку.
        """
        if task_id not in self._tasks:
            return {
                'ok': False,
                'error': f'Task {task_id} not found',
                'status': 'fail'
            }
        
        task = self._tasks[task_id]
        elapsed = asyncio.get_event_loop().time() - task['created_at']
        
        # Симулируем прогресс: waiting -> queuing -> generating -> success
        if elapsed < 0.1:
            state = 'waiting'
        elif elapsed < 0.2:
            state = 'queuing'
        elif elapsed < 0.5:
            state = 'generating'
        else:
            state = 'success'
            # Генерируем mock URLs
            api_model = task.get('api_model', 'unknown')
            result_urls = [
                self._generate_mock_url(api_model, task_id, i)
                for i in range(1)  # По умолчанию 1 результат
            ]
            task['result_urls'] = result_urls
        
        task['status'] = state
        
        import json
        if state == 'success':
            return {
                'ok': True,
                'state': state,
                'resultJson': json.dumps({
                    'resultUrls': task.get('result_urls', [])
                })
            }
        elif state == 'fail':
            return {
                'ok': False,
                'state': state,
                'error': 'Mock failure (for testing)'
            }
        
        return {
            'ok': True,
            'state': state
        }
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Возвращает моковый список моделей.
        Использует реальные ID моделей из kie_models.py для совместимости.
        """
        try:
            from kie_models import KIE_MODELS
            # Возвращаем упрощенную структуру
            return [
                {
                    'id': model['id'],
                    'name': model.get('name', model['id']),
                    'category': model.get('category', 'unknown')
                }
                for model in KIE_MODELS[:10]  # Первые 10 для скорости
            ]
        except ImportError:
            # Fallback если kie_models недоступен
            return [
                {'id': 'z-image', 'name': 'Z Image', 'category': 'image'},
                {'id': 'flux-2-pro-text-to-image', 'name': 'Flux 2 Pro', 'category': 'image'},
            ]
    
    async def healthcheck(self) -> bool:
        """Моковый healthcheck всегда возвращает True."""
        return True


# Глобальный экземпляр gateway
_gateway_instance: Optional[KieGateway] = None


def get_kie_gateway() -> KieGateway:
    """
    Фабрика для получения gateway.
    Возвращает MockKieGateway если:
    - TEST_MODE=1, или
    - ALLOW_REAL_GENERATION=0
    Иначе возвращает RealKieGateway.
    """
    global _gateway_instance
    
    if _gateway_instance is None:
        if should_use_mock_gateway():
            logger.info("🔧 Using MockKieGateway (TEST_MODE or ALLOW_REAL_GENERATION=0)")
            _gateway_instance = MockKieGateway()
        else:
            logger.info("✅ Using RealKieGateway")
            _gateway_instance = RealKieGateway()
    
    return _gateway_instance


def reset_gateway():
    """Сбрасывает глобальный экземпляр gateway (для тестов)."""
    global _gateway_instance
    _gateway_instance = None

