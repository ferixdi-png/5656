"""
Модуль для параллельной генерации нескольких запросов одновременно.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


async def parallel_generate(
    tasks: List[Dict[str, Any]],
    generate_func: Callable,
    max_concurrent: int = 5,
    progress_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
    """
    Выполняет параллельную генерацию нескольких задач.
    
    Args:
        tasks: Список задач для генерации (каждая задача - словарь с параметрами)
        generate_func: Асинхронная функция для генерации одной задачи
        max_concurrent: Максимальное количество одновременных генераций
        progress_callback: Функция обратного вызова для уведомления о прогрессе
    
    Returns:
        Список результатов генерации
    """
    if not tasks:
        return []
    
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def generate_with_semaphore(task_data: Dict[str, Any], task_index: int) -> Dict[str, Any]:
        """Генерирует одну задачу с ограничением через семафор."""
        async with semaphore:
            try:
                logger.info(f"🚀 Начало генерации задачи {task_index + 1}/{len(tasks)}")
                
                if progress_callback:
                    await progress_callback(task_index, len(tasks), "started")
                
                result = await generate_func(task_data)
                
                if progress_callback:
                    await progress_callback(task_index, len(tasks), "completed")
                
                logger.info(f"✅ Задача {task_index + 1}/{len(tasks)} завершена")
                return {
                    'task_index': task_index,
                    'task_data': task_data,
                    'result': result,
                    'status': 'success',
                    'timestamp': datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"❌ Ошибка при генерации задачи {task_index + 1}/{len(tasks)}: {e}", exc_info=True)
                
                if progress_callback:
                    await progress_callback(task_index, len(tasks), "error", str(e))
                
                return {
                    'task_index': task_index,
                    'task_data': task_data,
                    'result': None,
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
    
    # Создаем задачи для параллельного выполнения
    generation_tasks = [
        generate_with_semaphore(task, idx)
        for idx, task in enumerate(tasks)
    ]
    
    # Выполняем все задачи параллельно
    logger.info(f"🔄 Запуск параллельной генерации {len(tasks)} задач (макс. одновременных: {max_concurrent})")
    results = await asyncio.gather(*generation_tasks, return_exceptions=True)
    
    # Обрабатываем исключения
    processed_results = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"❌ Исключение при генерации задачи {idx + 1}: {result}", exc_info=True)
            processed_results.append({
                'task_index': idx,
                'task_data': tasks[idx],
                'result': None,
                'status': 'error',
                'error': str(result),
                'timestamp': datetime.now().isoformat()
            })
        else:
            processed_results.append(result)
    
    # Сортируем результаты по индексу задачи
    processed_results.sort(key=lambda x: x['task_index'])
    
    successful = sum(1 for r in processed_results if r['status'] == 'success')
    failed = len(processed_results) - successful
    
    logger.info(f"✅ Параллельная генерация завершена: {successful} успешных, {failed} ошибок")
    
    return processed_results


async def batch_generate(
    model_id: str,
    params_list: List[Dict[str, Any]],
    create_task_func: Callable,
    max_concurrent: int = 5,
    progress_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
    """
    Выполняет пакетную генерацию для одной модели с разными параметрами.
    
    Args:
        model_id: ID модели
        params_list: Список наборов параметров для генерации
        create_task_func: Функция для создания задачи генерации
        max_concurrent: Максимальное количество одновременных генераций
        progress_callback: Функция обратного вызова для уведомления о прогрессе
    
    Returns:
        Список результатов генерации
    """
    tasks = [
        {'model_id': model_id, 'params': params}
        for params in params_list
    ]
    
    async def generate_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Генерирует одну задачу."""
        return await create_task_func(
            task_data['model_id'],
            task_data['params']
        )
    
    return await parallel_generate(
        tasks,
        generate_task,
        max_concurrent=max_concurrent,
        progress_callback=progress_callback
    )

