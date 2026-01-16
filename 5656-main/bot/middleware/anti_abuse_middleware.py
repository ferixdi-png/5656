"""
Middleware для защиты от злоупотреблений.

Интегрирует AntiAbuseSystem в обработку обновлений.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery

from app.security.anti_abuse import get_anti_abuse
from app.utils.correlation import correlation_tag

logger = logging.getLogger(__name__)


class AntiAbuseMiddleware(BaseMiddleware):
    """
    Middleware для защиты от злоупотреблений.
    
    Проверяет:
    - Rate limiting для пользователей
    - Защита от спама
    - Защита от DDoS
    """
    
    def __init__(self):
        super().__init__()
        self.anti_abuse = get_anti_abuse()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверить запрос на злоупотребления."""
        cid = correlation_tag()
        
        # Извлечь user_id и IP
        user_id = None
        ip = None
        
        if isinstance(event, Update):
            if event.message and event.message.from_user:
                user_id = event.message.from_user.id
            elif event.callback_query and event.callback_query.from_user:
                user_id = event.callback_query.from_user.id
        elif isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
        
        # IP из webhook request (если есть)
        if "request" in data:
            request = data["request"]
            if hasattr(request, "remote"):
                ip = request.remote
        
        # Определить тип запроса
        request_type = "general"
        if isinstance(event, (Message, CallbackQuery)):
            # Проверить, это генерация?
            if isinstance(event, CallbackQuery):
                callback_data = event.data
                if callback_data and ("generate" in callback_data or "model:" in callback_data):
                    # Проверить, бесплатная ли модель
                    # TODO: Интегрировать с FreeModelManager
                    request_type = "generation"
            elif isinstance(event, Message):
                # Проверить, это команда генерации?
                if event.text and ("generate" in event.text.lower() or "/start" in event.text):
                    request_type = "generation"
        
        # Проверить rate limit
        allowed, reason, retry_after = await self.anti_abuse.check_request_allowed(
            user_id=user_id,
            ip=ip,
            request_type=request_type
        )
        
        if not allowed:
            logger.warning(
                f"{cid} [ANTI_ABUSE] Request blocked: user_id={user_id} ip={ip} "
                f"reason={reason} retry_after={retry_after}"
            )
            
            # Отправить сообщение пользователю
            try:
                if isinstance(event, Message):
                    await event.answer(
                        f"⏱ {reason}\n\n"
                        f"Попробуйте снова через {int(retry_after) + 1} секунд."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        f"⏱ {reason}\n\nПопробуйте через {int(retry_after) + 1}с",
                        show_alert=True
                    )
            except Exception as e:
                logger.error(f"{cid} [ANTI_ABUSE] Failed to send block message: {e}")
            
            # Не обрабатывать запрос
            return
        
        # Запрос разрешен, обработать
        try:
            result = await handler(event, data)
            
            # Записать успешный запрос
            await self.anti_abuse.record_request(
                user_id=user_id,
                ip=ip,
                success=True
            )
            
            return result
            
        except Exception as e:
            # Записать неудачный запрос
            telegram_error = "Telegram" in type(e).__name__
            await self.anti_abuse.record_request(
                user_id=user_id,
                ip=ip,
                success=False,
                telegram_error=telegram_error
            )
            
            # Пробросить ошибку дальше
            raise

