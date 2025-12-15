"""
Скрипт для тестирования бесплатных и условно бесплатных инструментов
Тестирует каждый инструмент через реальные API запросы
"""

import asyncio
import aiohttp
import os
import json
import sys
import io
from datetime import datetime
from dotenv import load_dotenv
from kie_client import KIEClient

# Устанавливаем UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Загружаем переменные окружения
load_dotenv()

# Результаты тестирования
test_results = {
    "z-image": {"status": "pending", "error": None, "task_id": None, "result_url": None},
    "recraft/remove-background": {"status": "pending", "error": None, "task_id": None, "result_url": None},
    "recraft/crisp-upscale": {"status": "pending", "error": None, "task_id": None, "result_url": None}
}

# Тестовые данные
TEST_DATA = {
    "z-image": {
        "prompt": "A beautiful sunset over mountains, digital art, vibrant colors",
        "aspect_ratio": "1:1"
    },
    "recraft/remove-background": {
        "image": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400"  # Тестовое изображение
    },
    "recraft/crisp-upscale": {
        "image": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400"  # Тестовое изображение
    }
}


async def create_task(client: KIEClient, model_id: str, input_params: dict) -> dict:
    """Создает задачу генерации через API"""
    try:
        result = await client.create_task(model_id, input_params)
        if not result.get('ok'):
            raise Exception(result.get('error', 'Unknown error'))
        return {'code': 200, 'data': {'taskId': result.get('taskId')}}
    except Exception as e:
        raise Exception(f"Ошибка при создании задачи: {str(e)}")


async def query_task(client: KIEClient, task_id: str) -> dict:
    """Запрашивает статус задачи"""
    try:
        result = await client.get_task_status(task_id)
        if not result.get('ok'):
            raise Exception(result.get('error', 'Unknown error'))
        return {
            'code': 200,
            'data': {
                'taskId': result.get('taskId'),
                'state': result.get('state'),
                'resultJson': result.get('resultJson'),
                'failCode': result.get('failCode'),
                'failMsg': result.get('failMsg')
            }
        }
    except Exception as e:
        raise Exception(f"Ошибка при запросе статуса: {str(e)}")


async def wait_for_task_completion(client: KIEClient, task_id: str, max_wait_time: int = 120) -> dict:
    """Ожидает завершения задачи с проверкой статуса"""
    start_time = asyncio.get_event_loop().time()
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait_time:
            raise TimeoutError(f"Задача {task_id} не завершилась за {max_wait_time} секунд")
        
        result = await query_task(client, task_id)
        
        if result.get('code') != 200:
            raise Exception(f"Ошибка API: {result.get('message', 'Unknown error')}")
        
        data = result.get('data', {})
        state = data.get('state', 'unknown')
        
        if state == 'success':
            return result
        elif state == 'fail':
            fail_msg = data.get('failMsg', 'Unknown error')
            fail_code = data.get('failCode', 'Unknown')
            raise Exception(f"Задача завершилась с ошибкой: {fail_code} - {fail_msg}")
        elif state in ['waiting', 'queuing', 'generating']:
            # Ждем еще
            await asyncio.sleep(3)
        else:
            raise Exception(f"Неизвестный статус задачи: {state}")
    
    return result


