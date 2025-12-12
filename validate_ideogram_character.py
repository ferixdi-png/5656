"""
Валидация входных данных для модели ideogram/character
"""

def validate_ideogram_character_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели ideogram/character
    
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
    
    # 2. Проверка reference_image_input/reference_image_urls (обязательный)
    # Модель ожидает reference_image_input как массив, но пользователь может передать reference_image_urls
    reference_image_input = None
    if 'reference_image_input' in data:
        reference_image_input = data['reference_image_input']
    elif 'reference_image_urls' in data:
        # Конвертируем reference_image_urls в reference_image_input (массив)
        if isinstance(data['reference_image_urls'], list):
            # Берем только первый элемент (поддерживается только 1 изображение)
            reference_image_input = [data['reference_image_urls'][0]] if len(data['reference_image_urls']) > 0 and data['reference_image_urls'][0] else None
        elif data['reference_image_urls']:
            # Если это строка, конвертируем в массив
            reference_image_input = [data['reference_image_urls']]
    
    if not reference_image_input:
        errors.append("[ERROR] Параметр 'reference_image_input' или 'reference_image_urls' обязателен и не может быть пустым")
    else:
        # Проверяем, что это массив
        if not isinstance(reference_image_input, list):
            errors.append("[ERROR] Параметр 'reference_image_input' должен быть массивом (списком)")
        elif len(reference_image_input) == 0:
            errors.append("[ERROR] Параметр 'reference_image_input' не может быть пустым массивом")
        elif len(reference_image_input) > 1:
            errors.append("[WARNING] Параметр 'reference_image_input' должен содержать только 1 изображение. Остальные будут проигнорированы")
        else:
            # Проверяем, что это строка (URL)
            if not isinstance(reference_image_input[0], str) or not reference_image_input[0]:
                errors.append("[ERROR] URL референсного изображения должен быть непустой строкой")
    
    # 3. Проверка rendering_speed (опциональный, enum)
    # Модель ожидает: ["TURBO", "BALANCED", "QUALITY"]
    valid_rendering_speeds = ["TURBO", "BALANCED", "QUALITY"]
    if 'rendering_speed' in data and data['rendering_speed']:
        rendering_speed = str(data['rendering_speed']).upper()
        if rendering_speed not in valid_rendering_speeds:
            errors.append(f"[ERROR] Параметр 'rendering_speed' имеет недопустимое значение: '{data['rendering_speed']}'. Допустимые значения: {', '.join(valid_rendering_speeds)}")
    
    # 4. Проверка style (опциональный, enum)
    # Модель ожидает: ["AUTO", "REALISTIC", "FICTION"]
    valid_styles = ["AUTO", "REALISTIC", "FICTION"]
    if 'style' in data and data['style']:
        style = str(data['style']).upper()
        if style not in valid_styles:
            errors.append(f"[ERROR] Параметр 'style' имеет недопустимое значение: '{data['style']}'. Допустимые значения: {', '.join(valid_styles)}")
    
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
    
    # 7. Проверка image_size (опциональный, enum)
    # Модель ожидает: ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
    valid_image_sizes = ["square", "square_hd", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
    
    if 'image_size' in data and data['image_size']:
        image_size = str(data['image_size']).lower()
        # Нормализуем значение (заменяем пробелы и двоеточия на подчеркивания)
        normalized_size = image_size.replace(" ", "_").replace(":", "_")
        if normalized_size not in valid_image_sizes:
            errors.append(f"[ERROR] Параметр 'image_size' имеет недопустимое значение: '{data['image_size']}'. Допустимые значения: {', '.join(valid_image_sizes)}")
    
    # 8. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 5000)")
    
    # 9. Проверка seed (опциональный, integer) - если указан в форме
    # ПРИМЕЧАНИЕ: В описании модели seed не указан, но форма может его передавать
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Seed может быть любым целым числом (нет ограничений в модели)
        except (ValueError, TypeError):
            errors.append(f"[WARNING] Параметр 'seed' должен быть целым числом, получено: {data['seed']}. Параметр не поддерживается моделью и будет проигнорирован")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Place the woman from the uploaded portrait, wearing a casual white blouse, in a peaceful garden setting. The scene should feature vibrant green plants and colorful flowers, with soft sunlight filtering through the leaves. She should be sitting on a wooden bench, holding a book and smiling gently. The background should be filled with lush greenery, with a serene, tranquil atmosphere. Golden afternoon light should highlight the woman's face and create soft shadows on the ground, adding a peaceful, reflective mood to the scene",
    "reference_image_urls": ["File 1"],  # Массив с референсными изображениями (поддерживается только 1)
    "rendering_speed": "",  # Не указан - будет использован default "BALANCED"
    "style": "",  # Не указан - будет использован default "AUTO"
    "expand_prompt": None,  # Не указан - будет использован default True
    "num_images": "1",  # В модели это string
    "image_size": "square_hd",  # Указан
    "seed": "",  # Не указан - опциональный (и не поддерживается моделью)
    "negative_prompt": ""  # Не указан - опциональный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для ideogram/character")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  reference_image_urls: {test_data['reference_image_urls']}")
    print(f"  rendering_speed: '{test_data['rendering_speed']}' (не указан - будет использован default 'BALANCED')")
    print(f"  style: '{test_data['style']}' (не указан - будет использован default 'AUTO')")
    print(f"  expand_prompt: {test_data['expand_prompt']} (не указан - будет использован default True)")
    print(f"  num_images: '{test_data['num_images']}'")
    print(f"  image_size: '{test_data['image_size']}'")
    print(f"  seed: '{test_data['seed']}' (не указан - опциональный, не поддерживается моделью)")
    print(f"  negative_prompt: '{test_data['negative_prompt']}' (не указан - опциональный)")
    print()
    
    is_valid, errors = validate_ideogram_character_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        print(f"  - reference_image_urls: будет конвертирован в reference_image_input (массив) [OK]")
        if test_data.get('rendering_speed'):
            print(f"  - rendering_speed: '{test_data['rendering_speed']}' - валидное значение [OK]")
        else:
            print(f"  - rendering_speed: не указан, будет использован default 'BALANCED' [OK]")
        if test_data.get('style'):
            print(f"  - style: '{test_data['style']}' - валидное значение [OK]")
        else:
            print(f"  - style: не указан, будет использован default 'AUTO' [OK]")
        print(f"  - expand_prompt: опциональный, не указан - будет использован default True [OK]")
        print(f"  - num_images: '{test_data['num_images']}' - валидное значение [OK]")
        if test_data.get('image_size'):
            print(f"  - image_size: '{test_data['image_size']}' - валидное значение [OK]")
        else:
            print(f"  - image_size: не указан, будет использован default 'square_hd' [OK]")
        if test_data.get('seed'):
            print(f"  - seed: '{test_data['seed']}' - параметр не поддерживается моделью, будет проигнорирован [WARNING]")
        else:
            print(f"  - seed: опциональный, не указан [OK]")
        if test_data.get('negative_prompt'):
            print(f"  - negative_prompt: {len(test_data['negative_prompt'])} символов (лимит: 5000) [OK]")
        else:
            print(f"  - negative_prompt: опциональный, не указан [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется reference_image_input (массив с референсными изображениями, поддерживается только 1)")
        print("  - rendering_speed влияет на цену: TURBO (12 кредитов), BALANCED (18 кредитов), QUALITY (24 кредита)")
        print("  - expand_prompt (MagicPrompt) по умолчанию включен (True)")
        print("  - image_size определяет разрешение генерируемого изображения (default: square_hd)")
        print("  - Референсные изображения должны быть в формате JPEG, PNG или WebP (макс. 10MB)")
        print("  - Параметр 'seed' не поддерживается моделью и будет проигнорирован, если указан")
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
    
    # reference_image_input - обязательный (конвертируем reference_image_urls в массив)
    if 'reference_image_urls' in test_data and test_data['reference_image_urls']:
        if isinstance(test_data['reference_image_urls'], list):
            # Берем только первый элемент (поддерживается только 1 изображение)
            if len(test_data['reference_image_urls']) > 0 and test_data['reference_image_urls'][0]:
                api_data['reference_image_input'] = [test_data['reference_image_urls'][0]]
        elif test_data['reference_image_urls']:
            api_data['reference_image_input'] = [test_data['reference_image_urls']]
    elif 'reference_image_input' in test_data:
        api_data['reference_image_input'] = test_data['reference_image_input']
    
    # rendering_speed - опциональный, но можно указать default
    if test_data.get('rendering_speed'):
        rendering_speed = str(test_data['rendering_speed']).upper()
        api_data['rendering_speed'] = rendering_speed
    else:
        api_data['rendering_speed'] = "BALANCED"  # default
    
    # style - опциональный, но можно указать default
    if test_data.get('style'):
        style = str(test_data['style']).upper()
        api_data['style'] = style
    else:
        api_data['style'] = "AUTO"  # default
    
    # expand_prompt - только если указан
    if test_data.get('expand_prompt') is not None:
        api_data['expand_prompt'] = bool(test_data['expand_prompt'])
    # Иначе не включаем (будет использован default True)
    
    # num_images - опциональный, но можно указать default
    if test_data.get('num_images'):
        api_data['num_images'] = test_data['num_images']
    else:
        api_data['num_images'] = "1"  # default
    
    # image_size - опциональный, но можно указать default
    if test_data.get('image_size'):
        image_size = str(test_data['image_size']).lower()
        # Нормализуем значение
        normalized_size = image_size.replace(" ", "_").replace(":", "_")
        api_data['image_size'] = normalized_size
    else:
        api_data['image_size'] = "square_hd"  # default
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    
    # seed - НЕ включаем, так как модель его не поддерживает
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

