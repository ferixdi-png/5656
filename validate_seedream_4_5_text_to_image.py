"""
Валидация входных данных для модели seedream/4.5-text-to-image
"""

def validate_seedream_4_5_text_to_image_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели seedream/4.5-text-to-image
    
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
        if len(prompt) > 3000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 3000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка aspect_ratio (обязательный, enum)
    # Модель ожидает: ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
    # Форма может передавать: "1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"
    valid_aspect_ratios = ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
    
    if 'aspect_ratio' not in data or not data['aspect_ratio']:
        errors.append("[ERROR] Параметр 'aspect_ratio' обязателен и не может быть пустым")
    else:
        aspect_ratio = str(data['aspect_ratio']).strip()
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 3. Проверка quality (обязательный, enum)
    # Модель ожидает: ["basic", "high"] (в нижнем регистре)
    # Форма может передавать: "Basic", "High"
    valid_qualities = ["basic", "high"]
    
    if 'quality' not in data or not data['quality']:
        errors.append("[ERROR] Параметр 'quality' обязателен и не может быть пустым")
    else:
        quality = str(data['quality']).strip().lower()
        if quality not in valid_qualities:
            errors.append(f"[ERROR] Параметр 'quality' имеет недопустимое значение: '{data['quality']}'. Допустимые значения: {', '.join(valid_qualities)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "A full-process cafe design tool for entrepreneurs and designers. It covers core needs including store layout, functional zoning, decoration style, equipment selection, and customer group adaptation, supporting integrated planning of \"commercial attributes + aesthetic design.\" Suitable as a promotional image for a cafe design SaaS product, with a 16:9 aspect ratio.",
    "aspect_ratio": "1:1",  # Обязательный
    "quality": "Basic"  # Обязательный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для seedream/4.5-text-to-image")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}'")
    print(f"  quality: '{test_data['quality']}'")
    print()
    
    is_valid, errors = validate_seedream_4_5_text_to_image_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 3000) [OK]")
        print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        quality_normalized = str(test_data['quality']).strip().lower()
        print(f"  - quality: '{test_data['quality']}' -> нормализовано в '{quality_normalized}' [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание изображения, макс. 3000 символов)")
        print("  - Требуется aspect_ratio (соотношение сторон изображения)")
        print("  - Требуется quality (качество изображения: basic = 2K, high = 4K)")
        print()
        print("[PRICING] Ценообразование:")
        quality_normalized = str(test_data.get('quality', 'basic')).strip().lower()
        print(f"  - Текущая цена: 6.5 кредитов за изображение (фиксированная)")
        print(f"  - Параметры quality='{quality_normalized}' и aspect_ratio='{test_data.get('aspect_ratio', '1:1')}' не влияют на цену")
        print("  - ВНИМАНИЕ: Если API изменит ценообразование в зависимости от quality (basic=2K, high=4K),")
        print("    необходимо обновить функцию calculate_price_rub() в bot_kie.py")
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
    
    # quality - обязательный (нормализуем в нижний регистр)
    quality = str(test_data['quality']).strip().lower()
    api_data['quality'] = quality
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




