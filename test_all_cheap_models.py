"""
Скрипт для тестирования всех моделей дешевле 0.1 доллара (10 кредитов)
Тестирует только валидацию параметров без реальных API запросов (без списания кредитов)
"""

import sys
import io
import json
from kie_models import KIE_MODELS, get_model_by_id

# Упрощенная функция расчета цены (только для моделей дешевле 10 кредитов)
def calculate_price_credits(model_id: str, params: dict = None) -> float:
    """Рассчитывает цену в кредитах для модели"""
    if params is None:
        params = {}
    
    # Модели дешевле 10 кредитов
    if model_id == "z-image":
        return 0.8
    elif model_id == "google/nano-banana" or model_id == "google/nano-banana-edit":
        return 4.0
    elif model_id == "seedream/4.5-text-to-image" or model_id == "seedream/4.5-edit":
        return 6.5
    elif model_id == "bytedance/seedream-v4-text-to-image" or model_id == "bytedance/seedream-v4-edit":
        max_images = params.get("max_images", 1)
        return 5.0 * max_images
    elif model_id == "bytedance/seedream":
        return 3.5
    elif model_id == "recraft/remove-background" or model_id == "recraft/crisp-upscale":
        return 0.0
    elif model_id == "sora-watermark-remover":
        return 10.0
    elif model_id == "ideogram/v3-reframe" or model_id == "ideogram/v3-text-to-image" or model_id == "ideogram/v3-edit" or model_id == "ideogram/v3-remix":
        rendering_speed = params.get("rendering_speed", "TURBO")
        num_images = int(params.get("num_images", "1"))
        if rendering_speed == "TURBO":
            return 3.5 * num_images
        elif rendering_speed == "BALANCED":
            return 7.0 * num_images
        else:  # QUALITY
            return 10.0 * num_images
    elif model_id == "qwen/text-to-image":
        image_size = params.get("image_size", "square_hd")
        mp_map = {
            "square": 0.26,
            "square_hd": 1.05,
            "portrait_4_3": 0.79,
            "portrait_16_9": 1.84,
            "landscape_4_3": 0.79,
            "landscape_16_9": 1.84
        }
        megapixels = mp_map.get(image_size, 1.05)
        return 4.0 * megapixels
    elif model_id == "qwen/image-to-image":
        return 4.0
    elif model_id == "qwen/image-edit":
        image_size = params.get("image_size", "landscape_4_3")
        num_images = int(params.get("num_images", "1"))
        mp_map = {
            "square": 0.26,
            "square_hd": 1.05,
            "portrait_4_3": 0.79,
            "portrait_16_9": 1.84,
            "landscape_4_3": 0.79,
            "landscape_16_9": 1.84
        }
        megapixels = mp_map.get(image_size, 0.79)
        return 6.0 * megapixels * num_images
    elif model_id == "google/imagen4-fast":
        num_images = int(params.get("num_images", "1"))
        return 4.0 * num_images
    elif model_id == "elevenlabs/speech-to-text":
        # 3.5 кредитов за минуту, для теста используем минимальную цену
        return 3.5
    elif model_id == "hailuo/02-image-to-video-standard":
        resolution = params.get("resolution", "512P")
        duration = int(params.get("duration", "6"))
        if resolution == "512P":
            # Минимальная цена при 1 секунде = 2 кредита
            return 2.0 * max(duration, 1)
        else:  # 768P
            return 5.0 * max(duration, 1)
    elif model_id == "hailuo/02-text-to-video-standard":
        duration = int(params.get("duration", "6"))
        # Минимальная цена при 1 секунде = 5 кредитов
        return 5.0 * max(duration, 1)
    elif model_id == "infinitalk/from-audio":
        resolution = params.get("resolution", "480p")
        # Минимальная длительность для теста - 1 секунда
        default_duration = 1
        if resolution == "720p":
            return 12.0 * default_duration
        else:  # 480p
            # При 480p и 1 секунде = 3 кредита (дешевле 10)
            return 3.0 * default_duration
    elif model_id == "hailuo/2-3-image-to-video-standard":
        resolution = params.get("resolution", "768P")
        duration = int(params.get("duration", "6"))
        if resolution == "1080P":
            return 7.0 * duration
        else:  # 768P
            return 5.0 * duration
    elif model_id == "hailuo/2-3-image-to-video-pro":
        resolution = params.get("resolution", "768P")
        duration = int(params.get("duration", "6"))
        if resolution == "1080P":
            return 9.5 * duration
        else:  # 768P
            return 5.0 * duration
    elif model_id == "wan/2-2-animate-move" or model_id == "wan/2-2-animate-replace":
        resolution = params.get("resolution", "480p")
        default_duration = 5
        if resolution == "720p":
            return 12.5 * default_duration
        elif resolution == "580p":
            return 9.5 * default_duration
        else:  # 480p
            return 6.0 * default_duration
    elif model_id == "wan/2-2-a14b-text-to-video-turbo" or model_id == "wan/2-2-a14b-image-to-video-turbo":
        resolution = params.get("resolution", "480p")
        default_duration = 5
        if resolution == "720p":
            return 16.0 * default_duration
        elif resolution == "580p":
            return 12.0 * default_duration
        else:  # 480p
            return 8.0 * default_duration
    
    # Если модель не найдена, возвращаем большое значение
    return 999.0

