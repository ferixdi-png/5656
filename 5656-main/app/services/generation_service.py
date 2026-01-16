"""
Generation service - работа с генерациями через единый API
Polling без блокировки event loop
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.utils.logging_config import get_logger
from app.integrations.kie_stub import get_kie_client_or_stub
from app.storage import get_storage
from app.storage.status import normalize_job_status
from app.utils.webhook import build_kie_callback_url

logger = get_logger(__name__)


class GenerationService:
    """Сервис для работы с генерациями"""
    
    def __init__(self):
        self.kie_client = get_kie_client_or_stub()
        self.storage = get_storage()
        self._polling_tasks: Dict[str, asyncio.Task] = {}
    
    async def create_generation(
        self,
        user_id: int,
        model_id: str,
        model_name: str,
        params: Dict[str, Any],
        price: float
    ) -> str:
        """
        Создать генерацию
        
        Returns:
            job_id: str - ID задачи
        """
        # Создаем задачу в KIE (с реальным callback URL, если задан)
        callback_url = build_kie_callback_url()
        result = await self.kie_client.create_task(model_id, params, callback_url=callback_url or None)
        
        if not result.get('ok'):
            error = result.get('error', 'Unknown error')
            logger.error(f"[GEN] Failed to create task: {error}")
            raise RuntimeError(f"Failed to create generation task: {error}")
        
        task_id = result.get('taskId')
        if not task_id:
            raise RuntimeError("No taskId in KIE response")
        
        # Сохраняем job в storage
        # Используем task_id как job_id для простоты
        job_id = await self.storage.add_generation_job(
            user_id=user_id,
            model_id=model_id,
            model_name=model_name,
            params=params,
            price=price,
            task_id=task_id,  # external_task_id будет сохранен как task_id
            status="queued"
        )
        
        logger.info(f"[GEN] Generation created: job_id={job_id}, task_id={task_id}, user_id={user_id}")
        
        return job_id
    
    async def start_polling(
        self,
        job_id: str,
        on_progress: Optional[callable] = None,
        on_complete: Optional[callable] = None,
        on_error: Optional[callable] = None
    ) -> None:
        """
        Начать polling задачи (без блокировки event loop)
        
        Args:
            job_id: ID задачи
            on_progress: Callback для обновления прогресса (state, message)
            on_complete: Callback при завершении (result_urls)
            on_error: Callback при ошибке (error_message)
        """
        if job_id in self._polling_tasks:
            logger.warning(f"[GEN] Polling already started for job {job_id}")
            return
        
        async def _poll_task():
            """Polling задача в фоне"""
            try:
                job = await self.storage.get_job(job_id)
                if not job:
                    logger.error(f"[GEN] Job {job_id} not found")
                    if on_error:
                        await on_error("Job not found")
                    return
                
                # Получаем external_task_id (от KIE API)
                task_id = job.get('external_task_id') or job.get('task_id')
                if not task_id:
                    logger.error(f"[GEN] No task_id in job {job_id}, job={job}")
                    if on_error:
                        await on_error("No task_id")
                    return
                
                # Polling с обновлением статуса
                timeout = 900  # 15 минут
                poll_interval = 3  # 3 секунды
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > timeout:
                        timeout_message = "Task timed out while waiting for completion."
                        await self.storage.update_job_status(job_id, "failed", error_message=timeout_message)
                        if on_error:
                            await on_error(timeout_message)
                        break
                    
                    # CRITICAL FIX: Check storage first (callback may have updated it)
                    # This prevents infinite polling if KIE API is stuck but callback arrived
                    current_job = await self.storage.get_job(job_id)
                    if current_job:
                        storage_status = current_job.get('status')
                        if storage_status in ('done', 'failed'):
                            # Callback already updated to terminal state
                            logger.info(f"[GEN] Storage already has terminal status {storage_status} for job {job_id}")
                            if storage_status == 'done':
                                result_urls = current_job.get('result_urls', [])
                                if on_progress:
                                    await on_progress('done', 'Готово')
                                if on_complete:
                                    await on_complete(result_urls)
                                break
                            else:  # failed
                                error_msg = current_job.get('error_message', 'Generation failed.')
                                if on_progress:
                                    await on_progress('failed', 'Ошибка')
                                if on_error:
                                    await on_error(error_msg)
                                break
                    
                    # Получаем статус от KIE API (fallback if callback hasn't arrived yet)
                    status = await self.kie_client.get_task_status(task_id)
                    
                    if not status.get('ok'):
                        # Ошибка получения статуса - продолжаем polling
                        await asyncio.sleep(poll_interval)
                        continue
                    
                    state = status.get('state', 'pending')
                    normalized_state = normalize_job_status(state)
                    
                    # Обновляем статус в storage
                    await self.storage.update_job_status(
                        job_id,
                        normalized_state,
                        result_urls=status.get('resultUrls', []),
                        error_message=status.get('failMsg')
                    )
                    
                    # Вызываем callback прогресса
                    if on_progress:
                        progress_messages = {
                            'queued': 'В очереди',
                            'running': 'В работе',
                            'done': 'Готово',
                            'failed': 'Ошибка'
                        }
                        message = progress_messages.get(normalized_state, normalized_state)
                        await on_progress(normalized_state, message)
                    
                    if normalized_state == 'done':
                        result_urls = status.get('resultUrls', [])
                        if on_complete:
                            await on_complete(result_urls)
                        break
                    
                    if normalized_state == 'failed':
                        error_msg = status.get('failMsg', 'Generation failed.')
                        if on_error:
                            await on_error(error_msg)
                        break
                    
                    # pending или processing - продолжаем polling
                    await asyncio.sleep(poll_interval)
            
            except Exception as e:
                error_message = f"Unexpected error while polling job: {e}"
                logger.error(f"[GEN] Polling error for job {job_id}: {e}", exc_info=True)
                await self.storage.update_job_status(job_id, "failed", error_message=error_message)
                if on_error:
                    await on_error(error_message)
            finally:
                # Удаляем задачу из списка
                self._polling_tasks.pop(job_id, None)
        
        # Запускаем polling в фоне
        task = asyncio.create_task(_poll_task())
        self._polling_tasks[job_id] = task
    
    async def wait_for_generation(
        self,
        job_id: str,
        timeout: int = 900
    ) -> Dict[str, Any]:
        """
        Ждать завершения генерации (блокирующий вариант)
        
        Returns:
            {
                'ok': bool,
                'result_urls': List[str] (если ok),
                'error': str (если не ok)
            }
        """
        job = await self.storage.get_job(job_id)
        if not job:
            return {
                'ok': False,
                'error': 'Job not found'
            }
        
        # Получаем external_task_id (от KIE API)
        task_id = job.get('external_task_id') or job.get('task_id')
        if not task_id:
            return {
                'ok': False,
                'error': 'No task_id'
            }
        
        # Используем wait_for_task из клиента
        try:
            result = await self.kie_client.wait_for_task(task_id, timeout=timeout)
            
            normalized_state = normalize_job_status(result.get('state', 'failed'))
            if normalized_state == 'done':
                result_urls = result.get('resultUrls', [])
                await self.storage.update_job_status(job_id, 'done', result_urls=result_urls)
                return {
                    'ok': True,
                    'result_urls': result_urls
                }
            error = result.get('error') or result.get('failMsg', 'Generation failed.')
            await self.storage.update_job_status(job_id, 'failed', error_message=error)
            return {
                'ok': False,
                'error': error
            }
        except Exception as e:
            error_message = f"Unexpected error while waiting for generation: {e}"
            logger.error(f"[GEN] Wait error for job {job_id}: {e}", exc_info=True)
            await self.storage.update_job_status(job_id, 'failed', error_message=error_message)
            return {
                'ok': False,
                'error': error_message
            }
    
    async def cancel_generation(self, job_id: str) -> bool:
        """Отменить генерацию"""
        try:
            await self.storage.update_job_status(job_id, "canceled")
            
            # Отменяем polling задачу если есть
            if job_id in self._polling_tasks:
                task = self._polling_tasks[job_id]
                task.cancel()
                self._polling_tasks.pop(job_id, None)
            
            return True
        except Exception as e:
            logger.error(f"[GEN] Failed to cancel job {job_id}: {e}")
            return False


def get_generation_service() -> GenerationService:
    """Получить generation service (singleton)"""
    # TODO: можно добавить singleton если нужно
    return GenerationService()
