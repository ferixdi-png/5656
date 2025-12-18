"""
Обработка ошибок с API Kie.ai и поставщиками моделей.
Чёткие сообщения для пользователя и детальное логирование.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSource(Enum):
    """Источник ошибки."""
    KIE_AI = "kie_ai"
    PROVIDER = "provider"
    NETWORK = "network"
    UNKNOWN = "unknown"


class ErrorType(Enum):
    """Тип ошибки."""
    SERVER_ERROR = "server_error"  # 500, 503
    RATE_LIMIT = "rate_limit"  # 429
    PAYMENT_ERROR = "payment_error"  # Недостаточно кредитов у поставщика
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"


class ProviderErrorHandler:
    """Обработчик ошибок с провайдерами и Kie.ai."""
    
    def __init__(self):
        self.error_log: list[Dict[str, Any]] = []
    
    def _log_error(
        self,
        source: ErrorSource,
        error_type: ErrorType,
        status_code: Optional[int],
        message: str,
        details: Dict[str, Any]
    ):
        """Логирует ошибку с деталями."""
        error_entry = {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "source": source.value,
            "error_type": error_type.value,
            "status_code": status_code,
            "message": message,
            "details": details
        }
        
        self.error_log.append(error_entry)
        
        # Логируем в файл
        logger.error(
            f"❌ ERROR [{source.value.upper()}] [{error_type.value}]: {message}",
            extra={
                "status_code": status_code,
                "details": details
            }
        )
    
    def handle_api_error(
        self,
        status_code: int,
        response_data: Optional[Dict[str, Any]] = None,
        request_details: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обрабатывает ошибку API Kie.ai.
        
        Returns:
            (user_message, error_details)
        """
        error_type = None
        user_message = None
        
        if status_code == 429:
            error_type = ErrorType.RATE_LIMIT
            user_message = (
                "⚠️ <b>В данный момент мы ограничены по API</b>\n\n"
                "Пожалуйста, повторите запрос через некоторое время.\n\n"
                "Это временное ограничение на стороне сервера."
            )
        elif status_code in [500, 502, 503, 504]:
            error_type = ErrorType.SERVER_ERROR
            user_message = (
                "❌ <b>Простите, возникла ошибка на сервере Kie.ai</b>\n\n"
                "Пожалуйста, попробуйте позже.\n\n"
                "Это техническая проблема на стороне сервера, мы уже работаем над её решением."
            )
        elif status_code == 400:
            error_type = ErrorType.VALIDATION_ERROR
            user_message = (
                "❌ <b>Ошибка в параметрах запроса</b>\n\n"
                "Пожалуйста, проверьте введённые параметры и попробуйте снова."
            )
        elif status_code == 401 or status_code == 403:
            error_type = ErrorType.PAYMENT_ERROR
            user_message = (
                "❌ <b>Ошибка авторизации</b>\n\n"
                "Пожалуйста, обратитесь к администратору."
            )
        else:
            error_type = ErrorType.UNKNOWN
            user_message = (
                "❌ <b>Произошла ошибка при обработке запроса</b>\n\n"
                "Пожалуйста, попробуйте позже.\n\n"
                "Если ошибка повторяется, обратитесь в поддержку."
            )
        
        error_details = {
            "status_code": status_code,
            "response_data": response_data,
            "request_details": request_details,
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
        }
        
        self._log_error(
            source=ErrorSource.KIE_AI,
            error_type=error_type,
            status_code=status_code,
            message=f"API error: {status_code}",
            details=error_details
        )
        
        return user_message, error_details
    
    def handle_provider_error(
        self,
        provider_name: str,
        error_message: str,
        status_code: Optional[int] = None,
        request_details: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обрабатывает ошибку на стороне поставщика модели.
        
        Returns:
            (user_message, error_details)
        """
        error_type = ErrorType.UNKNOWN
        
        # Определяем тип ошибки по сообщению
        error_lower = error_message.lower()
        if "credit" in error_lower or "payment" in error_lower or "balance" in error_lower:
            error_type = ErrorType.PAYMENT_ERROR
        elif "timeout" in error_lower or "timed out" in error_lower:
            error_type = ErrorType.TIMEOUT
        elif "rate limit" in error_lower or "too many" in error_lower:
            error_type = ErrorType.RATE_LIMIT
        elif status_code and status_code >= 500:
            error_type = ErrorType.SERVER_ERROR
        
        user_message = (
            f"❌ <b>Ошибка на стороне поставщика модели ({provider_name})</b>\n\n"
            "Пожалуйста, повторите запрос позже.\n\n"
            "Это техническая проблема на стороне поставщика, мы уже уведомлены об этом."
        )
        
        error_details = {
            "provider": provider_name,
            "error_message": error_message,
            "status_code": status_code,
            "request_details": request_details,
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
        }
        
        self._log_error(
            source=ErrorSource.PROVIDER,
            error_type=error_type,
            status_code=status_code,
            message=f"Provider error ({provider_name}): {error_message}",
            details=error_details
        )
        
        return user_message, error_details
    
    def handle_network_error(
        self,
        error_message: str,
        request_details: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обрабатывает сетевую ошибку.
        
        Returns:
            (user_message, error_details)
        """
        user_message = (
            "❌ <b>Ошибка соединения с сервером</b>\n\n"
            "Пожалуйста, проверьте ваше интернет-соединение и попробуйте снова."
        )
        
        error_details = {
            "error_message": error_message,
            "request_details": request_details,
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
        }
        
        self._log_error(
            source=ErrorSource.NETWORK,
            error_type=ErrorType.NETWORK_ERROR,
            status_code=None,
            message=f"Network error: {error_message}",
            details=error_details
        )
        
        return user_message, error_details
    
    def handle_task_creation_error(
        self,
        model_id: str,
        error: Exception,
        request_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обрабатывает ошибку при создании задачи.
        
        Returns:
            (user_message, error_details)
        """
        error_str = str(error)
        status_code = getattr(error, 'status', None) or getattr(error, 'status_code', None)
        
        if status_code:
            return self.handle_api_error(status_code, request_details={
                "model_id": model_id,
                "params": request_params
            })
        elif "timeout" in error_str.lower():
            return self.handle_network_error(error_str, request_details={
                "model_id": model_id,
                "params": request_params
            })
        else:
            user_message = (
                "❌ <b>Ошибка при создании задачи</b>\n\n"
                "Это может быть из-за технической неполадки на сервере.\n\n"
                "Пожалуйста, попробуйте позже."
            )
            
            error_details = {
                "model_id": model_id,
                "error": error_str,
                "request_params": request_params,
                "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
            }
            
            self._log_error(
                source=ErrorSource.UNKNOWN,
                error_type=ErrorType.UNKNOWN,
                status_code=status_code,
                message=f"Task creation error: {error_str}",
                details=error_details
            )
            
            return user_message, error_details
    
    def handle_task_result_error(
        self,
        task_id: str,
        error: Exception
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обрабатывает ошибку при получении результата задачи.
        
        Returns:
            (user_message, error_details)
        """
        error_str = str(error)
        status_code = getattr(error, 'status', None) or getattr(error, 'status_code', None)
        
        if status_code:
            return self.handle_api_error(status_code, request_details={
                "task_id": task_id
            })
        else:
            user_message = (
                "❌ <b>Ошибка при получении результата</b>\n\n"
                "Пожалуйста, попробуйте позже.\n\n"
                "Ваш запрос обрабатывается, но возникла проблема при получении результата."
            )
            
            error_details = {
                "task_id": task_id,
                "error": error_str,
                "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
            }
            
            self._log_error(
                source=ErrorSource.UNKNOWN,
                error_type=ErrorType.UNKNOWN,
                status_code=status_code,
                message=f"Task result error: {error_str}",
                details=error_details
            )
            
            return user_message, error_details
    
    def get_error_report(self, limit: int = 100) -> Dict[str, Any]:
        """
        Генерирует отчёт об ошибках.
        
        Args:
            limit: Максимальное количество ошибок в отчёте
        
        Returns:
            Отчёт с деталями всех ошибок
        """
        recent_errors = self.error_log[-limit:] if len(self.error_log) > limit else self.error_log
        
        # Группируем по источнику
        errors_by_source = {}
        errors_by_type = {}
        
        for error in recent_errors:
            source = error["source"]
            error_type = error["error_type"]
            
            if source not in errors_by_source:
                errors_by_source[source] = []
            errors_by_source[source].append(error)
            
            if error_type not in errors_by_type:
                errors_by_type[error_type] = []
            errors_by_type[error_type].append(error)
        
        return {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "total_errors": len(self.error_log),
            "recent_errors_count": len(recent_errors),
            "errors_by_source": {
                source: len(errors) for source, errors in errors_by_source.items()
            },
            "errors_by_type": {
                error_type: len(errors) for error_type, errors in errors_by_type.items()
            },
            "recent_errors": recent_errors
        }
    
    def clear_error_log(self):
        """Очищает лог ошибок."""
        self.error_log.clear()
        logger.info("✅ Error log cleared")


# Глобальный экземпляр обработчика
_error_handler = ProviderErrorHandler()


def get_error_handler() -> ProviderErrorHandler:
    """Возвращает глобальный экземпляр обработчика ошибок."""
    return _error_handler


def handle_api_error(status_code: int, **kwargs) -> Tuple[str, Dict[str, Any]]:
    """Удобная функция для обработки ошибок API."""
    return _error_handler.handle_api_error(status_code, **kwargs)


def handle_provider_error(provider_name: str, error_message: str, **kwargs) -> Tuple[str, Dict[str, Any]]:
    """Удобная функция для обработки ошибок провайдера."""
    return _error_handler.handle_provider_error(provider_name, error_message, **kwargs)

