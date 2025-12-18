"""
Модуль для улучшенного логирования запросов и ошибок API.
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)

# Настройка логирования для API запросов
api_logger = logging.getLogger('api_requests')
api_logger.setLevel(logging.INFO)

# Настройка логирования для ошибок
error_logger = logging.getLogger('api_errors')
error_logger.setLevel(logging.ERROR)


def log_api_request(
    endpoint: str,
    method: str = 'GET',
    params: Optional[Dict[str, Any]] = None,
    response: Optional[Dict[str, Any]] = None,
    duration: Optional[float] = None,
    success: bool = True
):
    """
    Логирует запрос к API.
    
    Args:
        endpoint: Endpoint API
        method: HTTP метод
        params: Параметры запроса
        response: Ответ API
        duration: Длительность запроса в секундах
        success: Успешность запроса
    """
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'endpoint': endpoint,
        'method': method,
        'success': success,
        'duration': duration
    }
    
    if params:
        # Маскируем чувствительные данные
        safe_params = _mask_sensitive_data(params.copy())
        log_data['params'] = safe_params
    
    if response:
        # Логируем только основные поля ответа
        log_data['response'] = {
            'ok': response.get('ok'),
            'error': response.get('error') if not success else None,
            'taskId': response.get('taskId'),
            'state': response.get('state')
        }
    
    if success:
        api_logger.info(f"✅ API Request: {json.dumps(log_data, ensure_ascii=False)}")
    else:
        api_logger.error(f"❌ API Request Failed: {json.dumps(log_data, ensure_ascii=False)}")


def log_api_error(
    endpoint: str,
    error: Exception,
    params: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None
):
    """
    Логирует ошибку API.
    
    Args:
        endpoint: Endpoint API
        error: Исключение
        params: Параметры запроса
        context: Дополнительный контекст
    """
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'endpoint': endpoint,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context or {}
    }
    
    if params:
        safe_params = _mask_sensitive_data(params.copy())
        log_data['params'] = safe_params
    
    error_logger.error(
        f"❌ API Error: {json.dumps(log_data, ensure_ascii=False)}",
        exc_info=True
    )


def _mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Маскирует чувствительные данные в параметрах."""
    sensitive_keys = ['api_key', 'token', 'password', 'secret', 'auth']
    masked_data = data.copy()
    
    for key in masked_data:
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            if isinstance(masked_data[key], str):
                masked_data[key] = '***MASKED***'
            elif isinstance(masked_data[key], dict):
                masked_data[key] = _mask_sensitive_data(masked_data[key])
    
    return masked_data


def log_generation_request(
    user_id: int,
    model_id: str,
    params: Dict[str, Any],
    task_id: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None
):
    """
    Логирует запрос на генерацию.
    
    Args:
        user_id: ID пользователя
        model_id: ID модели
        params: Параметры генерации
        task_id: ID задачи
        success: Успешность запроса
        error: Сообщение об ошибке
    """
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'model_id': model_id,
        'task_id': task_id,
        'success': success,
        'params': _mask_sensitive_data(params.copy())
    }
    
    if error:
        log_data['error'] = error
    
    if success:
        logger.info(f"✅ Generation Request: {json.dumps(log_data, ensure_ascii=False)}")
    else:
        logger.error(f"❌ Generation Request Failed: {json.dumps(log_data, ensure_ascii=False)}")


def log_balance_check(
    user_id: int,
    required_balance: float,
    user_balance: float,
    sufficient: bool
):
    """
    Логирует проверку баланса.
    
    Args:
        user_id: ID пользователя
        required_balance: Требуемый баланс
        user_balance: Текущий баланс пользователя
        sufficient: Достаточно ли средств
    """
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'required_balance': required_balance,
        'user_balance': user_balance,
        'sufficient': sufficient
    }
    
    logger.info(f"💰 Balance Check: {json.dumps(log_data, ensure_ascii=False)}")


def api_request_logger(endpoint: str):
    """
    Декоратор для логирования API запросов.
    
    Args:
        endpoint: Endpoint API
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            success = True
            error = None
            response = None
            
            try:
                # Извлекаем параметры из kwargs
                params = kwargs.copy()
                if args:
                    params['args'] = str(args)
                
                response = await func(*args, **kwargs)
                
                if isinstance(response, dict) and not response.get('ok'):
                    success = False
                    error = response.get('error', 'Unknown error')
                
            except Exception as e:
                success = False
                error = str(e)
                log_api_error(endpoint, e, params=kwargs)
                raise
            finally:
                duration = time.time() - start_time
                log_api_request(
                    endpoint=endpoint,
                    method='POST' if 'create' in endpoint.lower() or 'invoke' in endpoint.lower() else 'GET',
                    params=kwargs,
                    response=response,
                    duration=duration,
                    success=success
                )
            
            return response
        return wrapper
    return decorator

