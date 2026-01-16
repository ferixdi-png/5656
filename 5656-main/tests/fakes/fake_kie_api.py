"""
Fake KIE API для тестов
НИКОГДА не делает реальных HTTP запросов
"""

import asyncio
import os
import time
from typing import Dict, Any, Optional
from enum import Enum


class TaskState(Enum):
    WAITING = "waiting"
    QUEUING = "queuing"
    GENERATING = "generating"
    SUCCESS = "success"
    FAILED = "failed"


class FakeKieAPI:
    """Fake KIE API - полностью моковый"""
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._task_counter = 0
        self._fail_mode = False
        self._timeout_mode = False
    
    def set_fail_mode(self, enabled: bool = True):
        """Включает режим фейла"""
        self._fail_mode = enabled
    
    def set_timeout_mode(self, enabled: bool = True):
        """Включает режим таймаута"""
        self._timeout_mode = enabled
    
    async def create_task(self, model_id: str, input_data: Dict[str, Any], callback_url: Optional[str] = None) -> Dict[str, Any]:
        """Создаёт задачу (fake)"""
        if self._fail_mode:
            return {
                "ok": False,
                "error": "Fake API failure mode"
            }
        
        if self._timeout_mode:
            # Управляемый таймаут для тестов (не убивает пайплайн)
            sleep_seconds = float(os.getenv("FAKE_TIMEOUT_SLEEP", "0.2"))
            await asyncio.sleep(sleep_seconds)  # Симуляция таймаута
        
        self._task_counter += 1
        task_id = f"fake_task_{self._task_counter}"
        
        self._tasks[task_id] = {
            "taskId": task_id,
            "model_id": model_id,
            "input": input_data,
            "state": TaskState.WAITING.value,
            "created_at": time.time(),
            "callback_url": callback_url
        }
        
        return {
            "ok": True,
            "taskId": task_id,
            "status": "created"
        }
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Получает статус задачи (fake)"""
        if task_id not in self._tasks:
            return {
                "ok": False,
                "error": "Task not found"
            }
        
        task = self._tasks[task_id]
        elapsed = time.time() - task["created_at"]
        
        # Симуляция прогресса
        if elapsed < 1:
            task["state"] = TaskState.WAITING.value
        elif elapsed < 2:
            task["state"] = TaskState.QUEUING.value
        elif elapsed < 5:
            task["state"] = TaskState.GENERATING.value
        else:
            if self._fail_mode:
                task["state"] = TaskState.FAILED.value
                return {
                    "ok": False,
                    "state": TaskState.FAILED.value,
                    "error": "Fake API failure"
                }
            else:
                task["state"] = TaskState.SUCCESS.value
                return {
                    "ok": True,
                    "state": TaskState.SUCCESS.value,
                    "resultJson": '{"url": "https://fake-result.com/image.jpg"}'
                }
        
        return {
            "ok": True,
            "state": task["state"]
        }
