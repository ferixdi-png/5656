"""
Button Registry and Callback Router
Единый реестр всех кнопок и их обработчиков
"""

import re
import logging
from typing import Dict, Callable, Optional, List, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CallbackType(Enum):
    """Тип callback'а"""
    EXACT = "exact"  # Точное совпадение
    PREFIX = "prefix"  # Начинается с
    PATTERN = "pattern"  # Регулярное выражение


@dataclass
class ButtonHandler:
    """Информация об обработчике кнопки"""
    callback_data: str
    handler: Callable
    handler_name: str
    callback_type: CallbackType = CallbackType.EXACT
    description: str = ""
    file: str = ""
    line: int = 0


class ButtonRegistry:
    """Реестр всех кнопок бота"""
    
    def __init__(self):
        self._handlers: Dict[str, ButtonHandler] = {}
        self._prefix_handlers: List[ButtonHandler] = []
        self._pattern_handlers: List[ButtonHandler] = []
        self._all_callbacks: Set[str] = set()
    
    def register(
        self,
        callback_data: str,
        handler: Callable,
        handler_name: str = None,
        callback_type: CallbackType = CallbackType.EXACT,
        description: str = "",
        file: str = "",
        line: int = 0
    ):
        """Регистрирует обработчик кнопки"""
        handler_name = handler_name or handler.__name__
        
        button_handler = ButtonHandler(
            callback_data=callback_data,
            handler=handler,
            handler_name=handler_name,
            callback_type=callback_type,
            description=description,
            file=file,
            line=line
        )
        
        if callback_type == CallbackType.EXACT:
            if callback_data in self._handlers:
                logger.warning(f"⚠️ Дубликат callback_data: '{callback_data}' (было: {self._handlers[callback_data].handler_name}, новое: {handler_name})")
            self._handlers[callback_data] = button_handler
            self._all_callbacks.add(callback_data)
        elif callback_type == CallbackType.PREFIX:
            self._prefix_handlers.append(button_handler)
        elif callback_type == CallbackType.PATTERN:
            self._pattern_handlers.append(button_handler)
    
    def get_handler(self, callback_data: str) -> Optional[ButtonHandler]:
        """Получает обработчик для callback_data"""
        # Точное совпадение
        if callback_data in self._handlers:
            return self._handlers[callback_data]
        
        # Префикс
        for handler in self._prefix_handlers:
            if callback_data.startswith(handler.callback_data):
                return handler
        
        # Паттерн
        for handler in self._pattern_handlers:
            try:
                if re.match(handler.callback_data, callback_data):
                    return handler
            except re.error:
                logger.warning(f"⚠️ Неверный regex паттерн: {handler.callback_data}")
        
        return None
    
    def get_all_callbacks(self) -> Set[str]:
        """Возвращает все зарегистрированные callback_data"""
        return self._all_callbacks.copy()
    
    def validate(self) -> Dict[str, List[str]]:
        """Валидирует реестр и возвращает найденные проблемы"""
        issues = {
            "duplicates": [],
            "missing_handlers": [],
            "warnings": []
        }
        
        # Проверка дубликатов уже делается при регистрации
        # Здесь можно добавить дополнительные проверки
        
        return issues


class CallbackRouter:
    """Роутер для обработки callback'ов с fallback"""
    
    def __init__(self, registry: ButtonRegistry):
        self.registry = registry
        self._fallback_handler: Optional[Callable] = None
        self._stats = {
            "total": 0,
            "handled": 0,
            "fallback": 0,
            "errors": 0
        }
    
    def set_fallback_handler(self, handler: Callable):
        """Устанавливает fallback обработчик для неизвестных callback'ов"""
        self._fallback_handler = handler
    
    async def route(
        self,
        callback_data: str,
        update,
        context,
        user_id: int = None,
        user_lang: str = 'ru'
    ) -> bool:
        """
        Роутит callback_data к соответствующему обработчику
        
        Returns:
            bool: True если обработано, False если использован fallback
        """
        self._stats["total"] += 1
        
        try:
            handler_info = self.registry.get_handler(callback_data)
            
            if handler_info:
                try:
                    await handler_info.handler(update, context)
                    self._stats["handled"] += 1
                    return True
                except Exception as e:
                    logger.error(f"❌ Ошибка в обработчике '{handler_info.handler_name}' для '{callback_data}': {e}", exc_info=True)
                    self._stats["errors"] += 1
                    # Пробуем fallback
                    if self._fallback_handler:
                        await self._fallback_handler(callback_data, update, context, user_id, user_lang, error=str(e))
                        self._stats["fallback"] += 1
                    return False
            else:
                # Неизвестный callback - используем fallback
                if self._fallback_handler:
                    await self._fallback_handler(callback_data, update, context, user_id, user_lang)
                    self._stats["fallback"] += 1
                    return False
                else:
                    logger.error(f"❌ Неизвестный callback_data: '{callback_data}' и нет fallback handler")
                    self._stats["errors"] += 1
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в роутере для '{callback_data}': {e}", exc_info=True)
            self._stats["errors"] += 1
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """Возвращает статистику обработки"""
        return self._stats.copy()







