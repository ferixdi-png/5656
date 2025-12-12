"""
Валидация входных данных для модели ideogram/v3-edit
"""

def validate_ideogram_v3_edit_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели ideogram/v3-edit
    
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
    
    # 3. Проверка mask_input/mask_url (обязательный)
    # Модель ожидает mask_input как массив, но пользователь может передать mask_url
    mask_input = None
    if 'mask_input' in data:
        mask_input = data['mask_input']
    elif 'mask_url' in data:
        # Конвертируем mask_url в mask_input (массив)
        mask_input = [data['mask_url']] if data['mask_url'] else None
    
    if not mask_input:
        errors.append("[ERROR] Параметр 'mask_input' или 'mask_url' обязателен и не может быть пустым")
    else:
        # Проверяем, что это массив
        if not isinstance(mask_input, list):
            errors.append("[ERROR] Параметр 'mask_input' должен быть массивом (списком)")
        elif len(mask_input) == 0:
            errors.append("[ERROR] Параметр 'mask_input' не может быть пустым массивом")
        elif len(mask_input) > 1:
            errors.append("[ERROR] Параметр 'mask_input' должен содержать только 1 маску (максимум 1 элемент)")
        else:
            # Проверяем, что это строка (URL)
            if not isinstance(mask_input[0], str) or not mask_input[0]:
                errors.append("[ERROR] URL маски должен быть непустой строкой")
    
    # 4. Проверка rendering_speed (опциональный, enum)
    # Модель ожидает: ["TURBO", "BALANCED", "QUALITY"]
    # Форма может передавать: "Turbo", "Balanced", "Quality"
    valid_rendering_speeds = ["TURBO", "BALANCED", "QUALITY"]
    if 'rendering_speed' in data and data['rendering_speed']:
        rendering_speed = str(data['rendering_speed']).upper()
        if rendering_speed not in valid_rendering_speeds:
            errors.append(f"[ERROR] Параметр 'rendering_speed' имеет недопустимое значение: '{data['rendering_speed']}'. Допустимые значения: {', '.join(valid_rendering_speeds)}")
    
    # 5. Проверка expand_prompt (опциональный, boolean)
    if 'expand_prompt' in data and data['expand_prompt'] is not None:
        expand_prompt = data['expand_prompt']
        if not isinstance(expand_prompt, bool):
            # Попытка конвертации строки в boolean
            if isinstance(expand_prompt, str):
                if expand_prompt.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    errors.append(f"[ERROR] Параметр 'expand_prompt' должен быть boolean (true/false), получено: {expand_prompt}")
            else:
                errors.append(f"[ERROR] Параметр 'expand_prompt' должен быть boolean, получено: {type(expand_prompt).__name__}")
    
    # 6. Проверка num_images (опциональный, enum как string)
    valid_num_images = ["1", "2", "3", "4"]
    if 'num_images' in data and data['num_images']:
        num_images = str(data['num_images'])  # Модель ожидает string
        if num_images not in valid_num_images:
            errors.append(f"[ERROR] Параметр 'num_images' имеет недопустимое значение: '{num_images}'. Допустимые значения: {', '.join(valid_num_images)}")
    
    # 7. Проверка seed (опциональный, integer)
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Seed может быть любым целым числом (нет ограничений в модели)
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть целым числом, получено: {data['seed']}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A dog wearing a cowboy hat",
    "image_url": "Upload successfully",  # Это будет URL после загрузки
    "mask_url": "Upload successfully",  # Это будет URL после загрузки
    "rendering_speed": "",  # Не указан - будет использован default "BALANCED"
    "expand_prompt": None,  # Не указан - будет использован default True
    "num_images": "1",  # В модели это string
    "seed": ""  # Не указан - опциональный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для ideogram/v3-edit")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt']}' ({len(test_data['prompt'])} символов)")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  mask_url: '{test_data['mask_url']}'")
    print(f"  rendering_speed: '{test_data['rendering_speed']}' (не указан - будет использован default 'BALANCED')")
    print(f"  expand_prompt: {test_data['expand_prompt']} (не указан - будет использован default True)")
    print(f"  num_images: '{test_data['num_images']}'")
    print(f"  seed: '{test_data['seed']}' (не указан - опциональный)")
    print()
    
    is_valid, errors = validate_ideogram_v3_edit_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        print(f"  - image_url: будет конвертирован в image_input (массив) [OK]")
        print(f"  - mask_url: будет конвертирован в mask_input (массив) [OK]")
        if test_data.get('rendering_speed'):
            print(f"  - rendering_speed: '{test_data['rendering_speed']}' - валидное значение [OK]")
        else:
            print(f"  - rendering_speed: не указан, будет использован default 'BALANCED' [OK]")
        print(f"  - expand_prompt: опциональный, не указан - будет использован default True [OK]")
        print(f"  - num_images: '{test_data['num_images']}' - валидное значение [OK]")
        if test_data.get('seed'):
            try:
                seed_val = int(test_data['seed'])
                print(f"  - seed: {seed_val} - валидное значение [OK]")
            except:
                print(f"  - seed: '{test_data['seed']}' - будет конвертирован в число [OK]")
        else:
            print(f"  - seed: опциональный, не указан [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image_input (массив с URL изображения) и mask_input (массив с URL маски)")
        print("  - rendering_speed влияет на цену: TURBO (3.5 кредита), BALANCED (7 кредитов), QUALITY (10 кредитов)")
        print("  - expand_prompt (MagicPrompt) по умолчанию включен (True)")
        print("  - Маска должна соответствовать размерам входного изображения")
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
    
    # mask_input - обязательный (конвертируем mask_url в массив)
    if 'mask_url' in test_data and test_data['mask_url']:
        api_data['mask_input'] = [test_data['mask_url']]
    elif 'mask_input' in test_data:
        api_data['mask_input'] = test_data['mask_input']
    
    # rendering_speed - опциональный, но можно указать default
    if test_data.get('rendering_speed'):
        rendering_speed = str(test_data['rendering_speed']).upper()
        api_data['rendering_speed'] = rendering_speed
    else:
        api_data['rendering_speed'] = "BALANCED"  # default
    
    # expand_prompt - только если указан
    if test_data.get('expand_prompt') is not None:
        api_data['expand_prompt'] = bool(test_data['expand_prompt'])
    # Иначе не включаем (будет использован default True)
    
    # num_images - опциональный, но можно указать default
    if test_data.get('num_images'):
        api_data['num_images'] = test_data['num_images']
    else:
        api_data['num_images'] = "1"  # default
    
    # seed - только если указан (как integer!)
    if test_data.get('seed'):
        try:
            api_data['seed'] = int(test_data['seed'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный seed
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

