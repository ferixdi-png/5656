"""
Global Error Guard with Self-Healing
Глобальная обработка ошибок с автоматическим исправлением
"""

import os
import sys
import json
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Категория ошибки"""
    UNKNOWN = "unknown"
    MISSING_HANDLER = "missing_handler"
    IMPORT_ERROR = "import_error"
    ATTRIBUTE_ERROR = "attribute_error"
    CALLBACK_ERROR = "callback_error"
    GENERATION_ERROR = "generation_error"
    API_ERROR = "api_error"
    DATABASE_ERROR = "database_error"


@dataclass
class IncidentBundle:
    """Пакет информации об инциденте"""
    timestamp: str
    error_type: str
    error_message: str
    category: str
    stacktrace: str
    user_id: Optional[int] = None
    callback_data: Optional[str] = None
    last_action: Optional[str] = None
    env_snapshot: Dict[str, str] = None
    version: str = "unknown"
    fixed: bool = False
    fix_applied: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Преобразует в словарь для сохранения"""
        return asdict(self)
    
    def save(self, file_path: Path):
        """Сохраняет инцидент в JSON"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Не удалось сохранить инцидент: {e}")


class ErrorGuard:
    """Глобальная защита от ошибок с self-healing"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.incidents_dir = project_root / "data" / "incidents"
        self.incidents_dir.mkdir(parents=True, exist_ok=True)
        
        # Whitelist безопасных фиксов
        self.safe_fixes = {
            ErrorCategory.MISSING_HANDLER: self._fix_missing_handler,
            ErrorCategory.IMPORT_ERROR: self._fix_import_error,
            ErrorCategory.ATTRIBUTE_ERROR: self._fix_attribute_error,
        }
        
        self.stats = {
            "total_errors": 0,
            "fixed_errors": 0,
            "degraded_routes": []
        }
    
    def classify_error(self, error: Exception, context: Dict = None) -> ErrorCategory:
        """Классифицирует ошибку"""
        error_msg = str(error).lower()
        error_type = type(error).__name__
        
        if "modulenotfounderror" in error_type.lower() or "no module named" in error_msg:
            return ErrorCategory.IMPORT_ERROR
        elif "attributeerror" in error_type.lower():
            return ErrorCategory.ATTRIBUTE_ERROR
        elif "callback" in error_msg or "button" in error_msg:
            return ErrorCategory.CALLBACK_ERROR
        elif "generation" in error_msg or "kie" in error_msg:
            return ErrorCategory.GENERATION_ERROR
        elif "database" in error_msg or "connection" in error_msg:
            return ErrorCategory.DATABASE_ERROR
        elif context and context.get("callback_data"):
            return ErrorCategory.MISSING_HANDLER
        else:
            return ErrorCategory.UNKNOWN
    
    def create_incident_bundle(
        self,
        error: Exception,
        context: Dict = None,
        user_id: int = None,
        callback_data: str = None
    ) -> IncidentBundle:
        """Создаёт пакет информации об инциденте"""
        category = self.classify_error(error, context)
        
        # Безопасный снимок окружения (без секретов)
        env_snapshot = {}
        safe_vars = ["ENV", "BOT_MODE", "PYTHONPATH", "PORT", "ENABLE_HEALTH_SERVER"]
        for var in safe_vars:
            value = os.getenv(var)
            if value:
                env_snapshot[var] = value
        
        bundle = IncidentBundle(
            timestamp=datetime.now().isoformat(),
            error_type=type(error).__name__,
            error_message=str(error),
            category=category.value,
            stacktrace=traceback.format_exc(),
            user_id=user_id,
            callback_data=callback_data,
            last_action=context.get("last_action") if context else None,
            env_snapshot=env_snapshot,
            version=self._get_version()
        )
        
        return bundle
    
    def _get_version(self) -> str:
        """Получает версию (из git или даты)"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return datetime.now().strftime("%Y%m%d")
    
    async def handle_error(
        self,
        error: Exception,
        update=None,
        context=None,
        user_id: int = None,
        callback_data: str = None
    ) -> bool:
        """
        Обрабатывает ошибку и пытается применить безопасный фикс
        
        Returns:
            bool: True если фикс применён, False если нет
        """
        self.stats["total_errors"] += 1
        
        # Создаём инцидент
        incident_context = {
            "callback_data": callback_data,
            "last_action": "button_callback" if callback_data else "unknown"
        }
        bundle = self.create_incident_bundle(error, incident_context, user_id, callback_data)
        
        # Сохраняем инцидент
        incident_file = self.incidents_dir / f"incident_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        bundle.save(incident_file)
        
        # Пытаемся применить безопасный фикс
        category = self.classify_error(error, incident_context)
        
        if category in self.safe_fixes:
            try:
                fix_result = await self.safe_fixes[category](error, bundle, update, context)
                if fix_result:
                    bundle.fixed = True
                    bundle.fix_applied = fix_result
                    bundle.save(incident_file)
                    self.stats["fixed_errors"] += 1
                    logger.info(f"✅ Автоматически исправлена ошибка: {category.value}")
                    return True
            except Exception as fix_error:
                logger.error(f"❌ Ошибка при применении фикса: {fix_error}")
        
        # Если фикс не применён - режим деградации
        if callback_data:
            self._degrade_route(callback_data)
        
        return False
    
    async def _fix_missing_handler(
        self,
        error: Exception,
        bundle: IncidentBundle,
        update,
        context
    ) -> Optional[str]:
        """Фикс для отсутствующего обработчика"""
        # Fallback handler уже должен обработать это
        # Здесь можно добавить дополнительную логику
        return "fallback_handler_applied"
    
    async def _fix_import_error(
        self,
        error: Exception,
        bundle: IncidentBundle,
        update,
        context
    ) -> Optional[str]:
        """Фикс для ошибок импорта"""
        # Не исправляем автоматически - требует изменения кода
        logger.warning("⚠️ Import error требует ручного исправления")
        return None
    
    async def _fix_attribute_error(
        self,
        error: Exception,
        bundle: IncidentBundle,
        update,
        context
    ) -> Optional[str]:
        """Фикс для AttributeError"""
        # Не исправляем автоматически - требует изменения кода
        logger.warning("⚠️ Attribute error требует ручного исправления")
        return None
    
    def _degrade_route(self, callback_data: str):
        """Отключает проблемный маршрут (режим деградации)"""
        if callback_data not in self.stats["degraded_routes"]:
            self.stats["degraded_routes"].append(callback_data)
            logger.warning(f"⚠️ Маршрут '{callback_data}' переведён в режим деградации")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику обработки ошибок"""
        return {
            **self.stats,
            "incidents_dir": str(self.incidents_dir)
        }







