"""
Валидация входных данных для модели seedream/4.5-edit
"""

def validate_seedream_4_5_edit_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели seedream/4.5-edit
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 3000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) > 3000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 3000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка image_urls (обязательный, массив URL)
    # Модель ожидает image_urls как массив, но пользователь может передать image_input или строку
    image_urls = None
    if 'image_urls' in data:
        image_urls = data['image_urls']
    elif 'image_input' in data:
        # Конвертируем image_input в image_urls
        image_urls = data['image_input']
    elif 'image_url' in data:
        # Конвертируем image_url в image_urls
        image_urls = data['image_url']
    
    if not image_urls:
        errors.append("[ERROR] Параметр 'image_urls' (или 'image_input', 'image_url') обязателен и не может быть пустым")
    else:
        # Конвертируем строку в массив
        if isinstance(image_urls, str):
            image_urls = [image_urls]
        elif not isinstance(image_urls, list):
            errors.append(f"[ERROR] Параметр 'image_urls' должен быть массивом URL или строкой URL, получено: {type(image_urls).__name__}")
            image_urls = None
        
        if image_urls:
            if len(image_urls) == 0:
                errors.append("[ERROR] Параметр 'image_urls' не может быть пустым массивом")
            else:
                # Проверяем каждый URL в массиве
                for idx, url in enumerate(image_urls):
                    url_str = str(url).strip()
                    if not url_str:
                        errors.append(f"[ERROR] URL изображения #{idx + 1} в массиве 'image_urls' не может быть пустым")
                    # Базовая проверка формата URL (должен начинаться с http:// или https://)
                    elif not (url_str.startswith('http://') or url_str.startswith('https://')):
                        # Предупреждение для placeholder значений (например, "File 1")
                        if url_str.lower().startswith('file') or 'upload' in url_str.lower() or 'click' in url_str.lower():
                            warnings.append(f"[WARNING] URL изображения #{idx + 1} может иметь неверный формат: '{url_str[:50]}...' (должен начинаться с http:// или https://). Это может быть placeholder, который будет заменен на реальный URL.")
                        else:
                            warnings.append(f"[WARNING] URL изображения #{idx + 1} может иметь неверный формат: '{url_str[:50]}...' (должен начинаться с http:// или https://)")
    
    # 3. Проверка aspect_ratio (обязательный, enum)
    # Модель ожидает: ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
    # Форма может передавать: "1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"
    valid_aspect_ratios = ["1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2", "21:9"]
    
    if 'aspect_ratio' not in data or not data['aspect_ratio']:
        errors.append("[ERROR] Параметр 'aspect_ratio' обязателен и не может быть пустым")
    else:
        aspect_ratio = str(data['aspect_ratio']).strip()
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 4. Проверка quality (обязательный, enum)
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
    return is_valid, errors, warnings


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Keep the model's pose and the flowing shape of the liquid dress unchanged. Change the clothing material from silver metal to completely transparent clear water (or glass). Through the liquid water, the model's skin details are visible. Lighting changes from reflection to refraction.",
    "image_urls": "File 1",  # Это будет заменено на реальный URL после загрузки
    "aspect_ratio": "1:1",  # Обязательный
    "quality": "Basic"  # Обязательный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для seedream/4.5-edit")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_urls: '{test_data['image_urls']}'")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}'")
    print(f"  quality: '{test_data['quality']}'")
    print()
    
    is_valid, errors, warnings = validate_seedream_4_5_edit_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 3000) [OK]")
        print(f"  - image_urls: '{test_data['image_urls']}' - будет заменено на реальный URL [OK]")
        print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        quality_normalized = str(test_data['quality']).strip().lower()
        print(f"  - quality: '{test_data['quality']}' -> нормализовано в '{quality_normalized}' [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание изменений, макс. 3000 символов)")
        print("  - Требуется image_urls (массив URL изображений для редактирования)")
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
        if warnings:
            print()
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
    
    print()
    print("=" * 60)
    
    # Дополнительная проверка: формат для API
    print()
    print("[API] Формат данных для отправки в API:")
    api_data = {}
    
    # prompt - обязательный
    api_data['prompt'] = test_data['prompt']
    
    # image_urls - обязательный (конвертируем в массив, если строка)
    image_urls = test_data['image_urls']
    if isinstance(image_urls, str):
        image_urls = [image_urls]
    api_data['image_urls'] = image_urls
    
    # aspect_ratio - обязательный
    api_data['aspect_ratio'] = str(test_data['aspect_ratio']).strip()
    
    # quality - обязательный (нормализуем в нижний регистр)
    quality = str(test_data['quality']).strip().lower()
    api_data['quality'] = quality
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))



