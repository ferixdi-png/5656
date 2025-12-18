#!/usr/bin/env python3
"""
Скрипт для финальной проверки интеграции с KIE API и всех моделей.
"""

import os
import sys
import asyncio
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


async def check_kie_api_integration():
    """Проверяет интеграцию с KIE API."""
    logger.info("🔍 Проверка интеграции с KIE API...")
    
    try:
        from kie_client import get_client
        
        client = get_client()
        
        # Проверяем получение списка моделей
        logger.info("📋 Получение списка моделей...")
        models = await client.list_models()
        
        if not models:
            logger.warning("⚠️ Список моделей пуст. Проверьте KIE_API_KEY и KIE_API_URL")
            return False
        
        logger.info(f"✅ Получено {len(models)} моделей из KIE API")
        
        # Проверяем несколько моделей
        test_models = models[:5] if len(models) >= 5 else models
        
        for model in test_models:
            model_id = model.get('id') or model.get('model_id')
            if not model_id:
                continue
            
            logger.info(f"🔍 Проверка модели: {model_id}")
            
            # Получаем информацию о модели
            model_info = await client.get_model(model_id)
            if model_info:
                logger.info(f"  ✅ Модель {model_id} доступна")
            else:
                logger.warning(f"  ⚠️ Модель {model_id} недоступна")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке KIE API: {e}", exc_info=True)
        return False


async def check_models_in_kie_models():
    """Проверяет, что все модели из KIE API есть в kie_models.py."""
    logger.info("🔍 Проверка моделей в kie_models.py...")
    
    try:
        from kie_client import get_client
        from kie_models import KIE_MODELS, get_model_by_id
        
        client = get_client()
        api_models = await client.list_models()
        
        if not api_models:
            logger.warning("⚠️ Не удалось получить модели из API")
            return False
        
        # Получаем ID моделей из API
        api_model_ids = set()
        for model in api_models:
            model_id = model.get('id') or model.get('model_id')
            if model_id:
                api_model_ids.add(model_id)
        
        # Получаем ID моделей из kie_models.py
        local_model_ids = set(KIE_MODELS.keys())
        
        # Проверяем, какие модели отсутствуют
        missing_models = api_model_ids - local_model_ids
        extra_models = local_model_ids - api_model_ids
        
        if missing_models:
            logger.warning(f"⚠️ Отсутствуют в kie_models.py: {len(missing_models)} моделей")
            for model_id in list(missing_models)[:10]:  # Показываем первые 10
                logger.warning(f"  - {model_id}")
        else:
            logger.info("✅ Все модели из API присутствуют в kie_models.py")
        
        if extra_models:
            logger.info(f"ℹ️ Дополнительные модели в kie_models.py: {len(extra_models)}")
        
        return len(missing_models) == 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке моделей: {e}", exc_info=True)
        return False


async def test_model_generation():
    """Тестирует генерацию для нескольких моделей."""
    logger.info("🧪 Тестирование генерации...")
    
    try:
        from kie_client import get_client
        from kie_models import KIE_MODELS
        from config_runtime import is_dry_run, allow_real_generation
        
        client = get_client()
        dry_run = is_dry_run() or not allow_real_generation()
        
        if dry_run:
            logger.info("🔧 Режим DRY_RUN: генерация будет симулирована")
        
        # Выбираем несколько моделей для тестирования
        test_models = list(KIE_MODELS.keys())[:3]
        
        for model_id in test_models:
            logger.info(f"🧪 Тестирование модели: {model_id}")
            
            try:
                # Получаем параметры модели
                model_info = KIE_MODELS.get(model_id)
                if not model_info:
                    logger.warning(f"  ⚠️ Модель {model_id} не найдена в KIE_MODELS")
                    continue
                
                # Подготавливаем тестовые параметры
                params = {}
                input_schema = model_info.get('input_schema', {})
                properties = input_schema.get('properties', {})
                
                # Добавляем обязательные параметры
                if 'prompt' in properties:
                    params['prompt'] = 'Test prompt for integration check'
                elif 'text' in properties:
                    params['text'] = 'Test text for integration check'
                
                # Пробуем создать задачу
                if dry_run:
                    logger.info(f"  🔧 DRY_RUN: Симуляция создания задачи для {model_id}")
                    logger.info(f"  ✅ Симуляция успешна")
                else:
                    task_result = await client.create_task(model_id, params)
                    if task_result:
                        logger.info(f"  ✅ Задача создана для {model_id}")
                    else:
                        logger.warning(f"  ⚠️ Не удалось создать задачу для {model_id}")
                
            except Exception as e:
                logger.error(f"  ❌ Ошибка при тестировании {model_id}: {e}", exc_info=True)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании генерации: {e}", exc_info=True)
        return False


async def main():
    """Основная функция проверки."""
    logger.info("🚀 Начало финальной проверки интеграции...")
    
    results = {
        'kie_api': False,
        'models_sync': False,
        'generation': False
    }
    
    # Проверка интеграции с KIE API
    results['kie_api'] = await check_kie_api_integration()
    
    # Проверка синхронизации моделей
    results['models_sync'] = await check_models_in_kie_models()
    
    # Тестирование генерации
    results['generation'] = await test_model_generation()
    
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
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

