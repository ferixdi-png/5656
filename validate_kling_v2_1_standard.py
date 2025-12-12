"""
Валидация входных данных для модели kling/v2-1-standard
"""

def validate_kling_v2_1_standard_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели kling/v2-1-standard
    
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
        if len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 5000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка image_input/image_url (обязательный)
    # Модель ожидает image_input как массив, но пользователь может передать image_url
    image_input = None
    if 'image_input' in data:
        image_input = data['image_input']
    elif 'image_url' in data:
        # Конвертируем image_url в image_input (массив)
        image_input = [data['image_url']] if data['image_url'] else None
    
    if not image_input:
        errors.append("[ERROR] Параметр 'image_input' или 'image_url' обязателен и не может быть пустым")
    else:
        # Проверяем, что это массив
        if not isinstance(image_input, list):
            errors.append("[ERROR] Параметр 'image_input' должен быть массивом (списком)")
        elif len(image_input) == 0:
            errors.append("[ERROR] Параметр 'image_input' не может быть пустым массивом")
        elif len(image_input) > 1:
            errors.append("[ERROR] Параметр 'image_input' должен содержать только 1 изображение (максимум 1 элемент)")
        else:
            # Проверяем, что это строка (URL)
            if not isinstance(image_input[0], str) or not image_input[0]:
                errors.append("[ERROR] URL изображения должен быть непустой строкой")
    
    # 3. Проверка duration (опциональный, enum)
    # Модель ожидает: ["5", "10"]
    # Форма может передавать: "5 seconds", "10 seconds"
    valid_durations = ["5", "10"]
    if 'duration' in data and data['duration']:
        duration = str(data['duration'])
        # Нормализуем значение (убираем " seconds" если есть)
        if " seconds" in duration.lower() or " second" in duration.lower():
            duration = duration.lower().replace(" seconds", "").replace(" second", "").strip()
        
        if duration not in valid_durations:
            errors.append(f"[ERROR] Параметр 'duration' имеет недопустимое значение: '{data['duration']}'. Допустимые значения: {', '.join(valid_durations)}")
    
    # 4. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 500)")
    
    # 5. Проверка cfg_scale (опциональный, number)
    # ВАЖНО: В модели это float от 0 до 1 с шагом 0.1
    if 'cfg_scale' in data and data['cfg_scale']:
        try:
            # Обработка запятой как разделителя десятичных (0,5 -> 0.5)
            cfg_scale_str = str(data['cfg_scale']).replace(',', '.')
            cfg_scale = float(cfg_scale_str)
            
            if cfg_scale < 0 or cfg_scale > 1:
                errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть в диапазоне от 0 до 1, получено: {cfg_scale}")
            else:
                # Проверяем шаг 0.1 (округление до 1 знака после запятой)
                rounded = round(cfg_scale, 1)
                if abs(cfg_scale - rounded) > 0.01:
                    errors.append(f"[WARNING] Параметр 'cfg_scale' должен иметь шаг 0.1, получено: {cfg_scale}. Будет округлено до {rounded}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть числом (0-1), получено: {data['cfg_scale']}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Begin with the uploaded image as the first frame. Gradually animate the scene: steam rises and drifts upward from the train; lantern lights flicker subtly; cloaked figures begin to move slowly — walking, turning, adjusting their belongings. Floating dust or magical particles catch the light. The text \"KLING 2.1 STANDARD API — Now on Kie.ai\" softly pulses with a golden glow. The camera pushes forward slightly, then slowly fades to black.",
    "image_url": "Upload successfully",  # Это будет URL после загрузки
    "duration": "5 seconds",  # Форма передает "5 seconds", нужно нормализовать в "5"
    "negative_prompt": "blur, distort, and low quality",
    "cfg_scale": "0,5"  # Указан с запятой (нужно конвертировать в 0.5)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для kling/v2-1-standard")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  duration: '{test_data['duration']}'")
    print(f"  negative_prompt: '{test_data['negative_prompt']}' ({len(test_data['negative_prompt'])} символов)")
    print(f"  cfg_scale: '{test_data['cfg_scale']}'")
    print()
    
    is_valid, errors = validate_kling_v2_1_standard_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        print(f"  - image_url: будет конвертирован в image_input (массив) [OK]")
        
        # Нормализация duration
        duration_normalized = str(test_data['duration']).lower().replace(" seconds", "").replace(" second", "").strip()
        print(f"  - duration: '{test_data['duration']}' -> нормализовано в '{duration_normalized}' [OK]")
        
        print(f"  - negative_prompt: {len(test_data['negative_prompt'])} символов (лимит: 500) [OK]")
        
        # Конвертация cfg_scale
        cfg_scale_str = str(test_data['cfg_scale']).replace(',', '.')
        cfg_scale_val = float(cfg_scale_str)
        print(f"  - cfg_scale: '{test_data['cfg_scale']}' -> конвертировано в {cfg_scale_val} [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image_input (массив с URL изображения) для генерации видео")
        print("  - duration влияет на цену: 5 секунд (25 кредитов), 10 секунд (50 кредитов)")
        print("  - cfg_scale определяет, насколько близко модель следует промпту (0-1, шаг 0.1)")
        print("  - По умолчанию duration='5', cfg_scale=0.5")
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
    
    # image_input - обязательный (конвертируем image_url в массив)
    if 'image_url' in test_data and test_data['image_url']:
        api_data['image_input'] = [test_data['image_url']]
    elif 'image_input' in test_data:
        api_data['image_input'] = test_data['image_input']
    
    # duration - опциональный, но можно указать default
    if test_data.get('duration'):
        duration = str(test_data['duration'])
        # Нормализуем значение (убираем " seconds" если есть)
        if " seconds" in duration.lower() or " second" in duration.lower():
            duration = duration.lower().replace(" seconds", "").replace(" second", "").strip()
        api_data['duration'] = duration
    else:
        api_data['duration'] = "5"  # default
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    
    # cfg_scale - только если указан (как number!)
    if test_data.get('cfg_scale'):
        try:
            cfg_scale_str = str(test_data['cfg_scale']).replace(',', '.')
            cfg_scale_val = float(cfg_scale_str)
            # Округляем до 1 знака после запятой (шаг 0.1)
            api_data['cfg_scale'] = round(cfg_scale_val, 1)
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный cfg_scale
    else:
        api_data['cfg_scale'] = 0.5  # default
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))



