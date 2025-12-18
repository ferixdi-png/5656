"""
Модуль для предпросмотра результатов генерации.
"""

import logging
from typing import Dict, Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


async def generate_preview(
    model_id: str,
    params: Dict[str, Any],
    preview_type: str = 'thumbnail'
) -> Optional[Dict[str, Any]]:
    """
    Генерирует предпросмотр результата.
    
    Args:
        model_id: ID модели
        params: Параметры генерации
        preview_type: Тип предпросмотра ('thumbnail', 'low_quality', 'sample')
    
    Returns:
        Словарь с данными предпросмотра или None
    """
    try:
        # Создаем параметры для предпросмотра (низкое качество для скорости)
        preview_params = params.copy()
        
        # Уменьшаем качество для предпросмотра
        if 'resolution' in preview_params:
            if '1080' in str(preview_params['resolution']):
                preview_params['resolution'] = '480p'
            elif '720' in str(preview_params['resolution']):
                preview_params['resolution'] = '360p'
        
        # Добавляем флаг предпросмотра
        preview_params['preview'] = True
        preview_params['preview_type'] = preview_type
        
        # Создаем задачу предпросмотра
        from kie_gateway import get_kie_gateway
        gateway = get_kie_gateway()
        
        result = await gateway.create_task(model_id, preview_params)
        
        if result.get('ok'):
            return {
                'task_id': result.get('taskId'),
                'preview_type': preview_type,
                'params': preview_params
            }
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при генерации предпросмотра: {e}", exc_info=True)
        return None


async def get_preview_url(task_id: str) -> Optional[str]:
    """
    Получает URL предпросмотра по task_id.
    
    Args:
        task_id: ID задачи
    
    Returns:
        URL предпросмотра или None
    """
    try:
        from kie_gateway import get_kie_gateway
        gateway = get_kie_gateway()
        
        status = await gateway.get_task_status(task_id)
        
        if status.get('ok') and status.get('state') == 'success':
            result_data = status.get('result', {})
            preview_urls = result_data.get('previewUrls', [])
            
            if preview_urls:
                return preview_urls[0]
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении URL предпросмотра: {e}", exc_info=True)
        return None


def create_thumbnail_from_url(image_url: str, size: tuple = (200, 200)) -> Optional[str]:
    """
    Создает миниатюру из URL изображения.
    
    Args:
        image_url: URL изображения
        size: Размер миниатюры (width, height)
    
    Returns:
        URL миниатюры или None
    """
    # В реальной реализации здесь будет создание миниатюры
    # Пока возвращаем оригинальный URL
    logger.info(f"🖼️ Создание миниатюры {size} из {image_url}")
    return image_url