# Устанавливаем UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Максимальная цена в кредитах (0.1 доллара = 10 кредитов)
MAX_PRICE_CREDITS = 10.0

# Результаты тестирования
test_results = {}


def get_test_params_for_model(model_id: str, model_info: dict) -> dict:
    """Генерирует тестовые параметры для модели"""
    input_params = model_info.get('input_params', {})
    test_params = {}
    
    for param_name, param_info in input_params.items():
        param_type = param_info.get('type', 'string')
        required = param_info.get('required', False)
        default = param_info.get('default')
        enum_values = param_info.get('enum', [])
        max_length = param_info.get('max_length')
        
        if not required and default is None:
            # Пропускаем необязательные параметры без default
            continue
        
        if param_type == 'string':
            if enum_values:
                # Для моделей с переменной ценой выбираем минимальное значение
                if param_name == 'resolution' and '512P' in enum_values:
                    test_params[param_name] = '512P'  # Минимальная цена
                elif param_name == 'resolution' and '480p' in enum_values:
                    test_params[param_name] = '480p'  # Минимальная цена
                elif param_name == 'duration' and '1' in enum_values:
                    test_params[param_name] = '1'  # Минимальная длительность
                else:
                    # Используем первое значение из enum
                    test_params[param_name] = enum_values[0]
            elif param_name == 'prompt':
                # Для prompt используем короткий тестовый текст
                max_len = min(max_length or 100, 50)
                test_params[param_name] = "Test prompt for validation"[:max_len]
            elif param_name in ['image_url', 'audio_url']:
                # Для URL используем тестовый URL
                test_params[param_name] = "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400"
            else:
                test_params[param_name] = "test_value"
        elif param_type == 'number' or param_type == 'integer':
            # Для duration используем минимальное значение (1) если это параметр длительности
            if param_name == 'duration':
                test_params[param_name] = 1
            else:
                test_params[param_name] = param_info.get('default', 1)
        elif param_type == 'boolean':
            test_params[param_name] = param_info.get('default', False)
        elif param_type == 'array':
            if param_name in ['image_input', 'image_urls']:
                # Для изображений используем тестовый URL
                test_params[param_name] = ["https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400"]
            else:
                test_params[param_name] = ["test_item"]
        else:
            if default is not None:
                test_params[param_name] = default
            elif required:
                test_params[param_name] = "test_value"
    
    return test_params


