"""
Валидация входных данных для модели google/nano-banana-edit
"""

def validate_google_nano_banana_edit_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели google/nano-banana-edit
    
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
        prompt = str(data['prompt']).strip()
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка image_urls (обязательный, массив URL, максимум 10 изображений)
    # Модель ожидает image_urls как массив, но пользователь может передать image_input или строку
    image_urls = None
    if 'image_urls' in data:
        image_urls = data['image_urls']
    elif 'image_input' in data:
        # Конвертируем image_input в image_urls
        image_urls = data['image_input']
    
    if not image_urls:
        errors.append("[ERROR] Параметр 'image_urls' или 'image_input' обязателен и не может быть пустым")
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
            elif len(image_urls) > 10:
                errors.append(f"[ERROR] Параметр 'image_urls' может содержать максимум 10 изображений, получено: {len(image_urls)}")
            else:
                # Проверяем каждый URL в массиве
                for idx, url in enumerate(image_urls):
                    url_str = str(url).strip()
                    if not url_str:
                        errors.append(f"[ERROR] URL изображения #{idx + 1} в массиве 'image_urls' не может быть пустым")
                    # Базовая проверка формата URL (должен начинаться с http:// или https://)
                    elif not (url_str.startswith('http://') or url_str.startswith('https://')):
                        errors.append(f"[WARNING] URL изображения #{idx + 1} может иметь неверный формат: '{url_str[:50]}...' (должен начинаться с http:// или https://)")
    
    # 3. Проверка output_format (опциональный, enum)
    # Модель ожидает: ["PNG", "JPEG"] (в верхнем регистре)
    # Форма может передавать: "PNG", "JPEG"
    valid_output_formats = ["PNG", "JPEG"]
    if 'output_format' in data and data['output_format']:
        output_format = str(data['output_format']).strip().upper()
        if output_format not in valid_output_formats:
            errors.append(f"[ERROR] Параметр 'output_format' имеет недопустимое значение: '{data['output_format']}'. Допустимые значения: {', '.join(valid_output_formats)}")
    
    # 4. Проверка image_size (опциональный, enum)
    # Модель ожидает: ["1:1", "9:16", "16:9", "3:4", "4:3", "3:2", "2:3", "5:4", "4:5", "21:9", "auto"]
    # Форма может передавать: "1:1", "9:16", "16:9", "3:4", "4:3", "3:2", "2:3", "5:4", "4:5", "21:9", "auto"
    valid_image_sizes = ["1:1", "9:16", "16:9", "3:4", "4:3", "3:2", "2:3", "5:4", "4:5", "21:9", "auto"]
    
    if 'image_size' in data and data['image_size']:
        image_size = str(data['image_size']).strip().lower()
        if image_size not in valid_image_sizes:
            errors.append(f"[ERROR] Параметр 'image_size' имеет недопустимое значение: '{data['image_size']}'. Допустимые значения: {', '.join(valid_image_sizes)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "turn this photo into a character figure. Behind it, place a box with the character's image printed on it, and a computer showing the Blender modeling process on its screen. In front of the box, add a round plastic base with the character figure standing on it. set the scene indoors if possible",
    "image_urls": ["File 1"],  # Массив с URL изображений (до 10)
    "output_format": "PNG",  # Указан
    "image_size": "1:1"  # Указан
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для google/nano-banana-edit")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_urls: {test_data['image_urls']} ({len(test_data['image_urls'])} изображение(й))")
    print(f"  output_format: '{test_data['output_format']}'")
    print(f"  image_size: '{test_data['image_size']}'")
    print()
    
    is_valid, errors = validate_google_nano_banana_edit_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов [OK]")
        if isinstance(test_data.get('image_urls'), list):
            print(f"  - image_urls: {len(test_data['image_urls'])} изображение(й) (максимум 10) [OK]")
        else:
            print(f"  - image_urls: будет конвертирован в массив [OK]")
        if test_data.get('output_format'):
            output_format_normalized = str(test_data['output_format']).strip().upper()
            print(f"  - output_format: '{test_data['output_format']}' -> нормализовано в '{output_format_normalized}' [OK]")
        else:
            print(f"  - output_format: опциональный, не указан [OK]")
        if test_data.get('image_size'):
            image_size_normalized = str(test_data['image_size']).strip().lower()
            print(f"  - image_size: '{test_data['image_size']}' -> нормализовано в '{image_size_normalized}' [OK]")
        else:
            print(f"  - image_size: опциональный, не указан [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание для редактирования изображения)")
        print("  - Требуется image_urls (массив URL изображений для редактирования, максимум 10 изображений)")
        print("  - output_format определяет формат выходного изображения (PNG/JPEG, в верхнем регистре)")
        print("  - image_size определяет соотношение сторон изображения (1:1, 9:16, 16:9, 3:4, 4:3, 3:2, 2:3, 5:4, 4:5, 21:9, auto)")
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
    api_data['prompt'] = str(test_data['prompt']).strip()
    
    # image_urls - обязательный (конвертируем в массив, если нужно)
    if 'image_urls' in test_data and test_data['image_urls']:
        image_urls = test_data['image_urls']
        if isinstance(image_urls, str):
            api_data['image_urls'] = [image_urls]
        elif isinstance(image_urls, list):
            # Валидируем и очищаем каждый URL
            validated_urls = [str(url).strip() for url in image_urls if str(url).strip()]
            api_data['image_urls'] = validated_urls
        else:
            api_data['image_urls'] = [str(image_urls).strip()]
    elif 'image_input' in test_data and test_data['image_input']:
        # Конвертируем image_input в image_urls
        image_input = test_data['image_input']
        if isinstance(image_input, str):
            api_data['image_urls'] = [image_input]
        elif isinstance(image_input, list):
            validated_urls = [str(url).strip() for url in image_input if str(url).strip()]
            api_data['image_urls'] = validated_urls
        else:
            api_data['image_urls'] = [str(image_input).strip()]
    
    # output_format - опциональный, но можно указать default
    if test_data.get('output_format'):
        output_format = str(test_data['output_format']).strip().upper()
        api_data['output_format'] = output_format
    # Иначе не включаем (опциональный параметр)
    
    # image_size - опциональный, но можно указать default
    if test_data.get('image_size'):
        image_size = str(test_data['image_size']).strip().lower()
        api_data['image_size'] = image_size
    # Иначе не включаем (опциональный параметр)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))



