"""
Валидация входных данных для модели bytedance/v1-pro-image-to-video
"""

def validate_bytedance_v1_pro_image_to_video_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели bytedance/v1-pro-image-to-video
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors)
    """
    errors = []
    
    # 1. Проверка prompt (обязательный)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка image_input/image_url (обязательный)
    # Модель ожидает image_input как массив или image_url как строку
    image_input = None
    if 'image_input' in data:
        image_input = data['image_input']
    elif 'image_url' in data:
        # Конвертируем image_url в image_input (массив) или оставляем как строку
        if data['image_url']:
            image_input = data['image_url']
    
    if not image_input:
        errors.append("[ERROR] Параметр 'image_input' или 'image_url' обязателен и не может быть пустым")
    else:
        # Проверяем, что это строка (URL) или массив
        if isinstance(image_input, list):
            if len(image_input) == 0:
                errors.append("[ERROR] Параметр 'image_input' не может быть пустым массивом")
            elif len(image_input) > 1:
                errors.append("[ERROR] Параметр 'image_input' должен содержать только 1 изображение (максимум 1 элемент)")
            else:
                if not isinstance(image_input[0], str) or not image_input[0]:
                    errors.append("[ERROR] URL изображения должен быть непустой строкой")
        elif isinstance(image_input, str):
            if len(image_input) == 0:
                errors.append("[ERROR] URL изображения должен быть непустой строкой")
        else:
            errors.append("[ERROR] Параметр 'image_input' или 'image_url' должен быть строкой (URL) или массивом")
    
    # 3. Проверка resolution (опциональный, enum)
    # Модель ожидает: ["480p", "720p", "1080p"]
    valid_resolutions = ["480p", "720p", "1080p"]
    if 'resolution' in data and data['resolution']:
        resolution = str(data['resolution'])
        if resolution not in valid_resolutions:
            errors.append(f"[ERROR] Параметр 'resolution' имеет недопустимое значение: '{resolution}'. Допустимые значения: {', '.join(valid_resolutions)}")
    
    # 4. Проверка duration (опциональный, enum)
    # Модель ожидает: ["5s", "10s"] или ["5", "10"]
    valid_durations = ["5s", "10s", "5", "10"]
    if 'duration' in data and data['duration']:
        duration = str(data['duration'])
        # Нормализуем значение (убираем пробелы)
        duration = duration.strip()
        if duration not in valid_durations:
            errors.append(f"[ERROR] Параметр 'duration' имеет недопустимое значение: '{data['duration']}'. Допустимые значения: {', '.join(valid_durations)}")
    
    # 5. Проверка camera_fixed (опциональный, boolean)
    if 'camera_fixed' in data and data['camera_fixed'] is not None:
        camera_fixed = data['camera_fixed']
        if not isinstance(camera_fixed, bool):
            # Попытка конвертации строки в boolean
            if isinstance(camera_fixed, str):
                if camera_fixed.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[ERROR] Параметр 'camera_fixed' должен быть boolean (true/false), получено: {camera_fixed}")
            else:
                errors.append(f"[ERROR] Параметр 'camera_fixed' должен быть boolean, получено: {type(camera_fixed).__name__}")
    
    # 6. Проверка seed (опциональный, integer)
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Seed может быть любым целым числом, включая -1 для случайного
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть целым числом, получено: {data['seed']}")
    
    # 7. Проверка enable_safety_checker (опциональный, boolean)
    if 'enable_safety_checker' in data and data['enable_safety_checker'] is not None:
        enable_safety_checker = data['enable_safety_checker']
        if not isinstance(enable_safety_checker, bool):
            # Попытка конвертации строки в boolean
            if isinstance(enable_safety_checker, str):
                if enable_safety_checker.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[ERROR] Параметр 'enable_safety_checker' должен быть boolean (true/false), получено: {enable_safety_checker}")
            else:
                errors.append(f"[ERROR] Параметр 'enable_safety_checker' должен быть boolean, получено: {type(enable_safety_checker).__name__}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A golden retriever dashing through shallow surf at the beach, back angle camera low near waterline, splashes frozen in time, blur trails in waves and paws, afternoon sun glinting off wet fur, overcast day, dramatic clouds",
    "image_url": "Upload successfully",  # Это будет URL после загрузки
    "resolution": "",  # Не указан - опциональный
    "duration": "5s",  # Указан с "s"
    "camera_fixed": None,  # Не указан - опциональный
    "seed": "-1",  # Указан -1 для случайного
    "enable_safety_checker": None  # Не указан - опциональный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для bytedance/v1-pro-image-to-video")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  resolution: '{test_data['resolution']}' (не указан - опциональный)")
    print(f"  duration: '{test_data['duration']}'")
    print(f"  camera_fixed: {test_data['camera_fixed']} (не указан - опциональный)")
    print(f"  seed: '{test_data['seed']}'")
    print(f"  enable_safety_checker: {test_data['enable_safety_checker']} (не указан - опциональный)")
    print()
    
    is_valid, errors = validate_bytedance_v1_pro_image_to_video_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов [OK]")
        print(f"  - image_url: указан (будет использован для генерации видео) [OK]")
        if test_data.get('resolution'):
            print(f"  - resolution: '{test_data['resolution']}' - валидное значение [OK]")
        else:
            print(f"  - resolution: не указан (опциональный) [OK]")
        
        # Нормализация duration
        duration = str(test_data['duration']).strip()
        print(f"  - duration: '{test_data['duration']}' - валидное значение [OK]")
        
        print(f"  - camera_fixed: опциональный, не указан [OK]")
        
        if test_data.get('seed'):
            try:
                seed_val = int(test_data['seed'])
                if seed_val == -1:
                    print(f"  - seed: {seed_val} - случайный seed [OK]")
                else:
                    print(f"  - seed: {seed_val} - валидное значение [OK]")
            except:
                print(f"  - seed: '{test_data['seed']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - seed: опциональный, не указан [OK]")
        
        print(f"  - enable_safety_checker: опциональный, не указан [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Это модель image-to-video (требует image_url или image_input)")
        print("  - resolution влияет на скорость и качество: 480p (быстрее), 720p (баланс), 1080p (выше качество)")
        print("  - duration определяет длительность видео (5s или 10s)")
        print("  - camera_fixed - фиксация позиции камеры")
        print("  - seed: -1 для случайного значения, любое целое число для воспроизводимости")
        print("  - enable_safety_checker: по умолчанию включен в Playground, можно отключить через API")
    else:
        print("[ERROR] ОБНАРУЖЕНЫ ОШИБКИ:")
        print()
        for error in errors:
            print(f"  {error}")
    
    print()
    print("=" * 60)
    
    # Дополнительная проверка: формат для API
    print()
    print("[API] Формат данных для отправки в API:")
    api_data = {}
    
    # prompt - обязательный
    api_data['prompt'] = test_data['prompt']
    
    # image_input/image_url - обязательный
    if 'image_url' in test_data and test_data['image_url']:
        # Модель может принимать как image_url (строка), так и image_input (массив)
        # Проверяем, что это не placeholder
        if test_data['image_url'] not in ["Upload successfully", "Click to upload or drag and drop", ""]:
            api_data['image_url'] = test_data['image_url']
        # Или можно использовать image_input как массив
        # api_data['image_input'] = [test_data['image_url']]
    elif 'image_input' in test_data:
        api_data['image_input'] = test_data['image_input']
    
    # resolution - только если указан
    if test_data.get('resolution'):
        api_data['resolution'] = test_data['resolution']
    # Иначе не включаем (будет использован default)
    
    # duration - опциональный, но можно указать default
    if test_data.get('duration'):
        duration = str(test_data['duration']).strip()
        api_data['duration'] = duration
    else:
        api_data['duration'] = "5s"  # default
    
    # camera_fixed - только если указан
    if test_data.get('camera_fixed') is not None:
        api_data['camera_fixed'] = bool(test_data['camera_fixed'])
    # Иначе не включаем
    
    # seed - только если указан (как integer!)
    if test_data.get('seed'):
        try:
            api_data['seed'] = int(test_data['seed'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный seed
    
    # enable_safety_checker - только если указан
    if test_data.get('enable_safety_checker') is not None:
        api_data['enable_safety_checker'] = bool(test_data['enable_safety_checker'])
    # Иначе не включаем (будет использован default - включен)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