async def test_z_image(client: KIEClient):
    """Тестирует Z-Image (условно бесплатно - 5 раз в день)"""
    print("\n" + "="*80)
    print("🧪 ТЕСТИРОВАНИЕ: Z-Image (условно бесплатно - 5 раз в день)")
    print("="*80)
    
    model_id = "z-image"
    input_params = TEST_DATA[model_id]
    
    print(f"\n[INFO] Параметры:")
    print(f"  Model: {model_id}")
    print(f"  Prompt: {input_params['prompt']}")
    print(f"  Aspect Ratio: {input_params['aspect_ratio']}")
    
    try:
        print(f"\n[1/3] Создание задачи...")
        result = await create_task(client, model_id, input_params)
        
        if result.get('code') != 200:
            raise Exception(f"Ошибка создания задачи: {result.get('message', 'Unknown error')}")
        
        task_id = result.get('data', {}).get('taskId')
        if not task_id:
            raise Exception("Не получен taskId от API")
        
        test_results[model_id]["task_id"] = task_id
        print(f"  ✅ Задача создана: {task_id}")
        
        print(f"\n[2/3] Ожидание завершения генерации (макс. 120 сек)...")
        final_result = await wait_for_task_completion(client, task_id, max_wait_time=120)
        
        data = final_result.get('data', {})
        result_json = data.get('resultJson', '{}')
        
        try:
            result_data = json.loads(result_json)
            result_urls = result_data.get('resultUrls', [])
            if result_urls:
                test_results[model_id]["result_url"] = result_urls[0]
                print(f"  ✅ Генерация завершена успешно!")
                print(f"  📸 Результат: {result_urls[0]}")
            else:
                raise Exception("Не получены URL результатов")
        except json.JSONDecodeError:
            raise Exception(f"Не удалось распарсить resultJson: {result_json}")
        
        test_results[model_id]["status"] = "success"
        print(f"\n✅ Z-Image: ТЕСТ ПРОЙДЕН УСПЕШНО")
        
    except Exception as e:
        test_results[model_id]["status"] = "failed"
        test_results[model_id]["error"] = str(e)
        print(f"\n❌ Z-Image: ОШИБКА - {str(e)}")


async def test_recraft_remove_background(client: KIEClient):
    """Тестирует Recraft Remove Background (бесплатно и безлимитно)"""
    print("\n" + "="*80)
    print("🧪 ТЕСТИРОВАНИЕ: Recraft Remove Background (бесплатно и безлимитно)")
    print("="*80)
    
    model_id = "recraft/remove-background"
    input_params = {"image": TEST_DATA[model_id]["image"]}
    
    print(f"\n[INFO] Параметры:")
    print(f"  Model: {model_id}")
    print(f"  Image URL: {input_params['image']}")
    
    try:
        print(f"\n[1/3] Создание задачи...")
        result = await create_task(client, model_id, input_params)
        
        if result.get('code') != 200:
            raise Exception(f"Ошибка создания задачи: {result.get('message', 'Unknown error')}")
        
        task_id = result.get('data', {}).get('taskId')
        if not task_id:
            raise Exception("Не получен taskId от API")
        
        test_results[model_id]["task_id"] = task_id
        print(f"  ✅ Задача создана: {task_id}")
        
        print(f"\n[2/3] Ожидание завершения генерации (макс. 120 сек)...")
        final_result = await wait_for_task_completion(client, task_id, max_wait_time=120)
        
        data = final_result.get('data', {})
        result_json = data.get('resultJson', '{}')
        
        try:
            result_data = json.loads(result_json)
            result_urls = result_data.get('resultUrls', [])
            if result_urls:
                test_results[model_id]["result_url"] = result_urls[0]
                print(f"  ✅ Генерация завершена успешно!")
                print(f"  📸 Результат: {result_urls[0]}")
            else:
                raise Exception("Не получены URL результатов")
        except json.JSONDecodeError:
            raise Exception(f"Не удалось распарсить resultJson: {result_json}")
        
        test_results[model_id]["status"] = "success"
        print(f"\n✅ Recraft Remove Background: ТЕСТ ПРОЙДЕН УСПЕШНО")
        
    except Exception as e:
        test_results[model_id]["status"] = "failed"
        test_results[model_id]["error"] = str(e)
        print(f"\n❌ Recraft Remove Background: ОШИБКА - {str(e)}")


