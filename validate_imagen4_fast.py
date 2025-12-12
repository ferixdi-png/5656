"""
Валидация входных данных для модели google/imagen4-fast
"""

def validate_imagen4_fast_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели google/imagen4-fast
    
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
    
    # 2. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 5000)")
    
    # 3. Проверка aspect_ratio (опциональный, enum)
    valid_aspect_ratios = ["1:1", "16:9", "9:16", "3:4", "4:3"]
    if 'aspect_ratio' in data and data['aspect_ratio']:
        aspect_ratio = str(data['aspect_ratio'])
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{aspect_ratio}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 4. Проверка num_images (опциональный, enum как string)
    valid_num_images = ["1", "2", "3", "4"]
    if 'num_images' in data and data['num_images']:
        num_images = str(data['num_images'])  # Модель ожидает string
        if num_images not in valid_num_images:
            errors.append(f"[ERROR] Параметр 'num_images' имеет недопустимое значение: '{num_images}'. Допустимые значения: {', '.join(valid_num_images)}")
    
    # 5. Проверка seed (опциональный, integer)
    if 'seed' in data and data['seed']:
        try:
            seed = int(data['seed'])
            # Проверка на разумные значения (обычно seed это положительное число)
            if seed < 0:
                errors.append(f"[ERROR] Параметр 'seed' должен быть неотрицательным числом, получено: {seed}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'seed' должен быть целым числом, получено: {data['seed']}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Create a cinematic, photorealistic medium shot capturing the nostalgic warmth of a late 90s indie film. The focus is a young woman with brightly dyed pink hair (slightly faded) and freckled skin, looking directly and intently into the camera lens with a hopeful yet slightly uncertain smile. She wears an oversized, vintage band t-shirt (slightly worn, with the faintly cracked white text \"KIE AI\" across the chest) layered over a long-sleeved striped top, along with simple silver stud earrings. The lighting is soft, golden hour sunlight streaming through a slightly dusty window, creating lens flare and illuminating dust motes in the air. The background shows a blurred, cluttered bedroom with posters on the wall and fairy lights, rendered with a shallow depth of field. Natural film grain, a warm, slightly muted color palette, and sharp focus on her expressive eyes enhance the intimate, authentic feel.",
    "negative_prompt": "",  # Пустое - это OK, параметр опциональный
    "aspect_ratio": "1:1",
    "num_images": "1",  # В модели это string
    "seed": ""  # Пустое - это OK, параметр опциональный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для google/imagen4-fast")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: {test_data['prompt'][:100]}... ({len(test_data['prompt'])} символов)")
    print(f"  negative_prompt: '{test_data['negative_prompt']}' (пустое - OK)")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}'")
    print(f"  num_images: '{test_data['num_images']}'")
    print(f"  seed: '{test_data['seed']}' (пустое - OK)")
    print()
    
    is_valid, errors = validate_imagen4_fast_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        print(f"  - negative_prompt: опциональный, пустое значение допустимо [OK]")
        print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        print(f"  - num_images: '{test_data['num_images']}' - валидное значение [OK]")
        print(f"  - seed: опциональный, пустое значение допустимо [OK]")
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
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    
    # aspect_ratio - опциональный, но можно указать default
    if test_data.get('aspect_ratio'):
        api_data['aspect_ratio'] = test_data['aspect_ratio']
    else:
        api_data['aspect_ratio'] = "1:1"  # default
    
    # num_images - опциональный, но можно указать default
    if test_data.get('num_images'):
        api_data['num_images'] = test_data['num_images']
    else:
        api_data['num_images'] = "1"  # default
    
    # seed - только если указан
    if test_data.get('seed'):
        try:
            api_data['seed'] = int(test_data['seed'])
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный seed
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




