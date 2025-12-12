"""
Валидация входных данных для модели kling/v1-avatar-standard
"""

def validate_kling_v1_avatar_standard_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели kling/v1-avatar-standard
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка image_url или image_input (обязательный, один URL)
    # Форма может передавать image_url, но API ожидает image_input (массив) или image_url
    image_url = None
    if 'image_url' in data and data['image_url']:
        image_url = str(data['image_url']).strip()
        # Проверяем на placeholder
        if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
            warnings.append(f"[WARNING] Параметр 'image_url' содержит placeholder: '{image_url}'. Убедитесь, что это валидный URL изображения")
    elif 'image_input' in data and data['image_input']:
        # Если передан image_input (массив или строка)
        image_input = data['image_input']
        if isinstance(image_input, list):
            if len(image_input) == 0:
                errors.append("[ERROR] Параметр 'image_input' не может быть пустым массивом")
            elif len(image_input) > 1:
                errors.append(f"[ERROR] Параметр 'image_input' должен содержать только 1 URL, получено: {len(image_input)}")
            else:
                image_url = str(image_input[0]).strip()
                if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
                    warnings.append(f"[WARNING] Параметр 'image_input' содержит placeholder: '{image_url}'. Убедитесь, что это валидный URL изображения")
        elif isinstance(image_input, str):
            image_url = image_input.strip()
            if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
                warnings.append(f"[WARNING] Параметр 'image_input' содержит placeholder: '{image_url}'. Убедитесь, что это валидный URL изображения")
        else:
            errors.append(f"[ERROR] Параметр 'image_input' должен быть строкой или массивом строк, получено: {type(image_input).__name__}")
    else:
        errors.append("[ERROR] Параметр 'image_url' или 'image_input' обязателен и не может быть пустым")
    
    # 2. Проверка audio_url или audio_input (обязательный, один URL)
    # Форма может передавать audio_url, но API ожидает audio_input (массив) или audio_url
    audio_url = None
    if 'audio_url' in data and data['audio_url']:
        audio_url = str(data['audio_url']).strip()
        # Проверяем на placeholder
        if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
            warnings.append(f"[WARNING] Параметр 'audio_url' содержит placeholder: '{audio_url}'. Убедитесь, что это валидный URL аудиофайла")
    elif 'audio_input' in data and data['audio_input']:
        # Если передан audio_input (массив или строка)
        audio_input = data['audio_input']
        if isinstance(audio_input, list):
            if len(audio_input) == 0:
                errors.append("[ERROR] Параметр 'audio_input' не может быть пустым массивом")
            elif len(audio_input) > 1:
                errors.append(f"[ERROR] Параметр 'audio_input' должен содержать только 1 URL, получено: {len(audio_input)}")
            else:
                audio_url = str(audio_input[0]).strip()
                if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
                    warnings.append(f"[WARNING] Параметр 'audio_input' содержит placeholder: '{audio_url}'. Убедитесь, что это валидный URL аудиофайла")
        elif isinstance(audio_input, str):
            audio_url = audio_input.strip()
            if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
                warnings.append(f"[WARNING] Параметр 'audio_input' содержит placeholder: '{audio_url}'. Убедитесь, что это валидный URL аудиофайла")
        else:
            errors.append(f"[ERROR] Параметр 'audio_input' должен быть строкой или массивом строк, получено: {type(audio_input).__name__}")
    else:
        errors.append("[ERROR] Параметр 'audio_url' или 'audio_input' обязателен и не может быть пустым")
    
    # 3. Проверка prompt (обязательный, макс. 5000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
        elif len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 5000)")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(audio_duration_seconds: float = 5.0) -> int:
    """
    Вычисляет цену в кредитах на основе длительности аудио
    
    Args:
        audio_duration_seconds: Длительность аудио в секундах (по умолчанию 5 секунд для примера, максимум 15 секунд)
        
    Returns:
        int: Цена в кредитах
    """
    # Ограничиваем до 15 секунд
    if audio_duration_seconds > 15:
        audio_duration_seconds = 15
    
    # 8 кредитов за секунду для 720P
    return int(8 * audio_duration_seconds)