async def test_recraft_crisp_upscale(client: KIEClient):
    """Тестирует Recraft Crisp Upscale (бесплатно и безлимитно)"""
    print("\n" + "="*80)
    print("🧪 ТЕСТИРОВАНИЕ: Recraft Crisp Upscale (бесплатно и безлимитно)")
    print("="*80)
    
    model_id = "recraft/crisp-upscale"
    input_params = {"image": TEST_DATA[model_id]["image"]}
    
    print(f"\n[INFO] Параметры:")
    print(f"  Model: {model_id}")
    print(f"  Image URL: {input_params['image']}")
    
    try:
        print(f"\n[1/3] Создание задачи...")
        result = await create_task(client, model_id, input_params)
        
        if result.get('code') != 200:
            raise Exception(f"Ошибка создания задачи: {result.get('message', 'Unknown error')}")
        
        task_id = result.get('data', {}).get('taskId')
        if not task_id:
            raise Exception("Не получен taskId от API")
        
        test_results[model_id]["task_id"] = task_id
        print(f"  ✅ Задача создана: {task_id}")
        
        print(f"\n[2/3] Ожидание завершения генерации (макс. 120 сек)...")
        final_result = await wait_for_task_completion(client, task_id, max_wait_time=120)
        
        data = final_result.get('data', {})
        result_json = data.get('resultJson', '{}')
        
        try:
            result_data = json.loads(result_json)
            result_urls = result_data.get('resultUrls', [])
            if result_urls:
                test_results[model_id]["result_url"] = result_urls[0]
                print(f"  ✅ Генерация завершена успешно!")
                print(f"  📸 Результат: {result_urls[0]}")
            else:
                raise Exception("Не получены URL результатов")
        except json.JSONDecodeError:
            raise Exception(f"Не удалось распарсить resultJson: {result_json}")
        
        test_results[model_id]["status"] = "success"
        print(f"\n✅ Recraft Crisp Upscale: ТЕСТ ПРОЙДЕН УСПЕШНО")
        
    except Exception as e:
        test_results[model_id]["status"] = "failed"
        test_results[model_id]["error"] = str(e)
        print(f"\n❌ Recraft Crisp Upscale: ОШИБКА - {str(e)}")


async def main():
    """Главная функция тестирования"""
    print("="*80)
    print("🚀 ТЕСТИРОВАНИЕ БЕСПЛАТНЫХ И УСЛОВНО БЕСПЛАТНЫХ ИНСТРУМЕНТОВ")
    print("="*80)
    print(f"\nВремя начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Проверяем наличие API ключа
    api_key = os.getenv('KIE_API_KEY')
    if not api_key:
        print("\n❌ ОШИБКА: KIE_API_KEY не найден в переменных окружения!")
        print("   Убедитесь, что файл .env содержит KIE_API_KEY")
        return
    
    print(f"\n✅ API ключ найден")
    
    # Создаем клиент
    client = KIEClient()
    
    # Тестируем каждый инструмент
    print("\n" + "="*80)
    print("НАЧАЛО ТЕСТИРОВАНИЯ")
    print("="*80)
    
    # 1. Z-Image (условно бесплатно)
    await test_z_image(client)
    
    # 2. Recraft Remove Background (бесплатно)
    await test_recraft_remove_background(client)
    
    # 3. Recraft Crisp Upscale (бесплатно)
    await test_recraft_crisp_upscale(client)
    
    # Итоговый отчет
    print("\n" + "="*80)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("="*80)
    print(f"\nВремя завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results.values() if r["status"] == "success")
    failed_tests = total_tests - passed_tests
    
    print(f"Всего тестов: {total_tests}")
    print(f"✅ Успешно: {passed_tests}")
    print(f"❌ Ошибок: {failed_tests}\n")
    
    for model_id, result in test_results.items():
        status_emoji = "✅" if result["status"] == "success" else "❌"
        print(f"{status_emoji} {model_id}: {result['status'].upper()}")
        if result["task_id"]:
            print(f"   Task ID: {result['task_id']}")
        if result["result_url"]:
            print(f"   Result: {result['result_url']}")
        if result["error"]:
            print(f"   Error: {result['error']}")
        print()
    
    if failed_tests == 0:
        print("="*80)
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*80)
        return 0
    else:
        print("="*80)
        print("⚠️  НЕКОТОРЫЕ ТЕСТЫ ЗАВЕРШИЛИСЬ С ОШИБКАМИ")
        print("="*80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

