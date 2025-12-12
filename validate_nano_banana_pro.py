"""
Валидация входных данных для модели nano-banana-pro
"""

def validate_nano_banana_pro_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели nano-banana-pro
    
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
        if len(prompt) > 10000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 10000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка image_input (опциональный, массив, до 8 изображений)
    if 'image_input' in data and data['image_input']:
        image_input = data['image_input']
        # Конвертируем строку в массив
        if isinstance(image_input, str):
            image_input = [image_input]
        elif not isinstance(image_input, list):
            errors.append(f"[ERROR] Параметр 'image_input' должен быть массивом URL или строкой URL, получено: {type(image_input).__name__}")
        else:
            if len(image_input) > 8:
                errors.append(f"[ERROR] Параметр 'image_input' может содержать максимум 8 изображений, получено: {len(image_input)}")
            else:
                # Проверяем каждый URL в массиве
                for idx, url in enumerate(image_input):
                    url_str = str(url).strip()
                    if not url_str:
                        errors.append(f"[ERROR] URL изображения #{idx + 1} в массиве 'image_input' не может быть пустым")
    
    # 3. Проверка aspect_ratio (опциональный, enum)
    # Модель ожидает: ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"]
    # Форма может передавать: "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"
    valid_aspect_ratios = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9", "auto"]
    
    if 'aspect_ratio' in data and data['aspect_ratio']:
        aspect_ratio = str(data['aspect_ratio']).strip()
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 4. Проверка resolution (опциональный, enum)
    # Модель ожидает: ["1K", "2K", "4K"]
    # Форма может передавать: "1K", "2K", "4K"
    valid_resolutions = ["1K", "2K", "4K"]
    if 'resolution' in data and data['resolution']:
        resolution = str(data['resolution']).strip().upper()
        if resolution not in valid_resolutions:
            errors.append(f"[ERROR] Параметр 'resolution' имеет недопустимое значение: '{data['resolution']}'. Допустимые значения: {', '.join(valid_resolutions)}")
    
    # 5. Проверка output_format (опциональный, enum)
    # Модель ожидает: ["png", "jpg"] (в нижнем регистре)
    # Форма может передавать: "PNG", "JPG"
    valid_output_formats = ["png", "jpg"]
    if 'output_format' in data and data['output_format']:
        output_format = str(data['output_format']).strip().lower()
        # Маппинг JPG -> jpg
        if output_format == "jpeg":
            output_format = "jpg"
        if output_format not in valid_output_formats:
            errors.append(f"[ERROR] Параметр 'output_format' имеет недопустимое значение: '{data['output_format']}'. Допустимые значения: {', '.join(valid_output_formats)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Comic poster: cool banana hero in shades leaps from sci-fi pad. Six panels: 1) 4K mountain landscape, 2) banana holds page of long multilingual text with auto translation, 3) Gemini 3 hologram for search/knowledge/reasoning, 4) camera UI sliders for angle focus color, 5) frame trio 1:1-9:16, 6) consistent banana poses. Footer shows Google icons. Tagline: Nano Banana Pro now on Kie AI.",
    "image_input": None,  # Не указан - опциональный
    "aspect_ratio": "1:1",  # Указан
    "resolution": "1K",  # Указан
    "output_format": "PNG"  # Указан
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для nano-banana-pro")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_input: {test_data['image_input']} (не указан - опциональный)")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}'")
    print(f"  resolution: '{test_data['resolution']}'")
    print(f"  output_format: '{test_data['output_format']}'")
    print()
    
    is_valid, errors = validate_nano_banana_pro_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 10000) [OK]")
        if test_data.get('image_input'):
            if isinstance(test_data['image_input'], list):
                print(f"  - image_input: {len(test_data['image_input'])} изображение(й) (максимум 8) [OK]")
            else:
                print(f"  - image_input: будет конвертирован в массив [OK]")
        else:
            print(f"  - image_input: опциональный, не указан [OK]")
        if test_data.get('aspect_ratio'):
            print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        else:
            print(f"  - aspect_ratio: опциональный, не указан - будет использован default '1:1' [OK]")
        if test_data.get('resolution'):
            resolution_normalized = str(test_data['resolution']).strip().upper()
            print(f"  - resolution: '{test_data['resolution']}' -> нормализовано в '{resolution_normalized}' [OK]")
        else:
            print(f"  - resolution: опциональный, не указан - будет использован default '1K' [OK]")
        if test_data.get('output_format'):
            output_format_normalized = str(test_data['output_format']).strip().lower()
            if output_format_normalized == "jpeg":
                output_format_normalized = "jpg"
            print(f"  - output_format: '{test_data['output_format']}' -> нормализовано в '{output_format_normalized}' [OK]")
        else:
            print(f"  - output_format: опциональный, не указан - будет использован default 'png' [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание изображения, макс. 10000 символов)")
        print("  - image_input - опциональный, входные изображения для трансформации или использования как референс (до 8 изображений)")
        print("  - aspect_ratio определяет соотношение сторон изображения (default: 1:1)")
        print("  - resolution влияет на цену: 1K/2K (18 кредитов), 4K (24 кредита), default: 1K")
        print("  - output_format определяет формат выходного изображения (png/jpg, default: png)")
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
    
    # image_input - опциональный, только если указан
    if test_data.get('image_input'):
        image_input = test_data['image_input']
        if isinstance(image_input, str):
            api_data['image_input'] = [image_input]
        elif isinstance(image_input, list):
            # Валидируем и очищаем каждый URL
            validated_urls = [str(url).strip() for url in image_input if str(url).strip()]
            api_data['image_input'] = validated_urls
        else:
            api_data['image_input'] = [str(image_input).strip()]
    # Иначе не включаем (опциональный параметр)
    
    # aspect_ratio - опциональный, но можно указать default
    if test_data.get('aspect_ratio'):
        api_data['aspect_ratio'] = str(test_data['aspect_ratio']).strip()
    else:
        api_data['aspect_ratio'] = "1:1"  # default
    
    # resolution - опциональный, но можно указать default
    if test_data.get('resolution'):
        resolution = str(test_data['resolution']).strip().upper()
        api_data['resolution'] = resolution
    else:
        api_data['resolution'] = "1K"  # default
    
    # output_format - опциональный, но можно указать default
    if test_data.get('output_format'):
        output_format = str(test_data['output_format']).strip().lower()
        # Маппинг JPG -> jpg, JPEG -> jpg
        if output_format == "jpeg":
            output_format = "jpg"
        api_data['output_format'] = output_format
    else:
        api_data['output_format'] = "png"  # default
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

