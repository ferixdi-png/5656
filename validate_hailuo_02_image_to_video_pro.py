"""
Валидация входных данных для модели hailuo/02-image-to-video-pro
"""

def validate_hailuo_02_image_to_video_pro_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели hailuo/02-image-to-video-pro
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 1500 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
        elif len(prompt) > 1500:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 1500)")
    
    # 2. Проверка image_url или image_input (обязательный, один URL)
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
    
    # 3. Проверка end_image_url (опциональный, должен быть валидным URL)
    if 'end_image_url' in data and data['end_image_url']:
        end_image_url = str(data['end_image_url']).strip()
        if end_image_url:
            # Проверяем на placeholder
            if end_image_url.lower() in ['upload successfully', 'file 1', 'preview', 'click to upload or drag and drop']:
                warnings.append(f"[WARNING] Параметр 'end_image_url' содержит placeholder: '{end_image_url}'. Убедитесь, что это валидный URL изображения")
            # Проверяем формат URL
            elif not (end_image_url.startswith('http://') or end_image_url.startswith('https://')):
                errors.append(f"[ERROR] Параметр 'end_image_url' должен быть валидным URL (начинаться с http:// или https://), получено: '{end_image_url[:50]}...'")
    
    # 4. Проверка prompt_optimizer (опциональный, boolean)
    if 'prompt_optimizer' in data and data['prompt_optimizer'] is not None:
        prompt_optimizer = data['prompt_optimizer']
        # Конвертируем строку в boolean, если нужно
        if isinstance(prompt_optimizer, str):
            prompt_optimizer_str = prompt_optimizer.strip().lower()
            if prompt_optimizer_str not in ['true', 'false', '1', '0', 'yes', 'no']:
                errors.append(f"[ERROR] Параметр 'prompt_optimizer' должен быть boolean (true/false), получено: '{prompt_optimizer}'")
        elif not isinstance(prompt_optimizer, bool):
            errors.append(f"[ERROR] Параметр 'prompt_optimizer' должен быть boolean, получено: {type(prompt_optimizer).__name__}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits() -> int:
    """
    Вычисляет цену в кредитах для модели hailuo/02-image-to-video-pro
    
    Returns:
        int: Цена в кредитах (фиксированная: 57 кредитов за 6-секундное 1080p видео)
    """
    # Фиксированная цена: 9.5 кредитов/сек × 6 секунд = 57 кредитов
    return 57


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Cinematic wide shot: A colossal starship drifts silently above the rings of Saturn, its metallic hull reflecting streaks of cosmic light. The camera pushes closer, revealing thousands of illuminated windows like a floating city. Smaller fighter crafts dart across the frame, leaving neon trails as they maneuver through the vastness of space. A sudden burst of thrusters scatters asteroid fragments in slow motion, glowing faintly as they collide and drift apart.",
    "image_url": "Upload successfully",  # Обязательный (форма передает image_url, но может быть placeholder)
    "end_image_url": "",  # Опциональный (пустой в данном случае)
    "prompt_optimizer": True  # Опциональный (boolean, по умолчанию True)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для hailuo/02-image-to-video-pro")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    # Проверяем image_url или image_input
    if 'image_url' in test_data:
        print(f"  image_url: '{test_data['image_url']}'")
    elif 'image_input' in test_data:
        print(f"  image_input: {test_data['image_input']}")
    print(f"  end_image_url: '{test_data.get('end_image_url', '')}'")
    print(f"  prompt_optimizer: {test_data.get('prompt_optimizer', True)}")
    print()
    
    is_valid, errors, warnings = validate_hailuo_02_image_to_video_pro_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: до 1500) [OK]")
        
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
        
        end_image_url = test_data.get('end_image_url', '')
        if end_image_url:
            if end_image_url.lower() in ['upload successfully', 'file 1', 'preview', 'click to upload or drag and drop']:
                print(f"  - end_image_url: '{end_image_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - end_image_url: '{end_image_url}' [OK]")
        else:
            print(f"  - end_image_url: не указан (опциональный) [OK]")
        
        prompt_optimizer = test_data.get('prompt_optimizer', True)
        print(f"  - prompt_optimizer: {prompt_optimizer} [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемой анимации видео, до 1500 символов)")
        print("  - Требуется image_url или image_input (URL входного изображения для анимации, 1 изображение)")
        print("  - Опционально end_image_url (URL изображения для использования как последний кадр видео)")
        print("  - Опционально prompt_optimizer (использовать оптимизатор промпта модели, по умолчанию True)")
        print("  - Модель генерирует 6-секундное 1080p видео из изображения")
        print()
        print("[PRICING] Ценообразование:")
        price = calculate_price_credits()
        print(f"  - Текущая цена: {price} кредитов (фиксированная)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * prompt не влияет на цену")
        print(f"    * image_url/image_input не влияет на цену")
        print(f"    * end_image_url не влияет на цену")
        print(f"    * prompt_optimizer не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Фиксированная цена: 57 кредитов за 6-секундное 1080p видео")
        print("    * Расчет: 9.5 кредитов/сек × 6 секунд = 57 кредитов")
        print("    * Все генерации имеют одинаковую цену независимо от параметров")
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
    
    # end_image_url - опциональный (должен быть валидным URL)
    if test_data.get('end_image_url'):
        end_image_url = str(test_data['end_image_url']).strip()
        if end_image_url and end_image_url.lower() not in ['upload successfully', 'file 1', 'preview', 'click to upload or drag and drop']:
            if end_image_url.startswith('http://') or end_image_url.startswith('https://'):
                api_data['end_image_url'] = end_image_url
    
    # prompt_optimizer - опциональный (конвертируем в boolean)
    if test_data.get('prompt_optimizer') is not None:
        prompt_optimizer = test_data['prompt_optimizer']
        if isinstance(prompt_optimizer, str):
            prompt_optimizer = prompt_optimizer.strip().lower()
            api_data['prompt_optimizer'] = prompt_optimizer in ['true', '1', 'yes']
        else:
            api_data['prompt_optimizer'] = bool(prompt_optimizer)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

