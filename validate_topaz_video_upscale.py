"""
Валидация входных данных для модели topaz/video-upscale
"""

def validate_topaz_video_upscale_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели topaz/video-upscale
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка video_url или video_input (обязательный, один URL)
    # Форма может передавать video_url, но API ожидает video_input (массив) или video_url
    video_url = None
    if 'video_url' in data and data['video_url']:
        video_url = str(data['video_url']).strip()
        # Проверяем на placeholder
        if video_url.lower() in ['upload successfully', 'file 1', 'preview']:
            warnings.append(f"[WARNING] Параметр 'video_url' содержит placeholder: '{video_url}'. Убедитесь, что это валидный URL видео")
    elif 'video_input' in data and data['video_input']:
        # Если передан video_input (массив или строка)
        video_input = data['video_input']
        if isinstance(video_input, list):
            if len(video_input) == 0:
                errors.append("[ERROR] Параметр 'video_input' не может быть пустым массивом")
            elif len(video_input) > 1:
                errors.append(f"[ERROR] Параметр 'video_input' должен содержать только 1 URL, получено: {len(video_input)}")
            else:
                video_url = str(video_input[0]).strip()
                if video_url.lower() in ['upload successfully', 'file 1', 'preview']:
                    warnings.append(f"[WARNING] Параметр 'video_input' содержит placeholder: '{video_url}'. Убедитесь, что это валидный URL видео")
        elif isinstance(video_input, str):
            video_url = video_input.strip()
            if video_url.lower() in ['upload successfully', 'file 1', 'preview']:
                warnings.append(f"[WARNING] Параметр 'video_input' содержит placeholder: '{video_url}'. Убедитесь, что это валидный URL видео")
        else:
            errors.append(f"[ERROR] Параметр 'video_input' должен быть строкой или массивом строк, получено: {type(video_input).__name__}")
    else:
        errors.append("[ERROR] Параметр 'video_url' или 'video_input' обязателен и не может быть пустым")
    
    # 2. Проверка upscale_factor (опциональный, enum: "1", "2" или "4")
    # Форма может передавать "1x", "2x", "4x" -> нужно нормализовать в "1", "2", "4"
    valid_upscale_factors = ["1", "2", "4"]
    
    if 'upscale_factor' in data and data['upscale_factor']:
        upscale_factor = str(data['upscale_factor']).strip().lower()
        # Убираем "x" в конце, если есть
        if upscale_factor.endswith('x'):
            upscale_factor = upscale_factor[:-1].strip()
        
        if upscale_factor not in valid_upscale_factors:
            errors.append(f"[ERROR] Параметр 'upscale_factor' имеет недопустимое значение: '{data['upscale_factor']}'. Допустимые значения: {', '.join(valid_upscale_factors)} (или с суффиксом 'x': 1x, 2x, 4x)")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(video_duration_seconds: float = 5.0) -> int:
    """
    Вычисляет цену в кредитах на основе длительности входного видео
    
    Args:
        video_duration_seconds: Длительность входного видео в секундах (по умолчанию 5 секунд для примера)
        
    Returns:
        int: Цена в кредитах
    """
    # 12 кредитов за секунду
    return int(12 * video_duration_seconds)


# Тестовые данные из запроса пользователя
test_data = {
    "video_url": "Upload successfully",  # Обязательный (форма передает video_url, но может быть placeholder)
    "upscale_factor": "2x"  # Опциональный (форма может передавать "2x", нужно нормализовать в "2")
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для topaz/video-upscale")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    # Проверяем video_url или video_input
    if 'video_url' in test_data:
        print(f"  video_url: '{test_data['video_url']}'")
    elif 'video_input' in test_data:
        print(f"  video_input: {test_data['video_input']}")
    print(f"  upscale_factor: '{test_data.get('upscale_factor', '2')}'")
    print()
    
    is_valid, errors, warnings = validate_topaz_video_upscale_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        # Обрабатываем video_url или video_input
        if 'video_url' in test_data:
            video_url = str(test_data['video_url']).strip()
            if video_url.lower() in ['upload successfully', 'file 1', 'preview']:
                print(f"  - video_url: '{video_url}' (placeholder, требуется валидный URL) [WARNING]")
            else:
                print(f"  - video_url: '{video_url}' [OK]")
        elif 'video_input' in test_data:
            video_input = test_data['video_input']
            if isinstance(video_input, list) and len(video_input) > 0:
                video_url = str(video_input[0]).strip()
            else:
                video_url = str(video_input).strip()
            print(f"  - video_input: '{video_url}' [OK]")
        
        upscale_factor = str(test_data.get('upscale_factor', '2')).strip().lower()
        if upscale_factor.endswith('x'):
            upscale_factor_normalized = upscale_factor[:-1].strip()
        else:
            upscale_factor_normalized = upscale_factor
        print(f"  - upscale_factor: '{test_data.get('upscale_factor', '2')}' -> нормализовано в '{upscale_factor_normalized}' [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется video_url или video_input (URL видео для увеличения разрешения, 1 видео)")
        print("  - Опционально upscale_factor (коэффициент увеличения: 1, 2 или 4, по умолчанию 2)")
        print("  - Модель увеличивает разрешение входного видео")
        print()
        print("[PRICING] Ценообразование:")
        # Длительность определяется длиной входного видео
        # Для примера используем 5 секунд
        example_duration = 5.0
        price = calculate_price_credits(example_duration)
        print(f"  - Примерная цена (для видео длительностью {example_duration} секунд): {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * длительность входного видео (12 кредитов/сек)")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * video_url/video_input не влияет на цену (но длительность видео влияет)")
        print(f"    * upscale_factor не влияет на цену")
        print()
        print("  - Информация о цене:")
        print("    * Цена: 12 кредитов за секунду входного видео")
        print("    * Примеры:")
        print("      * 5 секунд: 60 кредитов (12 кредитов/сек × 5)")
        print("      * 10 секунд: 120 кредитов (12 кредитов/сек × 10)")
        print("      * 15 секунд: 180 кредитов (12 кредитов/сек × 15)")
        print("    * Длительность определяется автоматически по длине входного видео")
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
    
    # video_url или video_input - обязательный
    # API ожидает video_url (строка) или video_input (массив)
    if 'video_url' in test_data:
        video_url = str(test_data['video_url']).strip()
        if video_url.lower() not in ['upload successfully', 'file 1', 'preview']:
            api_data['video_url'] = video_url
    elif 'video_input' in test_data:
        video_input = test_data['video_input']
        if isinstance(video_input, list):
            if len(video_input) > 0:
                video_url = str(video_input[0]).strip()
                if video_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                    api_data['video_url'] = video_url
        elif isinstance(video_input, str):
            video_url = video_input.strip()
            if video_url.lower() not in ['upload successfully', 'file 1', 'preview']:
                api_data['video_url'] = video_url
    
    # upscale_factor - опциональный (нормализуем, убирая "x" если нужно)
    if test_data.get('upscale_factor'):
        upscale_factor = str(test_data['upscale_factor']).strip().lower()
        if upscale_factor.endswith('x'):
            upscale_factor = upscale_factor[:-1].strip()
        api_data['upscale_factor'] = upscale_factor
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




