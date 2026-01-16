"""
KIE Stub - симулятор KIE API для тестов
Переключение через env KIE_STUB=1
"""

import os
import asyncio
import logging
import uuid
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class KIEStub:
    """Симулятор KIE API для тестов"""
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._task_states = {}  # task_id -> state progression
    
    async def create_task(
        self,
        model_id: str,
        input_data: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создать задачу (симуляция)
        
        Returns:
            {'ok': True, 'taskId': str}
        """
        task_id = str(uuid.uuid4())
        
        # Симулируем создание задачи
        self._tasks[task_id] = {
            'task_id': task_id,
            'model_id': model_id,
            'input_data': input_data,
            'callback_url': callback_url,
            'created_at': datetime.now().isoformat(),
            'state': 'pending'
        }
        
        # Запускаем симуляцию обработки (в фоне)
        asyncio.create_task(self._simulate_processing(task_id))
        
        logger.info(f"[STUB] Task created: {task_id} for model {model_id}")
        
        return {
            'ok': True,
            'taskId': task_id
        }
    
    async def _simulate_processing(self, task_id: str):
        """Симулировать обработку задачи"""
        # pending -> processing -> completed
        await asyncio.sleep(1)  # pending
        
        if task_id in self._tasks:
            self._tasks[task_id]['state'] = 'processing'
            logger.debug(f"[STUB] Task {task_id} -> processing")
        
        await asyncio.sleep(2)  # processing
        
        if task_id in self._tasks:
            # Генерируем фиктивные URLs
            task = self._tasks[task_id]
            model_id = task['model_id']
            
            # Генерируем результат в зависимости от типа модели
            result_urls = []
            if 'image' in model_id.lower() or 'text-to-image' in model_id.lower():
                result_urls = [f"https://example.com/generated/image_{task_id}.png"]
            elif 'video' in model_id.lower() or 'text-to-video' in model_id.lower():
                result_urls = [f"https://example.com/generated/video_{task_id}.mp4"]
            elif 'audio' in model_id.lower() or 'text-to-audio' in model_id.lower():
                result_urls = [f"https://example.com/generated/audio_{task_id}.mp3"]
            else:
                result_urls = [f"https://example.com/generated/result_{task_id}.txt"]
            
            self._tasks[task_id]['state'] = 'completed'
            self._tasks[task_id]['result_urls'] = result_urls
            self._tasks[task_id]['resultJson'] = json.dumps({'urls': result_urls})
            logger.debug(f"[STUB] Task {task_id} -> completed")
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Получить статус задачи (симуляция)
        
        Returns:
            {
                'ok': True,
                'state': str ('pending', 'processing', 'completed', 'failed'),
                'resultUrls': List[str] (если completed),
                'resultJson': str (если completed)
            }
        """
        if task_id not in self._tasks:
            return {
                'ok': False,
                'state': 'failed',
                'error': 'Task not found'
            }
        
        task = self._tasks[task_id]
        state = task.get('state', 'pending')
        
        result = {
            'ok': True,
            'state': state
        }
        
        if state == 'completed':
            result['resultUrls'] = task.get('result_urls', [])
            result['resultJson'] = task.get('resultJson', '{}')
        elif state == 'failed':
            result['failCode'] = 'STUB_ERROR'
            result['failMsg'] = 'Simulated error'
        
        return result
    
    async def wait_for_task(
        self,
        task_id: str,
        timeout: int = 900,
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """Ждать завершения задачи (симуляция)"""
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
                await asyncio.sleep(poll_interval)
                continue
            
            state = status.get('state', 'pending')
            
            if state in ('completed', 'failed'):
                return status
            
            await asyncio.sleep(poll_interval)


def get_kie_client_or_stub():
    """Получить KIE клиент или stub в зависимости от env"""
    use_stub = os.getenv('KIE_STUB', '0') == '1'
    
    if use_stub:
        logger.info("[STUB] Using KIE stub (KIE_STUB=1)")
        return KIEStub()
    else:
        from app.integrations.kie_client import KIEClient
        return KIEClient()


