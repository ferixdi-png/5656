"""
Модуль для многократной генерации с одним запросом.
Поддерживает генерацию нескольких объектов одновременно.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


async def generate_multiple(
    model_id: str,
    base_params: Dict[str, Any],
    count: int,
    variations: Optional[List[Dict[str, Any]]] = None,
    create_task_func: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Генерирует несколько объектов с одним запросом.
    
    Args:
        model_id: ID модели
        base_params: Базовые параметры для всех генераций
        count: Количество объектов для генерации
        variations: Список вариаций параметров (если None, используются базовые)
        create_task_func: Функция для создания задачи генерации
    
    Returns:
        Список результатов генерации
    """
    if count <= 0:
        return []
    
    if count > 10:
        logger.warning(f"⚠️ Запрошено {count} генераций, ограничиваем до 10")
        count = 10
    
    # Подготавливаем параметры для каждой генерации
    tasks_params = []
    
    if variations and len(variations) >= count:
        # Используем предоставленные вариации
        tasks_params = variations[:count]
    else:
        # Создаем вариации на основе базовых параметров
        for i in range(count):
            params = base_params.copy()
            
            # Добавляем вариации, если возможно
            if 'seed' not in params:
                # Используем разные seed для вариаций
                params['seed'] = i + 1
            
            tasks_params.append(params)
    
    # Выполняем параллельную генерацию
    try:
        from parallel_generation import parallel_generate
        
        async def create_task(task_params: Dict[str, Any]) -> Dict[str, Any]:
            """Создает задачу генерации."""
            if create_task_func:
                return await create_task_func(model_id, task_params)
            else:
                # Используем стандартную функцию создания задачи
                from kie_gateway import get_kie_gateway
                gateway = get_kie_gateway()
                return await gateway.create_task(model_id, task_params)
        
        results = await parallel_generate(
            tasks_params,
            create_task,
            max_concurrent=min(count, 5)  # Ограничиваем параллелизм
        )
        
        # Подсчитываем успешные генерации
        successful = sum(1 for r in results if r and r.get('status') == 'success')
        logger.info(f"✅ Многократная генерация завершена: {successful}/{count} успешных")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Ошибка при многократной генерации: {e}", exc_info=True)
        return []


def calculate_batch_price(model_id: str, params: Dict[str, Any], count: int) -> float:
    """
    Рассчитывает стоимость многократной генерации.
    
    Args:
        model_id: ID модели
        params: Параметры генерации
        count: Количество генераций
    
    Returns:
        Общая стоимость
    """
    try:
        from bot_kie import calculate_price_rub
        
        # Рассчитываем стоимость одной генерации
        single_price = calculate_price_rub(model_id, params, is_admin_user=False)
        
        # Общая стоимость
        total_price = single_price * count
        
        # Можно добавить скидку за объем
        if count >= 5:
            total_price *= 0.9  # 10% скидка за 5+ генераций
        elif count >= 3:
            total_price *= 0.95  # 5% скидка за 3+ генераций
        
        return total_price
        
    except Exception as e:
        logger.error(f"❌ Ошибка при расчете стоимости батча: {e}", exc_info=True)
        return 0.0

