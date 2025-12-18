"""
Обработка ошибок API KIE AI.
Обрабатывает статусы: waiting, queuing, generating, success, failed.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def handle_api_error(
    response: Dict[str, Any],
    model_id: str,
    mode: str,
    user_lang: str = 'ru'
) -> str:
    """
    Обрабатывает ошибку API и возвращает понятное сообщение для пользователя.
    
    Args:
        response: Ответ от API с ошибкой
        model_id: ID модели
        mode: ID mode
        user_lang: Язык пользователя
    
    Returns:
        Понятное сообщение об ошибке
    """
    error_code = response.get('failCode') or response.get('code') or 'UNKNOWN'
    error_msg = response.get('failMsg') or response.get('error') or response.get('msg') or 'Unknown error'
    
    # Логируем детальную ошибку
    logger.error(
        f"❌ API Error для {model_id}:{mode}: "
        f"code={error_code}, message={error_msg}"
    )
    
    # Переводим код ошибки в понятное сообщение
    error_messages = {
        'INVALID_INPUT': 'Неверные параметры запроса',
        'INSUFFICIENT_CREDITS': 'Недостаточно кредитов',
        'MODEL_NOT_FOUND': 'Модель не найдена',
        'RATE_LIMIT': 'Превышен лимит запросов',
        'TIMEOUT': 'Превышено время ожидания',
        'SERVER_ERROR': 'Ошибка сервера',
        'VALIDATION_ERROR': 'Ошибка валидации параметров'
    }
    
    user_message = error_messages.get(error_code, error_msg)
    
    if user_lang == 'ru':
        return (
            f"❌ <b>Генерация не удалась</b>\n\n"
            f"Ошибка: {user_message}\n\n"
            f"💡 <b>Рекомендации:</b>\n"
            f"• Проверьте правильность параметров\n"
            f"• Попробуйте изменить prompt\n"
            f"• Убедитесь, что все обязательные параметры заполнены"
        )
    else:
        return (
            f"❌ <b>Generation failed</b>\n\n"
            f"Error: {user_message}\n\n"
            f"💡 <b>Recommendations:</b>\n"
            f"• Check parameter correctness\n"
            f"• Try changing the prompt\n"
            f"• Make sure all required parameters are filled"
        )


def handle_task_status(
    status_response: Dict[str, Any],
    model_id: str,
    mode: str
) -> Dict[str, Any]:
    """
    Обрабатывает статус задачи и определяет следующее действие.
    
    Args:
        status_response: Ответ от get_task_status
        model_id: ID модели
        mode: ID mode
    
    Returns:
        Обработанный статус с рекомендациями
    """
    state = status_response.get('state', 'unknown')
    
    result = {
        'state': state,
        'should_continue': False,
        'should_retry': False,
        'error': None
    }
    
    if state == 'success':
        result['should_continue'] = True
        result['should_retry'] = False
        
    elif state == 'fail':
        result['should_continue'] = False
        result['should_retry'] = False
        result['error'] = handle_api_error(status_response, model_id, mode)
        
    elif state in ['waiting', 'queuing', 'generating']:
        result['should_continue'] = True
        result['should_retry'] = True
        
    else:
        result['should_continue'] = False
        result['should_retry'] = True
        result['error'] = f"Неизвестный статус: {state}"
    
    return result


def log_api_error(
    error: Exception,
    context: Dict[str, Any],
    model_id: str,
    mode: str
):
    """
    Логирует ошибку API с полным контекстом.
    
    Args:
        error: Исключение
        context: Контекст ошибки
        model_id: ID модели
        mode: ID mode
    """
    logger.error(
        f"❌ API Error для {model_id}:{mode}: {type(error).__name__}: {str(error)}",
        exc_info=True
    )
    logger.error(f"❌ Контекст: {context}")

