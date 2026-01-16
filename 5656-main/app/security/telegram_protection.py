"""
Защита от банов Telegram.

Предотвращает:
1. Слишком много запросов к Telegram API
2. Постоянные ошибки (которые могут привести к бану)
3. Некорректные запросы
4. Игнорирование retry_after
"""
import asyncio
import time
import logging
from typing import Dict, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field

from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter, TelegramBadRequest

logger = logging.getLogger(__name__)


@dataclass
class TelegramAPIMetrics:
    """Метрики использования Telegram API."""
    # Счетчики запросов
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Ошибки
    retry_after_errors: int = 0
    bad_request_errors: int = 0
    other_errors: int = 0
    
    # Временные окна
    requests_last_minute: deque = field(default_factory=deque)
    requests_last_hour: deque = field(default_factory=deque)
    
    # Последние ошибки
    last_error_time: Optional[float] = None
    last_error_type: Optional[str] = None
    consecutive_errors: int = 0
    
    # Circuit breaker
    circuit_open: bool = False
    circuit_open_until: Optional[float] = None
    circuit_failures: int = 0


class TelegramProtection:
    """
    Защита от банов Telegram API.
    
    Функции:
    - Rate limiting для Telegram API
    - Circuit breaker при ошибках
    - Автоматическая обработка retry_after
    - Мониторинг ошибок
    """
    
    # Лимиты Telegram API (консервативные)
    MAX_REQUESTS_PER_SECOND = 20  # Telegram позволяет ~30, но мы используем 20 для безопасности
    MAX_REQUESTS_PER_MINUTE = 1000
    MAX_REQUESTS_PER_HOUR = 20000
    
    # Пороги для circuit breaker
    MAX_CONSECUTIVE_ERRORS = 5
    MAX_ERROR_RATE = 0.3  # 30% ошибок = открыть circuit
    CIRCUIT_OPEN_DURATION = 60  # секунд
    
    # Пороги для тревоги
    MAX_BAD_REQUESTS_PER_HOUR = 50  # 4xx ошибки - плохой знак
    
    def __init__(self):
        self._metrics = TelegramAPIMetrics()
        self._lock = asyncio.Lock()
        self._request_times: deque = deque()  # Времена последних запросов
    
    async def check_rate_limit(self) -> Tuple[bool, Optional[float]]:
        """
        Проверить rate limit перед запросом к Telegram API.
        
        Returns:
            (allowed, retry_after)
        """
        async with self._lock:
            now = time.time()
            
            # Проверить circuit breaker
            if self._metrics.circuit_open:
                if self._metrics.circuit_open_until and self._metrics.circuit_open_until > now:
                    retry_after = self._metrics.circuit_open_until - now
                    logger.warning(
                        f"[TELEGRAM_PROTECTION] Circuit breaker OPEN. "
                        f"Retry after {retry_after:.1f}s"
                    )
                    return False, retry_after
                else:
                    # Circuit закрыт, но нужно проверить метрики
                    self._metrics.circuit_open = False
                    self._metrics.circuit_open_until = None
            
            # Очистить старые времена запросов
            cutoff = now - 1.0  # Последняя секунда
            while self._request_times and self._request_times[0] < cutoff:
                self._request_times.popleft()
            
            # Проверить лимит в секунду
            if len(self._request_times) >= self.MAX_REQUESTS_PER_SECOND:
                # Нужно подождать
                oldest = self._request_times[0]
                retry_after = 1.0 - (now - oldest)
                if retry_after > 0:
                    logger.debug(
                        f"[TELEGRAM_PROTECTION] Rate limit: {len(self._request_times)}/s. "
                        f"Wait {retry_after:.2f}s"
                    )
                    return False, retry_after
            
            # Проверить лимит в минуту
            cutoff_minute = now - 60
            minute_requests = [t for t in self._request_times if t > cutoff_minute]
            if len(minute_requests) >= self.MAX_REQUESTS_PER_MINUTE:
                retry_after = 60 - (now - minute_requests[0])
                logger.warning(
                    f"[TELEGRAM_PROTECTION] Rate limit: {len(minute_requests)}/min. "
                    f"Wait {retry_after:.1f}s"
                )
                return False, retry_after
            
            # Запрос разрешен
            self._request_times.append(now)
            self._metrics.total_requests += 1
            self._metrics.requests_last_minute.append(now)
            self._metrics.requests_last_hour.append(now)
            
            # Очистить старые записи
            cutoff_hour = now - 3600
            while self._metrics.requests_last_minute and self._metrics.requests_last_minute[0] < cutoff_hour:
                self._metrics.requests_last_minute.popleft()
            while self._metrics.requests_last_hour and self._metrics.requests_last_hour[0] < cutoff_hour:
                self._metrics.requests_last_hour.popleft()
            
            return True, None
    
    async def record_success(self):
        """Записать успешный запрос."""
        async with self._lock:
            self._metrics.successful_requests += 1
            self._metrics.consecutive_errors = 0
            
            # Если circuit был открыт и ошибок нет - можно закрыть
            if self._metrics.circuit_open and self._metrics.consecutive_errors == 0:
                self._metrics.circuit_open = False
                self._metrics.circuit_open_until = None
                self._metrics.circuit_failures = 0
                logger.info("[TELEGRAM_PROTECTION] Circuit breaker CLOSED (successful requests)")
    
    async def record_error(self, error: Exception):
        """Записать ошибку Telegram API."""
        async with self._lock:
            now = time.time()
            self._metrics.failed_requests += 1
            self._metrics.last_error_time = now
            self._metrics.consecutive_errors += 1
            
            # Классифицировать ошибку
            if isinstance(error, TelegramRetryAfter):
                self._metrics.retry_after_errors += 1
                self._metrics.last_error_type = "RetryAfter"
                logger.warning(
                    f"[TELEGRAM_PROTECTION] RetryAfter error: {error.retry_after}s. "
                    f"Consecutive errors: {self._metrics.consecutive_errors}"
                )
            elif isinstance(error, TelegramBadRequest):
                self._metrics.bad_request_errors += 1
                self._metrics.last_error_type = "BadRequest"
                logger.warning(
                    f"[TELEGRAM_PROTECTION] BadRequest error: {error}. "
                    f"Consecutive errors: {self._metrics.consecutive_errors}"
                )
            else:
                self._metrics.other_errors += 1
                self._metrics.last_error_type = type(error).__name__
                logger.warning(
                    f"[TELEGRAM_PROTECTION] {type(error).__name__} error: {error}. "
                    f"Consecutive errors: {self._metrics.consecutive_errors}"
                )
            
            # Проверить circuit breaker
            error_rate = 0.0
            if self._metrics.total_requests > 10:
                error_rate = self._metrics.failed_requests / self._metrics.total_requests
            
            should_open_circuit = (
                self._metrics.consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS or
                error_rate > self.MAX_ERROR_RATE or
                self._metrics.bad_request_errors > self.MAX_BAD_REQUESTS_PER_HOUR
            )
            
            if should_open_circuit and not self._metrics.circuit_open:
                self._metrics.circuit_open = True
                self._metrics.circuit_open_until = now + self.CIRCUIT_OPEN_DURATION
                self._metrics.circuit_failures += 1
                logger.error(
                    f"[TELEGRAM_PROTECTION] Circuit breaker OPENED. "
                    f"Consecutive errors: {self._metrics.consecutive_errors}, "
                    f"Error rate: {error_rate:.2%}, "
                    f"Bad requests: {self._metrics.bad_request_errors}. "
                    f"Will retry after {self.CIRCUIT_OPEN_DURATION}s"
                )
    
    async def get_stats(self) -> Dict:
        """Получить статистику использования Telegram API."""
        async with self._lock:
            error_rate = 0.0
            if self._metrics.total_requests > 0:
                error_rate = self._metrics.failed_requests / self._metrics.total_requests
            
            return {
                "total_requests": self._metrics.total_requests,
                "successful_requests": self._metrics.successful_requests,
                "failed_requests": self._metrics.failed_requests,
                "error_rate": error_rate,
                "retry_after_errors": self._metrics.retry_after_errors,
                "bad_request_errors": self._metrics.bad_request_errors,
                "other_errors": self._metrics.other_errors,
                "requests_last_minute": len(self._metrics.requests_last_minute),
                "requests_last_hour": len(self._metrics.requests_last_hour),
                "consecutive_errors": self._metrics.consecutive_errors,
                "circuit_open": self._metrics.circuit_open,
                "circuit_open_until": self._metrics.circuit_open_until,
                "last_error_type": self._metrics.last_error_type,
            }


# Глобальный экземпляр
_telegram_protection: Optional[TelegramProtection] = None


def get_telegram_protection() -> TelegramProtection:
    """Получить глобальный экземпляр защиты Telegram."""
    global _telegram_protection
    if _telegram_protection is None:
        _telegram_protection = TelegramProtection()
    return _telegram_protection

