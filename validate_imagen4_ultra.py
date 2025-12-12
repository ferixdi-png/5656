"""
Валидация входных данных для модели google/imagen4-ultra
"""

def validate_imagen4_ultra_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели google/imagen4-ultra
    
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
    
    # 4. Проверка seed (опциональный, string, макс. 500 символов)
    # ВАЖНО: В отличие от imagen4-fast, здесь seed это string, а не integer!
    if 'seed' in data and data['seed']:
        seed = str(data['seed'])
        if len(seed) > 500:
            errors.append(f"[ERROR] Параметр 'seed' слишком длинный: {len(seed)} символов (максимум 500)")
    
    # 5. Проверка на недопустимые параметры
    # ВАЖНО: google/imagen4-ultra НЕ поддерживает параметр num_images (в отличие от imagen4-fast)
    if 'num_images' in data:
        errors.append("[WARNING] Параметр 'num_images' не поддерживается моделью google/imagen4-ultra. Этот параметр доступен только для google/imagen4-fast")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A lively comic scene where two colleagues are in an office. The first person says, 'Have you heard about Google Imagen 4 Ultra?' The second person responds with excitement, 'It's the best text-to-image tool out there!' The first person asks again, 'Do you know where to get the API?' The second person smiles and says, 'Kie.ai has it!' In the final panel, the two look at a screen showing Kie.ai's interface with an API option, with bright and colorful comic-style illustrations.",
    "negative_prompt": "",  # Пустое - это OK, параметр опциональный
    "aspect_ratio": "",  # Не указан - будет использован default "1:1"
    "seed": ""  # Пустое - это OK, параметр опциональный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для google/imagen4-ultra")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: {test_data['prompt'][:100]}... ({len(test_data['prompt'])} символов)")
    print(f"  negative_prompt: '{test_data['negative_prompt']}' (пустое - OK)")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}' (не указан - будет использован default '1:1')")
    print(f"  seed: '{test_data['seed']}' (пустое - OK)")
    print()
    
    is_valid, errors = validate_imagen4_ultra_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        print(f"  - negative_prompt: опциональный, пустое значение допустимо [OK]")
        if test_data.get('aspect_ratio'):
            print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        else:
            print(f"  - aspect_ratio: не указан, будет использован default '1:1' [OK]")
        print(f"  - seed: опциональный, пустое значение допустимо [OK]")
        print()
        print("[NOTE] Отличие от google/imagen4-fast:")
        print("  - google/imagen4-ultra НЕ поддерживает параметр 'num_images'")
        print("  - В google/imagen4-ultra 'seed' это string (макс. 500 символов)")
        print("  - В google/imagen4-fast 'seed' это integer")
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
    
    # seed - только если указан (как string!)
    if test_data.get('seed'):
        api_data['seed'] = str(test_data['seed'])  # Важно: string, не integer
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

