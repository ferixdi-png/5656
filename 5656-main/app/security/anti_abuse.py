"""
Комплексная защита от атак и злоупотреблений.

Защищает от:
1. DDoS атак на webhook
2. Спама от пользователей
3. Злоупотреблений (слишком много запросов)
4. Банов Telegram (обработка ошибок, rate limits)
5. Атак на баланс (слишком много генераций)
"""
import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class AbuseMetrics:
    """Метрики злоупотреблений для пользователя/IP."""
    user_id: Optional[int] = None
    ip: Optional[str] = None
    
    # Счетчики запросов
    total_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0
    
    # Временные окна
    requests_last_minute: deque = field(default_factory=deque)
    requests_last_hour: deque = field(default_factory=deque)
    
    # Флаги блокировки
    is_blocked: bool = False
    blocked_until: Optional[float] = None
    block_reason: str = ""
    
    # Telegram API ошибки
    telegram_errors: int = 0
    last_telegram_error: Optional[float] = None
    
    # Подозрительная активность
    suspicious_score: float = 0.0  # 0-100, чем выше - тем подозрительнее


class AntiAbuseSystem:
    """
    Система защиты от злоупотреблений.
    
    Защищает от:
    - Спама (flood protection)
    - DDoS атак
    - Злоупотреблений балансом
    - Банов Telegram
    """
    
    # Лимиты для обычных пользователей
    MAX_REQUESTS_PER_MINUTE = 30
    MAX_REQUESTS_PER_HOUR = 200
    MAX_REQUESTS_PER_DAY = 1000
    
    # Лимиты для генераций (защита баланса)
    MAX_GENERATIONS_PER_MINUTE = 5
    MAX_GENERATIONS_PER_HOUR = 20
    MAX_GENERATIONS_PER_DAY = 100
    
    # Лимиты для бесплатных моделей (строже)
    MAX_FREE_GENERATIONS_PER_MINUTE = 3
    MAX_FREE_GENERATIONS_PER_HOUR = 10
    MAX_FREE_GENERATIONS_PER_DAY = 30
    
    # Пороги для блокировки
    MAX_ERROR_RATE = 0.5  # 50% ошибок = блокировка
    MAX_TELEGRAM_ERRORS_PER_HOUR = 10
    SUSPICIOUS_SCORE_THRESHOLD = 70.0
    
    # Время блокировки
    BLOCK_DURATION_MINUTES = 15
    PERMANENT_BLOCK_AFTER = 3  # После 3 блокировок - постоянная
    
    def __init__(self):
        # user_id/IP -> AbuseMetrics
        self._metrics: Dict[Tuple[Optional[int], Optional[str]], AbuseMetrics] = {}
        self._lock = asyncio.Lock()
        
        # Белый список (админы, тестовые пользователи)
        self._whitelist: set = set()
        
        # История блокировок (для постоянной блокировки)
        self._block_history: Dict[Tuple[Optional[int], Optional[str]], List[float]] = defaultdict(list)
        
        # Очистка старых данных каждые 5 минут
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запустить фоновую очистку."""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(300)  # 5 минут
                await self._cleanup_old_data()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("[ANTI_ABUSE] Anti-abuse system started")
    
    async def stop(self):
        """Остановить систему."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("[ANTI_ABUSE] Anti-abuse system stopped")
    
    def add_to_whitelist(self, user_id: int):
        """Добавить пользователя в белый список."""
        self._whitelist.add(user_id)
        logger.info(f"[ANTI_ABUSE] User {user_id} added to whitelist")
    
    async def _get_metrics(self, user_id: Optional[int], ip: Optional[str]) -> AbuseMetrics:
        """Получить или создать метрики для пользователя/IP."""
        key = (user_id, ip)
        if key not in self._metrics:
            self._metrics[key] = AbuseMetrics(user_id=user_id, ip=ip)
        return self._metrics[key]
    
    async def _cleanup_old_data(self):
        """Очистить старые данные для экономии памяти."""
        async with self._lock:
            now = time.time()
            keys_to_remove = []
            
            for key, metrics in self._metrics.items():
                # Очистить старые временные окна
                cutoff_minute = now - 60
                cutoff_hour = now - 3600
                
                while metrics.requests_last_minute and metrics.requests_last_minute[0] < cutoff_minute:
                    metrics.requests_last_minute.popleft()
                while metrics.requests_last_hour and metrics.requests_last_hour[0] < cutoff_hour:
                    metrics.requests_last_hour.popleft()
                
                # Удалить метрики без активности за 24 часа
                if (not metrics.requests_last_hour and 
                    (not metrics.blocked_until or metrics.blocked_until < now) and
                    metrics.total_requests == 0):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._metrics.pop(key, None)
            
            if keys_to_remove:
                logger.debug(f"[ANTI_ABUSE] Cleaned {len(keys_to_remove)} inactive entries")
    
    async def check_request_allowed(
        self,
        user_id: Optional[int] = None,
        ip: Optional[str] = None,
        request_type: str = "general"
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Проверить, разрешен ли запрос.
        
        Args:
            user_id: ID пользователя (если есть)
            ip: IP адрес (если есть)
            request_type: Тип запроса (general, generation, free_generation)
        
        Returns:
            (allowed, reason, retry_after)
            - allowed: True если запрос разрешен
            - reason: Причина блокировки (если не разрешен)
            - retry_after: Через сколько секунд можно повторить
        """
        async with self._lock:
            # Белый список
            if user_id and user_id in self._whitelist:
                return True, None, None
            
            metrics = await self._get_metrics(user_id, ip)
            now = time.time()
            
            # Проверить блокировку
            if metrics.is_blocked:
                if metrics.blocked_until and metrics.blocked_until > now:
                    retry_after = metrics.blocked_until - now
                    return False, metrics.block_reason, retry_after
                else:
                    # Блокировка истекла
                    metrics.is_blocked = False
                    metrics.blocked_until = None
            
            # Очистить старые записи
            cutoff_minute = now - 60
            cutoff_hour = now - 3600
            
            while metrics.requests_last_minute and metrics.requests_last_minute[0] < cutoff_minute:
                metrics.requests_last_minute.popleft()
            while metrics.requests_last_hour and metrics.requests_last_hour[0] < cutoff_hour:
                metrics.requests_last_hour.popleft()
            
            # Проверить лимиты в зависимости от типа запроса
            if request_type == "generation":
                limit_minute = self.MAX_GENERATIONS_PER_MINUTE
                limit_hour = self.MAX_GENERATIONS_PER_HOUR
            elif request_type == "free_generation":
                limit_minute = self.MAX_FREE_GENERATIONS_PER_MINUTE
                limit_hour = self.MAX_FREE_GENERATIONS_PER_HOUR
            else:
                limit_minute = self.MAX_REQUESTS_PER_MINUTE
                limit_hour = self.MAX_REQUESTS_PER_HOUR
            
            # Проверить лимит в минуту
            if len(metrics.requests_last_minute) >= limit_minute:
                retry_after = 60 - (now - metrics.requests_last_minute[0])
                return False, f"Слишком много запросов. Лимит: {limit_minute}/мин", retry_after
            
            # Проверить лимит в час
            if len(metrics.requests_last_hour) >= limit_hour:
                retry_after = 3600 - (now - metrics.requests_last_hour[0])
                return False, f"Слишком много запросов. Лимит: {limit_hour}/час", retry_after
            
            # Проверить процент ошибок
            if metrics.total_requests > 10:
                metrics.error_rate = metrics.failed_requests / metrics.total_requests
                if metrics.error_rate > self.MAX_ERROR_RATE:
                    await self._block_user(metrics, "Слишком много ошибок", now)
                    return False, "Слишком много ошибок. Временная блокировка.", 900  # 15 минут
            
            # Проверить подозрительную активность
            if metrics.suspicious_score > self.SUSPICIOUS_SCORE_THRESHOLD:
                await self._block_user(metrics, "Подозрительная активность", now)
                return False, "Подозрительная активность обнаружена", 900
            
            # Запрос разрешен
            metrics.requests_last_minute.append(now)
            metrics.requests_last_hour.append(now)
            metrics.total_requests += 1
            
            return True, None, None
    
    async def record_request(
        self,
        user_id: Optional[int] = None,
        ip: Optional[str] = None,
        success: bool = True,
        telegram_error: bool = False
    ):
        """Записать запрос в метрики."""
        async with self._lock:
            metrics = await self._get_metrics(user_id, ip)
            
            if not success:
                metrics.failed_requests += 1
            
            if telegram_error:
                metrics.telegram_errors += 1
                metrics.last_telegram_error = time.time()
                
                # Если слишком много ошибок Telegram - блокировка
                if metrics.telegram_errors > self.MAX_TELEGRAM_ERRORS_PER_HOUR:
                    await self._block_user(
                        metrics,
                        "Слишком много ошибок Telegram API",
                        time.time()
                    )
            
            # Обновить подозрительный счет
            await self._update_suspicious_score(metrics)
    
    async def _update_suspicious_score(self, metrics: AbuseMetrics):
        """Обновить счет подозрительности."""
        score = 0.0
        
        # Высокий процент ошибок
        if metrics.total_requests > 10:
            error_rate = metrics.failed_requests / metrics.total_requests
            score += error_rate * 30  # До 30 баллов
        
        # Слишком много запросов
        if len(metrics.requests_last_minute) > self.MAX_REQUESTS_PER_MINUTE * 0.8:
            score += 20  # 20 баллов
        
        # Ошибки Telegram
        if metrics.telegram_errors > 5:
            score += 20  # 20 баллов
        
        # Очень быстрые запросы (подозрение на бота)
        if len(metrics.requests_last_minute) > 0:
            times = list(metrics.requests_last_minute)
            if len(times) > 1:
                intervals = [times[i] - times[i-1] for i in range(1, len(times))]
                avg_interval = sum(intervals) / len(intervals) if intervals else 0
                if avg_interval < 0.5:  # Меньше 0.5 секунды между запросами
                    score += 30  # 30 баллов
        
        metrics.suspicious_score = min(100.0, score)
    
    async def _block_user(
        self,
        metrics: AbuseMetrics,
        reason: str,
        now: float
    ):
        """Заблокировать пользователя/IP."""
        key = (metrics.user_id, metrics.ip)
        
        # Проверить историю блокировок
        block_count = len(self._block_history[key])
        
        if block_count >= self.PERMANENT_BLOCK_AFTER:
            # Постоянная блокировка
            metrics.is_blocked = True
            metrics.blocked_until = None  # Навсегда
            metrics.block_reason = f"Постоянная блокировка: {reason}"
            logger.warning(
                f"[ANTI_ABUSE] Permanent block: user_id={metrics.user_id} ip={metrics.ip} "
                f"reason={reason} blocks={block_count}"
            )
        else:
            # Временная блокировка
            metrics.is_blocked = True
            metrics.blocked_until = now + (self.BLOCK_DURATION_MINUTES * 60)
            metrics.block_reason = reason
            self._block_history[key].append(now)
            logger.warning(
                f"[ANTI_ABUSE] Temporary block: user_id={metrics.user_id} ip={metrics.ip} "
                f"reason={reason} until={metrics.blocked_until} blocks={block_count+1}"
            )
    
    async def get_stats(self, user_id: Optional[int] = None, ip: Optional[str] = None) -> Dict:
        """Получить статистику для пользователя/IP."""
        async with self._lock:
            metrics = await self._get_metrics(user_id, ip)
            
            return {
                "total_requests": metrics.total_requests,
                "failed_requests": metrics.failed_requests,
                "error_rate": metrics.error_rate,
                "requests_last_minute": len(metrics.requests_last_minute),
                "requests_last_hour": len(metrics.requests_last_hour),
                "is_blocked": metrics.is_blocked,
                "blocked_until": metrics.blocked_until,
                "suspicious_score": metrics.suspicious_score,
                "telegram_errors": metrics.telegram_errors,
            }


# Глобальный экземпляр
_anti_abuse: Optional[AntiAbuseSystem] = None


def get_anti_abuse() -> AntiAbuseSystem:
    """Получить глобальный экземпляр системы защиты."""
    global _anti_abuse
    if _anti_abuse is None:
        _anti_abuse = AntiAbuseSystem()
    return _anti_abuse

