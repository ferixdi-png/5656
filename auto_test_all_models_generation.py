"""
АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ ГЕНЕРАЦИЙ ВСЕХ МОДЕЛЕЙ KIE AI
Проверяет, что все модели корректно работают с KIE API
Тестирует создание задач, валидацию параметров, обработку ошибок
"""

import os
import sys
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
# Исправляем кодировку для Windows
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('model_generation_test.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Импортируем необходимые модули
try:
    from kie_models import KIE_MODELS, get_model_by_id
    from kie_client import KIEClient
except ImportError as e:
    logger.error(f"❌ Ошибка импорта: {e}")
    logger.error("Убедитесь, что все файлы на месте: kie_models.py, kie_client.py")
    sys.exit(1)


class ModelGenerationTester:
    """Класс для автоматического тестирования генераций всех моделей"""
    
    def __init__(self):
        self.kie_client = KIEClient()
        self.results = {
            'total_models': 0,
            'tested_models': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'results': []
        }
        
    def generate_test_params(self, model_id: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
        """Генерирует тестовые параметры для модели на основе input_params"""
        params = {}
        input_params = model_info.get('input_params', {})
        
        # Тестовые данные
        test_prompt = "Test generation - автоматическое тестирование"
        test_image_url = "https://via.placeholder.com/512"  # Placeholder изображение
        test_video_url = "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
        test_audio_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        
        for param_name, param_info in input_params.items():
            param_type = param_info.get('type', 'string')
            required = param_info.get('required', False)
            default = param_info.get('default')
            enum_values = param_info.get('enum', [])
            
            # Если параметр обязательный или есть default, добавляем его
            if required or default is not None:
                if param_name == 'prompt':
                    params[param_name] = test_prompt
                elif param_name in ['image_input', 'image_urls', 'image_url', 'image']:
                    if param_type == 'array':
                        params[param_name] = [test_image_url]
                    else:
                        params[param_name] = test_image_url
                elif param_name == 'video_url':
                    params[param_name] = test_video_url
                elif param_name == 'audio_url' or param_name == 'audio':
                    params[param_name] = test_audio_url
                elif enum_values:
                    # Берем первое значение из enum
                    params[param_name] = enum_values[0]
                elif param_type == 'boolean':
                    params[param_name] = False
                elif param_type == 'number':
                    params[param_name] = param_info.get('default', 1)
                elif param_type == 'integer':
                    params[param_name] = param_info.get('default', 1)
                elif default is not None:
                    params[param_name] = default
                else:
                    # Для строковых параметров без default используем тестовое значение
                    if param_type == 'string':
                        max_length = param_info.get('max_length', 100)
                        params[param_name] = test_prompt[:max_length]
        
        return params
    
    def prepare_api_params(self, model_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Подготавливает параметры для отправки в KIE API (как в bot_kie.py)"""
        api_params = params.copy()
        
        # Конвертации параметров согласно правилам KIE API
        if model_id == "recraft/remove-background" and 'image_input' in api_params:
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image'] = image_input
        elif model_id == "recraft/crisp-upscale" and 'image_input' in api_params:
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image'] = image_input
        elif model_id == "ideogram/v3-reframe" and 'image_input' in api_params:
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "topaz/image-upscale" and 'image_input' in api_params:
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        elif model_id == "seedream/4.5-edit" and 'image_input' in api_params:
            api_params['image_urls'] = api_params.pop('image_input')
        elif model_id == "kling-2.6/image-to-video" and 'image_input' in api_params:
            api_params['image_urls'] = api_params.pop('image_input')
        elif model_id == "flux-2/pro-image-to-image" and 'image_input' in api_params:
            api_params['input_urls'] = api_params.pop('image_input')
        elif model_id == "flux-2/flex-image-to-image" and 'image_input' in api_params:
            api_params['input_urls'] = api_params.pop('image_input')
        elif model_id == "kling/v2-5-turbo-image-to-video-pro" and 'image_input' in api_params:
            image_input = api_params.pop('image_input')
            if isinstance(image_input, list) and len(image_input) > 0:
                api_params['image_url'] = image_input[0]
            elif isinstance(image_input, str):
                api_params['image_url'] = image_input
        
        return api_params
    
    async def test_model_generation(self, model_id: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
        """Тестирует генерацию для одной модели"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🧪 Тестирование модели: {model_id}")
        logger.info(f"{'='*60}")
        
        result = {
            'model_id': model_id,
            'model_name': model_info.get('name', 'Unknown'),
            'status': 'unknown',
            'error': None,
            'task_id': None,
            'test_params': None,
            'api_params': None,
            'api_response': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Генерируем тестовые параметры
            test_params = self.generate_test_params(model_id, model_info)
            result['test_params'] = test_params
            
            logger.info(f"📋 Тестовые параметры: {json.dumps(test_params, ensure_ascii=False, indent=2)}")
            
            # Проверяем обязательные параметры
            input_params = model_info.get('input_params', {})
            required_params = [name for name, info in input_params.items() if info.get('required', False)]
            missing_params = [p for p in required_params if p not in test_params]
            
            if missing_params:
                error_msg = f"Отсутствуют обязательные параметры: {', '.join(missing_params)}"
                logger.error(f"❌ {error_msg}")
                result['status'] = 'failed'
                result['error'] = error_msg
                return result
            
            # Подготавливаем параметры для API
            api_params = self.prepare_api_params(model_id, test_params)
            result['api_params'] = api_params
            
            logger.info(f"📤 Параметры для KIE API: {json.dumps(api_params, ensure_ascii=False, indent=2)}")
            
            # Проверяем наличие API ключа
            if not self.kie_client.api_key:
                error_msg = "KIE_API_KEY не установлен в переменных окружения"
                logger.error(f"❌ {error_msg}")
                result['status'] = 'skipped'
                result['error'] = error_msg
                return result
            
            # Отправляем запрос в KIE API
            logger.info(f"🚀 Отправка запроса в KIE API...")
            api_result = await self.kie_client.create_task(model_id, api_params)
            result['api_response'] = api_result
            
            if api_result.get('ok'):
                task_id = api_result.get('taskId')
                result['task_id'] = task_id
                result['status'] = 'success'
                logger.info(f"✅ Задача успешно создана! Task ID: {task_id}")
                
                # Опционально: проверяем статус задачи
                if task_id:
                    logger.info(f"⏳ Проверка статуса задачи...")
                    await asyncio.sleep(2)  # Небольшая задержка
                    status_result = await self.kie_client.get_task_status(task_id)
                    if status_result.get('ok'):
                        state = status_result.get('state', 'unknown')
                        logger.info(f"📊 Статус задачи: {state}")
                        result['task_state'] = state
            else:
                error = api_result.get('error', 'Unknown error')
                result['status'] = 'failed'
                result['error'] = error
                logger.error(f"❌ Ошибка создания задачи: {error}")
                
                # Логируем полный ответ API для отладки
                logger.error(f"📋 Полный ответ API: {json.dumps(api_result, ensure_ascii=False, indent=2)}")
        
        except Exception as e:
            error_msg = f"Исключение при тестировании: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            result['status'] = 'failed'
            result['error'] = error_msg
        
        return result
    
    async def test_all_models(self, skip_expensive: bool = True):
        """Тестирует все модели"""
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 НАЧАЛО АВТОМАТИЧЕСКОГО ТЕСТИРОВАНИЯ ВСЕХ МОДЕЛЕЙ")
        logger.info(f"{'='*80}")
        logger.info(f"📅 Время начала: {datetime.now().isoformat()}")
        logger.info(f"📊 Всего моделей: {len(KIE_MODELS)}")
        logger.info(f"⏭️  Пропускать дорогие модели: {skip_expensive}")
        logger.info(f"{'='*80}\n")
        
        self.results['total_models'] = len(KIE_MODELS)
        
        # Дорогие модели, которые можно пропустить
        expensive_models = [
            'sora-2-pro-text-to-video', 'sora-2-pro-image-to-video',
            'sora-2-pro-storyboard', 'google/veo-3', 'google/veo-3.1'
        ]
        
        for model_info in KIE_MODELS:
            model_id = model_info.get('id')
            if not model_id:
                logger.warning(f"⚠️  Модель без ID пропущена: {model_info.get('name', 'Unknown')}")
                continue
            
            # Пропускаем дорогие модели, если указано
            if skip_expensive and model_id in expensive_models:
                logger.info(f"⏭️  Пропуск дорогой модели: {model_id}")
                self.results['skipped'] += 1
                continue
            
            # Тестируем модель
            result = await self.test_model_generation(model_id, model_info)
            self.results['results'].append(result)
            self.results['tested_models'] += 1
            
            if result['status'] == 'success':
                self.results['successful'] += 1
            elif result['status'] == 'failed':
                self.results['failed'] += 1
                self.results['errors'].append({
                    'model_id': model_id,
                    'error': result['error']
                })
            elif result['status'] == 'skipped':
                self.results['skipped'] += 1
            
            # Небольшая задержка между запросами
            await asyncio.sleep(1)
        
        # Сохраняем результаты
        self.save_results()
        
        # Выводим итоговый отчет
        self.print_summary()
    
    def save_results(self):
        """Сохраняет результаты тестирования в JSON файл"""
        filename = f"model_generation_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 Результаты сохранены в: {filename}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения результатов: {e}")
    
    def print_summary(self):
        """Выводит итоговый отчет"""
        logger.info(f"\n{'='*80}")
        logger.info(f"📊 ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ")
        logger.info(f"{'='*80}")
        logger.info(f"📅 Время завершения: {datetime.now().isoformat()}")
        logger.info(f"📦 Всего моделей: {self.results['total_models']}")
        logger.info(f"🧪 Протестировано: {self.results['tested_models']}")
        logger.info(f"✅ Успешно: {self.results['successful']}")
        logger.info(f"❌ Ошибки: {self.results['failed']}")
        logger.info(f"⏭️  Пропущено: {self.results['skipped']}")
        logger.info(f"{'='*80}\n")
        
        if self.results['errors']:
            logger.info(f"❌ ОШИБКИ:")
            for error in self.results['errors']:
                logger.info(f"  - {error['model_id']}: {error['error']}")
            logger.info("")
        
        # Статистика по статусам
        status_counts = {}
        for result in self.results['results']:
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        logger.info(f"📈 СТАТИСТИКА ПО СТАТУСАМ:")
        for status, count in status_counts.items():
            logger.info(f"  - {status}: {count}")
        logger.info("")


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Автоматическое тестирование генераций всех моделей KIE AI')
    parser.add_argument('--test-expensive', action='store_true', 
                       help='Тестировать дорогие модели (по умолчанию пропускаются)')
    parser.add_argument('--model', type=str, 
                       help='Тестировать только указанную модель (model_id)')
    
    args = parser.parse_args()
    
    tester = ModelGenerationTester()
    
    if args.model:
        # Тестируем только одну модель
        model_info = get_model_by_id(args.model)
        if not model_info:
            logger.error(f"❌ Модель не найдена: {args.model}")
            sys.exit(1)
        
        logger.info(f"🎯 Тестирование одной модели: {args.model}")
        result = await tester.test_model_generation(args.model, model_info)
        tester.results['results'].append(result)
        tester.results['tested_models'] = 1
        tester.results['total_models'] = 1
        
        if result['status'] == 'success':
            tester.results['successful'] = 1
        else:
            tester.results['failed'] = 1
        
        tester.save_results()
        tester.print_summary()
    else:
        # Тестируем все модели
        await tester.test_all_models(skip_expensive=not args.test_expensive)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Тестирование прервано пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