# Тестовые данные из запроса пользователя
test_data = {
    "image_url": "Upload successfully",  # Обязательный (форма передает image_url, но может быть placeholder)
    "audio_url": "Upload successfully",  # Обязательный (форма передает audio_url, но может быть placeholder)
    "prompt": "Enter your prompt..."  # Обязательный (может быть placeholder)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для kling/v1-avatar-standard")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    # Проверяем image_url или image_input
    if 'image_url' in test_data:
        print(f"  image_url: '{test_data['image_url']}'")
    elif 'image_input' in test_data:
        print(f"  image_input: {test_data['image_input']}")
    # Проверяем audio_url или audio_input
    if 'audio_url' in test_data:
        print(f"  audio_url: '{test_data['audio_url']}'")
    elif 'audio_input' in test_data:
        print(f"  audio_input: {test_data['audio_input']}")
    print(f"  prompt: '{test_data.get('prompt', '')}' ({len(test_data.get('prompt', ''))} символов)")
    print()
    
    is_valid, errors, warnings = validate_kling_v1_avatar_standard_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        # Обрабатываем image_url или image_input
        if 'image_url' in test_data:
            image_url = str(test_data['image_url']).strip()
            if image_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - image_url: '{image_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - image_url: '{image_url}' [OK]")
        elif 'image_input' in test_data:
            image_input = test_data['image_input']
            if isinstance(image_input, list) and len(image_input) > 0:
                image_url = str(image_input[0]).strip()
            else:
                image_url = str(image_input).strip()
            print(f"  - image_input: '{image_url}' [OK]")
        
        # Обрабатываем audio_url или audio_input
        if 'audio_url' in test_data:
            audio_url = str(test_data['audio_url']).strip()
            if audio_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - audio_url: '{audio_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - audio_url: '{audio_url}' [OK]")
        elif 'audio_input' in test_data:
            audio_input = test_data['audio_input']
            if isinstance(audio_input, list) and len(audio_input) > 0:
                audio_url = str(audio_input[0]).strip()
            else:
                audio_url = str(audio_input).strip()
            print(f"  - audio_input: '{audio_url}' [OK]")
        
        prompt = test_data.get('prompt', '')
        if prompt.lower() in ['enter your prompt...', '']:
            print(f"  - prompt: '{prompt}' (placeholder, требуется валидный промпт) [WARNING]")
        else:
            print(f"  - prompt: {len(prompt)} символов (лимит: до 5000) [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется image_url или image_input (URL изображения для использования как аватар, 1 изображение)")
        print("  - Требуется audio_url или audio_input (URL аудиофайла, 1 файл)")
        print("  - Требуется prompt (промпт для генерации видео, до 5000 символов)")
        print("  - Модель генерирует видео с разрешением 720P, до 15 секунд")
        print()
        print("[PRICING] Ценообразование:")
        # Длительность определяется длиной аудиофайла (до 15 секунд)
        # Для примера используем 5 секунд
        example_duration = 5.0
        price = calculate_price_credits(example_duration)
        print(f"  - Примерная цена (для аудио длительностью {example_duration} секунд): {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * длительность аудиофайла (8 кредитов/сек для 720P, до 15 секунд)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * image_url/image_input не влияет на цену")
        print(f"    * audio_url/audio_input не влияет на цену (но длительность аудио влияет)")
        print(f"    * prompt не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Цена: 8 кредитов за секунду (720P)")
        print("    * Максимальная длительность: 15 секунд")
        print("    * Примеры:")
        print("      * 5 секунд: 40 кредитов (8 кредитов/сек × 5)")
        print("      * 10 секунд: 80 кредитов (8 кредитов/сек × 10)")
        print("      * 15 секунд: 120 кредитов (8 кредитов/сек × 15)")
        print("    * Длительность определяется автоматически по длине аудиофайла")
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
    
    # image_url или image_input - обязательный
    # API ожидает image_url (строка) или image_input (массив)
    if 'image_url' in test_data:
        image_url = str(test_data['image_url']).strip()
        if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
            api_data['image_url'] = image_url
    elif 'image_input' in test_data:
        image_input = test_data['image_input']
        if isinstance(image_input, list):
            if len(image_input) > 0:
                image_url = str(image_input[0]).strip()
                if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                    api_data['image_url'] = image_url
        elif isinstance(image_input, str):
            image_url = image_input.strip()
            if image_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                api_data['image_url'] = image_url
    
    # audio_url или audio_input - обязательный
    # API ожидает audio_url (строка) или audio_input (массив)
    if 'audio_url' in test_data:
        audio_url = str(test_data['audio_url']).strip()
        if audio_url.lower() not in ['upload successfully', 'file 1', 'preview']:
            api_data['audio_url'] = audio_url
    elif 'audio_input' in test_data:
        audio_input = test_data['audio_input']
        if isinstance(audio_input, list):
            if len(audio_input) > 0:
                audio_url = str(audio_input[0]).strip()
                if audio_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                    api_data['audio_url'] = audio_url
        elif isinstance(audio_input, str):
            audio_url = audio_input.strip()
            if audio_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                api_data['audio_url'] = audio_url
    
    # prompt - обязательный
    prompt = test_data.get('prompt', '')
    if prompt.lower() not in ['enter your prompt...', '']:
        api_data['prompt'] = prompt
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