def validate_model_params(model_id: str, model_info: dict, test_params: dict) -> tuple[bool, list]:
    """Валидирует параметры модели"""
    errors = []
    input_params = model_info.get('input_params', {})
    
    # Проверяем обязательные параметры
    for param_name, param_info in input_params.items():
        if param_info.get('required', False):
            if param_name not in test_params or not test_params[param_name]:
                errors.append(f"Отсутствует обязательный параметр: {param_name}")
                continue
            
            # Проверяем тип
            param_type = param_info.get('type', 'string')
            value = test_params[param_name]
            
            if param_type == 'string':
                if not isinstance(value, str):
                    errors.append(f"Параметр {param_name} должен быть строкой")
                else:
                    max_length = param_info.get('max_length')
                    if max_length and len(value) > max_length:
                        errors.append(f"Параметр {param_name} слишком длинный: {len(value)} > {max_length}")
                    
                    enum_values = param_info.get('enum', [])
                    if enum_values and value not in enum_values:
                        errors.append(f"Параметр {param_name} имеет недопустимое значение: {value}. Допустимые: {enum_values}")
            
            elif param_type == 'array':
                if not isinstance(value, list):
                    errors.append(f"Параметр {param_name} должен быть массивом")
                else:
                    min_items = param_info.get('min_items')
                    max_items = param_info.get('max_items')
                    if min_items and len(value) < min_items:
                        errors.append(f"Параметр {param_name} должен содержать минимум {min_items} элементов")
                    if max_items and len(value) > max_items:
                        errors.append(f"Параметр {param_name} должен содержать максимум {max_items} элементов")
            
            elif param_type in ['number', 'integer']:
                if not isinstance(value, (int, float)):
                    errors.append(f"Параметр {param_name} должен быть числом")
    
    return len(errors) == 0, errors


def test_model(model_id: str, model_info: dict) -> dict:
    """Тестирует одну модель"""
    result = {
        "model_id": model_id,
        "name": model_info.get('name', model_id),
        "status": "pending",
        "errors": [],
        "warnings": [],
        "price_credits": None,
        "price_rub": None,
        "test_params": {}
    }
    
    try:
        # 1. Проверяем цену
        test_params = get_test_params_for_model(model_id, model_info)
        price_credits = calculate_price_credits(model_id, test_params)
        
        # Конвертируем в кредиты (1 кредит = 1 рубль примерно, но нужно проверить)
        # Для простоты считаем, что цена уже в кредитах
        result["price_credits"] = price_credits
        result["price_rub"] = price_credits
        
        if price_credits > MAX_PRICE_CREDITS:
            result["status"] = "skipped"
            result["warnings"].append(f"Цена {price_credits} кредитов превышает лимит {MAX_PRICE_CREDITS}")
            return result
        
        # 2. Генерируем тестовые параметры
        result["test_params"] = test_params
        
        # 3. Валидируем параметры
        is_valid, errors = validate_model_params(model_id, model_info, test_params)
        
        if is_valid:
            result["status"] = "success"
        else:
            result["status"] = "failed"
            result["errors"] = errors
        
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(f"Ошибка при тестировании: {str(e)}")
    
    return result


