"""
Валидация входных данных для модели z-image
"""

def validate_z_image_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели z-image
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors)
    """
    errors = []
    
    # 1. Проверка prompt (обязательный, макс. 1000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) > 1000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 1000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка aspect_ratio (обязательный, enum)
    # Модель ожидает: ["1:1", "4:3", "3:4", "16:9", "9:16"]
    # Форма может передавать: "1:1", "4:3", "3:4", "16:9", "9:16"
    valid_aspect_ratios = ["1:1", "4:3", "3:4", "16:9", "9:16"]
    
    if 'aspect_ratio' not in data or not data['aspect_ratio']:
        errors.append("[ERROR] Параметр 'aspect_ratio' обязателен и не может быть пустым")
    else:
        aspect_ratio = str(data['aspect_ratio']).strip()
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A hyper-realistic, close-up portrait of a 30-year-old mixed-heritage French-Italian woman drinking coffee from a cup that says \"Z-Image × Kie AI.\" Natural light. Shot on a Leica M6 with a Kodak Portra 400 film-grain aesthetic.",
    "aspect_ratio": "1:1"  # Обязательный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для z-image")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}'")
    print()
    
    is_valid, errors = validate_z_image_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 1000) [OK]")
        print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание изображения, макс. 1000 символов)")
        print("  - Требуется aspect_ratio (соотношение сторон изображения)")
        print()
        print("[PRICING] Ценообразование:")
        print(f"  - Цена: 0.8 кредитов за изображение (фиксированная)")
        print(f"  - Параметр aspect_ratio='{test_data.get('aspect_ratio', '1:1')}' не влияет на цену")
        print("  - Модель доступна бесплатно: 5 генераций в день для каждого пользователя")
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
    
    # aspect_ratio - обязательный
    api_data['aspect_ratio'] = str(test_data['aspect_ratio']).strip()
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))



