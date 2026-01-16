"""
Button Validator
Валидация всех кнопок на старте бота
"""

import re
import logging
from typing import Dict, List, Set, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class ButtonValidator:
    """Валидатор кнопок и их обработчиков"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.callbacks_in_code: Set[str] = set()
        self.callbacks_in_handlers: Set[str] = set()
        self.issues: List[Dict] = []
    
    def scan_code_for_callbacks(self, file_path: Path) -> Set[str]:
        """Сканирует код на наличие callback_data"""
        callbacks = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ищем все callback_data в коде
            patterns = [
                r'callback_data\s*[=:]\s*["\']([^"\']+)["\']',
                r'callback_data\s*=\s*f["\']([^"\']+)["\']',
                r'callback_data\s*=\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    callback = match.group(1)
                    # Убираем переменные из f-strings
                    if '{' not in callback and '}' not in callback:
                        callbacks.add(callback)
                    else:
                        # Извлекаем базовый паттерн (например, "gen_type:{type}" -> "gen_type:")
                        base = callback.split('{')[0] if '{' in callback else callback
                        if base:
                            callbacks.add(base)
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при сканировании {file_path}: {e}")
        
        return callbacks
    
    def scan_handlers(self, file_path: Path) -> Set[str]:
        """Сканирует обработчики callback'ов"""
        callbacks = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ищем обработку callback_data в button_callback
            # Паттерны: if data == "...", if data.startswith("..."), elif data == "..."
            patterns = [
                r'if\s+data\s*==\s*["\']([^"\']+)["\']',
                r'elif\s+data\s*==\s*["\']([^"\']+)["\']',
                r'if\s+data\.startswith\(["\']([^"\']+)["\']',
                r'elif\s+data\.startswith\(["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    callback = match.group(1)
                    callbacks.add(callback)
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при сканировании handlers в {file_path}: {e}")
        
        return callbacks
    
    def validate(self, registry) -> Dict[str, List[str]]:
        """Валидирует реестр кнопок"""
        issues = {
            "unhandled_callbacks": [],  # Кнопки в коде, но нет обработчика
            "dead_handlers": [],  # Обработчики, но нет кнопок
            "duplicates": [],
            "warnings": []
        }
        
        # Сканируем bot_kie.py
        bot_file = self.project_root / "bot_kie.py"
        if bot_file.exists():
            self.callbacks_in_code = self.scan_code_for_callbacks(bot_file)
            self.callbacks_in_handlers = self.scan_handlers(bot_file)
        
        # Получаем зарегистрированные callback'ы
        registered = registry.get_all_callbacks()
        
        # Проверяем необработанные callback'ы
        for callback in self.callbacks_in_code:
            if callback not in registered and callback not in self.callbacks_in_handlers:
                # Проверяем, не является ли это префиксом
                is_prefix = any(callback.startswith(reg) for reg in registered)
                if not is_prefix:
                    issues["unhandled_callbacks"].append(callback)
        
        # Проверяем "мёртвые" обработчики (если есть в реестре, но нет в коде)
        # Это менее критично, но стоит отметить
        
        return issues
    
    def print_report(self, issues: Dict[str, List[str]]):
        """Выводит отчёт о валидации"""
        logger.info("=" * 80)
        logger.info("🔍 ОТЧЁТ ВАЛИДАЦИИ КНОПОК")
        logger.info("=" * 80)
        
        if issues["unhandled_callbacks"]:
            logger.warning(f"⚠️ Найдено {len(issues['unhandled_callbacks'])} необработанных callback'ов:")
            for callback in issues["unhandled_callbacks"][:10]:  # Показываем первые 10
                logger.warning(f"   - {callback}")
            if len(issues["unhandled_callbacks"]) > 10:
                logger.warning(f"   ... и ещё {len(issues['unhandled_callbacks']) - 10}")
        else:
            logger.info("✅ Все callback'ы обработаны")
        
        if issues["dead_handlers"]:
            logger.warning(f"⚠️ Найдено {len(issues['dead_handlers'])} 'мёртвых' обработчиков")
        
        if issues["duplicates"]:
            logger.warning(f"⚠️ Найдено {len(issues['duplicates'])} дубликатов")
        
        logger.info("=" * 80)







