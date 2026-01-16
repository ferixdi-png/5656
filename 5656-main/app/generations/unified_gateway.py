"""
TASK 2: Унифицированный gateway для всех генераций KIE.ai
POST /api/v1/jobs/createTask
GET /api/v1/jobs/recordInfo?taskId=...
"""

import os
import asyncio
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class UnifiedKieGateway:
    """
    Унифицированный gateway для всех генераций через KIE API
    Поддерживает callback_url и fallback на polling с backoff
    """
    
    def __init__(self, base_gateway):
        """
        Args:
            base_gateway: Базовый gateway (RealKieGateway или MockKieGateway)
        """
        self.base_gateway = base_gateway
        self.callback_url = os.getenv("KIE_CALLBACK_URL")  # Опциональный callback URL
    
    async def create_task_unified(
        self,
        model_id: str,
        input_params: Dict[str, Any],
        user_id: int = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Создаёт задачу через единый endpoint
        
        Args:
            model_id: ID модели (например, "wan/2-6-text-to-video")
            input_params: Входные параметры
            user_id: ID пользователя (для телеметрии)
            metadata: Дополнительные метаданные
        
        Returns:
            {
                "ok": bool,
                "taskId": str,
                "status": str,
                "telemetry": {
                    "model_id": str,
                    "taskId": str,
                    "create_time": float,
                    "callback_url": Optional[str]
                }
            }
        """
        start_time = time.time()
        telemetry = {
            "model_id": model_id,
            "create_time": start_time,
            "callback_url": self.callback_url if self.callback_url else None
        }
        
        try:
            # Используем callback_url если задан в ENV
            callback_url = self.callback_url if self.callback_url else None
            
            # Создаём задачу через базовый gateway
            result = await self.base_gateway.create_task(
                model_id,
                input_params,
                callback_url=callback_url
            )
            
            elapsed = time.time() - start_time
            telemetry["elapsed"] = elapsed
            
            if result.get('ok'):
                task_id = result.get('taskId')
                telemetry["taskId"] = task_id
                telemetry["status"] = "created"
                
                # Обязательная телеметрия
                logger.info(
                    f"📊 TASK CREATED: model_id={model_id}, taskId={task_id}, "
                    f"elapsed={elapsed:.2f}s, callback_url={callback_url is not None}, "
                    f"user_id={user_id}"
                )
                
                return {
                    "ok": True,
                    "taskId": task_id,
                    "status": result.get('status', 'created'),
                    "telemetry": telemetry
                }
            else:
                error = result.get('error', 'Unknown error')
                telemetry["error"] = error
                telemetry["status"] = "failed"
                
                # Обязательная телеметрия для фейла
                logger.error(
                    f"❌ TASK CREATION FAILED: model_id={model_id}, "
                    f"error={error}, elapsed={elapsed:.2f}s, user_id={user_id}"
                )
                
                return {
                    "ok": False,
                    "error": error,
                    "telemetry": telemetry
                }
                
        except Exception as e:
            elapsed = time.time() - start_time
            telemetry["error"] = str(e)
            telemetry["status"] = "exception"
            telemetry["elapsed"] = elapsed
            
            logger.error(
                f"❌ TASK CREATION EXCEPTION: model_id={model_id}, "
                f"error={e}, elapsed={elapsed:.2f}s, user_id={user_id}",
                exc_info=True
            )
            
            return {
                "ok": False,
                "error": str(e),
                "telemetry": telemetry
            }
    
    async def get_task_status_unified(
        self,
        task_id: str,
        model_id: str = None,
        user_id: int = None,
        wait_time: float = 0.0
    ) -> Dict[str, Any]:
        """
        Получает статус задачи через единый endpoint
        
        Args:
            task_id: ID задачи
            model_id: ID модели (для телеметрии)
            user_id: ID пользователя (для телеметрии)
            wait_time: Время ожидания перед запросом (для телеметрии)
        
        Returns:
            {
                "ok": bool,
                "state": str,  # waiting, queuing, generating, success, failed
                "resultJson": Optional[str],
                "error": Optional[str],
                "telemetry": {
                    "taskId": str,
                    "state": str,
                    "wait_time": float,
                    "poll_time": float
                }
            }
        """
        poll_start = time.time()
        telemetry = {
            "taskId": task_id,
            "wait_time": wait_time,
            "poll_time": poll_start
        }
        
        try:
            result = await self.base_gateway.get_task(task_id)
            poll_elapsed = time.time() - poll_start
            
            state = result.get('state', 'unknown')
            telemetry["state"] = state
            telemetry["poll_elapsed"] = poll_elapsed
            
            # Обязательная телеметрия
            logger.info(
                f"📊 TASK STATUS: taskId={task_id}, state={state}, "
                f"wait_time={wait_time:.2f}s, poll_elapsed={poll_elapsed:.2f}s, "
                f"model_id={model_id}, user_id={user_id}"
            )
            
            if not result.get('ok'):
                error = result.get('error', 'Unknown error')
                telemetry["error"] = error
                
                # Телеметрия для фейла
                logger.error(
                    f"❌ TASK STATUS FAILED: taskId={task_id}, error={error}, "
                    f"state={state}, model_id={model_id}, user_id={user_id}"
                )
            
            result["telemetry"] = telemetry
            return result
            
        except Exception as e:
            poll_elapsed = time.time() - poll_start
            telemetry["error"] = str(e)
            telemetry["poll_elapsed"] = poll_elapsed
            
            logger.error(
                f"❌ TASK STATUS EXCEPTION: taskId={task_id}, error={e}, "
                f"model_id={model_id}, user_id={user_id}",
                exc_info=True
            )
            
            return {
                "ok": False,
                "error": str(e),
                "state": "error",
                "telemetry": telemetry
            }
    
    async def poll_task_with_backoff(
        self,
        task_id: str,
        model_id: str,
        user_id: int,
        max_polls: int = 300,
        initial_delay: float = 2.0,
        max_delay: float = 30.0,
        backoff_multiplier: float = 1.5
    ) -> Dict[str, Any]:
        """
        Polling задачи с экспоненциальным backoff
        
        Args:
            task_id: ID задачи
            model_id: ID модели
            user_id: ID пользователя
            max_polls: Максимальное количество опросов
            initial_delay: Начальная задержка (секунды)
            max_delay: Максимальная задержка (секунды)
            backoff_multiplier: Множитель для backoff
        
        Returns:
            Результат последнего запроса статуса
        """
        delay = initial_delay
        total_wait = 0.0
        
        for poll_num in range(max_polls):
            # Получаем статус
            result = await self.get_task_status_unified(
                task_id,
                model_id=model_id,
                user_id=user_id,
                wait_time=total_wait
            )
            
            if not result.get('ok'):
                # Ошибка запроса - продолжаем с backoff
                logger.warning(
                    f"⚠️ Poll {poll_num + 1}/{max_polls} failed for taskId={task_id}, "
                    f"retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                delay = min(delay * backoff_multiplier, max_delay)
                total_wait += delay
                continue
            
            state = result.get('state', 'unknown')
            
            # Финальные состояния - прекращаем polling
            if state in ['success', 'failed']:
                logger.info(
                    f"✅ Polling completed: taskId={task_id}, state={state}, "
                    f"total_polls={poll_num + 1}, total_wait={total_wait:.1f}s"
                )
                return result
            
            # Промежуточные состояния - продолжаем с backoff
            if state in ['waiting', 'queuing', 'generating']:
                await asyncio.sleep(delay)
                delay = min(delay * backoff_multiplier, max_delay)
                total_wait += delay
                continue
            
            # Неизвестное состояние - продолжаем с backoff
            logger.warning(
                f"⚠️ Unknown state '{state}' for taskId={task_id}, "
                f"continuing polling (poll {poll_num + 1}/{max_polls})"
            )
            await asyncio.sleep(delay)
            delay = min(delay * backoff_multiplier, max_delay)
            total_wait += delay
        
        # Достигнут максимум опросов
        logger.error(
            f"❌ Max polls reached for taskId={task_id}, "
            f"total_polls={max_polls}, total_wait={total_wait:.1f}s"
        )
        
        # Возвращаем последний результат
        return await self.get_task_status_unified(
            task_id,
            model_id=model_id,
            user_id=user_id,
            wait_time=total_wait
        )


def get_unified_gateway():
    """Получает унифицированный gateway"""
    from kie_gateway import get_kie_gateway
    base_gateway = get_kie_gateway()
    return UnifiedKieGateway(base_gateway)







