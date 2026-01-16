"""
Middleware для защиты от банов Telegram.

Обрабатывает:
- Rate limiting для Telegram API
- Circuit breaker при ошибках
- Автоматическая обработка retry_after
"""
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from app.security.telegram_protection import get_telegram_protection
from app.utils.correlation import correlation_tag

logger = logging.getLogger(__name__)


class TelegramProtectionMiddleware(BaseMiddleware):
    """
    Middleware для защиты от банов Telegram API.
    
    Функции:
    - Rate limiting перед запросами к Telegram API
    - Circuit breaker при ошибках
    - Автоматическая обработка retry_after
    """
    
    def __init__(self):
        super().__init__()
        self.protection = get_telegram_protection()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Обработать запрос с защитой от банов."""
        cid = correlation_tag()
        
        # Проверить rate limit перед любым запросом к Telegram API
        # (это делается в самом начале, до вызова handler)
        # Но handler может делать запросы к API, поэтому нужно обернуть
        
        try:
            # Выполнить handler
            result = await handler(event, data)
            
            # Записать успех
            await self.protection.record_success()
            
            return result
            
        except TelegramRetryAfter as e:
            # КРИТИЧНО: Всегда соблюдать retry_after
            retry_after = e.retry_after if hasattr(e, 'retry_after') else 1.0
            
            await self.protection.record_error(e)
            
            logger.warning(
                f"{cid} [TELEGRAM_PROTECTION] RetryAfter: {retry_after}s. "
                f"Waiting before retry..."
            )
            
            # Подождать указанное время
            await asyncio.sleep(retry_after)
            
            # Попробовать еще раз (только один раз)
            try:
                result = await handler(event, data)
                await self.protection.record_success()
                return result
            except Exception as retry_error:
                await self.protection.record_error(retry_error)
                raise
            
        except TelegramAPIError as e:
            # Другие ошибки Telegram API
            await self.protection.record_error(e)
            
            logger.error(
                f"{cid} [TELEGRAM_PROTECTION] Telegram API error: {e}"
            )
            
            # Проверить circuit breaker
            stats = await self.protection.get_stats()
            if stats["circuit_open"]:
                retry_after = stats.get("circuit_open_until", 0) - asyncio.get_event_loop().time()
                if retry_after > 0:
                    logger.error(
                        f"{cid} [TELEGRAM_PROTECTION] Circuit breaker OPEN. "
                        f"Request blocked. Retry after {retry_after:.1f}s"
                    )
                    # Не пробрасывать ошибку дальше, чтобы не спамить Telegram
                    # Просто логируем и возвращаем None (handler не выполнится)
                    return None
            
            # Пробросить ошибку дальше (для обработки в error handler)
            raise
        
        except Exception as e:
            # Другие ошибки - не связаны с Telegram API
            # Но все равно логируем
            logger.error(
                f"{cid} [TELEGRAM_PROTECTION] Unexpected error: {e}"
            )
            raise