def main():
    """Главная функция тестирования"""
    print("="*80)
    print("🧪 ТЕСТИРОВАНИЕ ВСЕХ МОДЕЛЕЙ ДЕШЕВЛЕ 0.1 ДОЛЛАРА (10 КРЕДИТОВ)")
    print("="*80)
    print("\nТестирование валидации параметров без реальных API запросов\n")
    
    # Находим все модели дешевле 10 кредитов
    cheap_models = []
    
    for model in KIE_MODELS:
        model_id = model.get('id')
        if not model_id:
            continue
        
        # Пропускаем модели со статусом "coming_soon"
        if model.get('coming_soon', False):
            continue
        
        try:
            # Пробуем рассчитать минимальную цену с минимальными параметрами
            test_params = get_test_params_for_model(model_id, model)
            
            # Для моделей с переменной ценой пробуем найти минимальную цену
            # Проверяем разные комбинации параметров для минимизации цены
            min_price = calculate_price_credits(model_id, test_params)
            
            # Для моделей с разрешением пробуем минимальное разрешение
            input_params = model.get('input_params', {})
            if 'resolution' in input_params:
                resolution_enum = input_params['resolution'].get('enum', [])
                if resolution_enum:
                    # Пробуем минимальное разрешение
                    test_params_min = test_params.copy()
                    # Выбираем разрешение с минимальной ценой
                    if '512P' in resolution_enum:
                        test_params_min['resolution'] = '512P'
                    elif '480p' in resolution_enum:
                        test_params_min['resolution'] = '480p'
                    elif '720p' in resolution_enum:
                        test_params_min['resolution'] = '720p'
                    price_min = calculate_price_credits(model_id, test_params_min)
                    min_price = min(min_price, price_min)
            
            # Для моделей с длительностью пробуем минимальную длительность
            if 'duration' in input_params:
                duration_enum = input_params['duration'].get('enum', [])
                if duration_enum:
                    # Пробуем минимальную длительность
                    test_params_min = test_params.copy()
                    # Выбираем минимальную длительность из enum
                    min_duration = min([int(d) for d in duration_enum if d.isdigit()], default=6)
                    test_params_min['duration'] = str(min_duration)
                    price_min = calculate_price_credits(model_id, test_params_min)
                    min_price = min(min_price, price_min)
            
            if min_price <= MAX_PRICE_CREDITS:
                cheap_models.append((model_id, model, min_price))
        except Exception as e:
            # Игнорируем ошибки для моделей, которые не поддерживаются в упрощенной функции
            pass
    
    print(f"Найдено моделей дешевле {MAX_PRICE_CREDITS} кредитов: {len(cheap_models)}\n")
    print("="*80)
    print("НАЧАЛО ТЕСТИРОВАНИЯ")
    print("="*80)
    print()
    
    # Тестируем каждую модель
    for idx, (model_id, model_info, price) in enumerate(cheap_models, 1):
        print(f"\n[{idx}/{len(cheap_models)}] Тестирование: {model_id}")
        print(f"  Название: {model_info.get('name', 'N/A')}")
        print(f"  Цена: {price} кредитов")
        
        result = test_model(model_id, model_info)
        test_results[model_id] = result
        
        if result["status"] == "success":
            print(f"  ✅ УСПЕШНО")
        elif result["status"] == "skipped":
            print(f"  ⏭️  ПРОПУЩЕНО: {', '.join(result['warnings'])}")
        else:
            print(f"  ❌ ОШИБКА")
            for error in result["errors"]:
                print(f"     - {error}")
    
    # Итоговый отчет
    print("\n" + "="*80)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("="*80)
    
    total = len(test_results)
    success = sum(1 for r in test_results.values() if r["status"] == "success")
    failed = sum(1 for r in test_results.values() if r["status"] == "failed")
    errors = sum(1 for r in test_results.values() if r["status"] == "error")
    skipped = sum(1 for r in test_results.values() if r["status"] == "skipped")
    
    print(f"\nВсего протестировано: {total}")
    print(f"✅ Успешно: {success}")
    print(f"❌ Ошибки валидации: {failed}")
    print(f"⚠️  Ошибки выполнения: {errors}")
    print(f"⏭️  Пропущено: {skipped}\n")
    
    # Детальный отчет по успешным
    if success > 0:
        print("✅ УСПЕШНО ПРОТЕСТИРОВАННЫЕ МОДЕЛИ:")
        for model_id, result in test_results.items():
            if result["status"] == "success":
                print(f"  • {model_id} ({result['name']}) - {result['price_credits']} кредитов")
        print()
    
    # Детальный отчет по ошибкам
    if failed > 0 or errors > 0:
        print("❌ МОДЕЛИ С ОШИБКАМИ:")
        for model_id, result in test_results.items():
            if result["status"] in ["failed", "error"]:
                print(f"  • {model_id} ({result['name']})")
                for error in result["errors"]:
                    print(f"    - {error}")
        print()
    
    # Сохраняем результаты в JSON
    output_file = "cheap_models_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    print(f"📄 Результаты сохранены в: {output_file}")
    
    if failed == 0 and errors == 0:
        print("\n" + "="*80)
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*80)
        return 0
    else:
        print("\n" + "="*80)
        print("⚠️  НЕКОТОРЫЕ ТЕСТЫ ЗАВЕРШИЛИСЬ С ОШИБКАМИ")
        print("="*80)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

