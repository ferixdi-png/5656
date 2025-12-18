#!/usr/bin/env python3
"""
Скрипт для проверки всех кнопок и их callback_data.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_all_callbacks():
    """Проверяет все callback_data в коде."""
    logger.info("🔍 Проверка всех callback_data...")
    
    try:
        bot_kie_path = root_dir / "bot_kie.py"
        
        if not bot_kie_path.exists():
            logger.error("❌ Файл bot_kie.py не найден")
            return False
        
        with open(bot_kie_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Ищем все callback_data
        import re
        
        # Паттерны для callback_data
        patterns = [
            r'callback_data=["\']([^"\']+)["\']',
            r"callback_data=['\"]([^'\"]+)['\"]",
        ]
        
        callbacks = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            callbacks.update(matches)
        
        logger.info(f"📋 Найдено {len(callbacks)} уникальных callback_data")
        
        # Проверяем обработчики для каждого callback
        handlers_found = {}
        handlers_missing = []
        
        for callback in sorted(callbacks):
            # Ищем обработчик для этого callback
            if f'"{callback}"' in content or f"'{callback}'" in content:
                # Проверяем, что есть обработка в button_callback или других функциях
                if f'data == "{callback}"' in content or f"data == '{callback}'" in content:
                    handlers_found[callback] = True
                elif callback.startswith('model:') or callback.startswith('set_param:') or callback.startswith('start:'):
                    # Эти callback обрабатываются через паттерны
                    handlers_found[callback] = True
                else:
                    handlers_missing.append(callback)
            else:
                handlers_missing.append(callback)
        
        if handlers_missing:
            logger.warning(f"⚠️ Не найдены обработчики для {len(handlers_missing)} callback:")
            for callback in handlers_missing[:10]:  # Показываем первые 10
                logger.warning(f"  - {callback}")
        else:
            logger.info("✅ Все callback_data имеют обработчики")
        
        return len(handlers_missing) == 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке callback: {e}", exc_info=True)
        return False


def check_keyboard_generation():
    """Проверяет генерацию клавиатур."""
    logger.info("🔍 Проверка генерации клавиатур...")
    
    try:
        from helpers import build_main_menu_keyboard
        from kie_models import KIE_MODELS
        
        # Проверяем главное меню
        keyboard = build_main_menu_keyboard()
        if keyboard:
            logger.info("✅ Главное меню генерируется корректно")
        else:
            logger.warning("⚠️ Главное меню не генерируется")
            return False
        
        # Проверяем клавиатуры для моделей
        test_models = list(KIE_MODELS.keys())[:5]
        
        for model_id in test_models:
            try:
                from helpers import build_model_keyboard
                model_keyboard = build_model_keyboard(model_id)
                if model_keyboard:
                    logger.debug(f"  ✅ Клавиатура для {model_id} генерируется")
                else:
                    logger.warning(f"  ⚠️ Клавиатура для {model_id} не генерируется")
            except Exception as e:
                logger.warning(f"  ⚠️ Ошибка при генерации клавиатуры для {model_id}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке клавиатур: {e}", exc_info=True)
        return False


def main():
    """Основная функция проверки."""
    logger.info("🚀 Начало проверки кнопок и callback...")
    
    results = {
        'callbacks': False,
        'keyboards': False
    }
    
    # Проверка callback_data
    results['callbacks'] = check_all_callbacks()
    
    # Проверка генерации клавиатур
    results['keyboards'] = check_keyboard_generation()
    
    # Итоговый отчет
    logger.info("\n" + "="*60)
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ:")
    logger.info("="*60)
    
    for check_name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info(f"  {check_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✅ Все проверки пройдены успешно!")
        return 0
    else:
        logger.warning("\n⚠️ Некоторые проверки не пройдены")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

