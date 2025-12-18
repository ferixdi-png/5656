#!/usr/bin/env python3
"""
Скрипт для автоматического обновления моделей из KIE API.
Можно запускать периодически (например, через cron) для синхронизации моделей.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

load_dotenv()

# Настройка логирования
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_and_update_models():
    """Проверяет и обновляет модели из KIE API."""
    try:
        from sync_models_from_api import find_missing_models, add_models_to_kie_models_py
        from pathlib import Path
        
        logger.info("🔄 Начало проверки обновлений моделей...")
        
        # Ищем недостающие модели
        missing_models = await find_missing_models()
        
        if not missing_models:
            logger.info("✅ Все модели из API уже присутствуют в коде!")
            return True
        
        logger.info(f"📊 Найдено {len(missing_models)} новых моделей")
        
        # Добавляем модели
        root_dir = Path(__file__).parent
        kie_models_file = root_dir / "kie_models.py"
        
        if add_models_to_kie_models_py(missing_models, kie_models_file):
            logger.info(f"✅ Модели успешно добавлены в {kie_models_file}")
            return True
        else:
            logger.error("❌ Не удалось добавить модели в файл")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении моделей: {e}", exc_info=True)
        return False


async def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Автоматическое обновление моделей из KIE API')
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Только проверить наличие новых моделей, не обновлять'
    )
    
    args = parser.parse_args()
    
    if args.check_only:
        # Только проверяем
        logger.info("🔍 Проверка наличия новых моделей...")
        try:
            from kie_client import get_client
            client = get_client()
            models = await client.list_models()
            
            from kie_models import KIE_MODELS
            existing_model_ids = {model.get('id') or model.get('model_id') for model in KIE_MODELS}
            api_model_ids = {model.get('id') or model.get('model_id') for model in models if model.get('id') or model.get('model_id')}
            
            new_models = api_model_ids - existing_model_ids
            
            if new_models:
                logger.info(f"✅ Найдено {len(new_models)} новых моделей: {', '.join(new_models)}")
                return 1
            else:
                logger.info("ℹ️ Новых моделей не найдено")
                return 0
                
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке моделей: {e}", exc_info=True)
            return 1
    
    # Обновляем модели
    try:
        success = await check_and_update_models()
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении моделей: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

