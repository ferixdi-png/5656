"""
Валидация входных данных для модели wan/2-5-image-to-video
"""

def validate_wan_2_5_image_to_video_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели wan/2-5-image-to-video
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 800 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
        elif len(prompt) > 800:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 800)")
    
    # 2. Проверка image_url/image_input (обязательный, один URL)
    # Модель ожидает image_url, но форма может передавать image_input
    # В bot_kie.py image_input конвертируется в image_url (берется первый элемент, если массив)
    image_url = None
    if 'image_url' in data:
        image_url = data['image_url']
    elif 'image_input' in data:
        image_input = data['image_input']
        # Если это массив, берем первый элемент
        if isinstance(image_input, list):
            if len(image_input) > 0:
                image_url = image_input[0]
            else:
                errors.append("[ERROR] Параметр 'image_input' не может быть пустым массивом")
        else:
            image_url = image_input
    
    if not image_url:
        errors.append("[ERROR] Параметр 'image_url' (или 'image_input') обязателен и не может быть пустым")
    else:
        image_url_str = str(image_url).strip()
        if not image_url_str:
            errors.append("[ERROR] Параметр 'image_url' не может быть пустым")
        # Базовая проверка формата URL (должен начинаться с http:// или https://)
        elif not (image_url_str.startswith('http://') or image_url_str.startswith('https://')):
            # Предупреждение для placeholder значений
            if image_url_str.lower().startswith('file') or 'upload' in image_url_str.lower() or 'click' in image_url_str.lower() or 'preview' in image_url_str.lower() or 'successfully' in image_url_str.lower():
                warnings.append(f"[WARNING] URL изображения может иметь неверный формат: '{image_url_str[:50]}...' (должен начинаться с http:// или https://). Это может быть placeholder, который будет заменен на реальный URL.")
            else:
                warnings.append(f"[WARNING] URL изображения может иметь неверный формат: '{image_url_str[:50]}...' (должен начинаться с http:// или https://)")
    
    # 3. Проверка duration (опциональный, enum: "5" или "10")
    # Форма может передавать: "5 seconds" -> нужно извлечь "5"
    valid_durations = ["5", "10"]
    
    if 'duration' in data and data['duration']:
        duration = str(data['duration']).strip().lower()
        # Убираем "s" или "seconds" в конце, если есть
        if duration.endswith('seconds'):
            duration = duration[:-7].strip()
        elif duration.endswith('s'):
            duration = duration[:-1].strip()
        
        if duration not in valid_durations:
            errors.append(f"[ERROR] Параметр 'duration' имеет недопустимое значение: '{data['duration']}'. Допустимые значения: {', '.join(valid_durations)} (или с суффиксом 's'/'seconds': 5s, 10s, 5 seconds, 10 seconds)")
    
    # 4. Проверка resolution (опциональный, enum: "720p" или "1080p")
    valid_resolutions = ["720p", "1080p"]
    
    if 'resolution' in data and data['resolution']:
        resolution = str(data['resolution']).strip().lower()
        # Убеждаемся, что есть суффикс "p"
        if not resolution.endswith('p'):
            resolution = resolution + 'p'
        
        if resolution not in valid_resolutions:
            errors.append(f"[ERROR] Параметр 'resolution' имеет недопустимое значение: '{data['resolution']}'. Допустимые значения: {', '.join(valid_resolutions)}")
    
    # 5. Проверка negative_prompt (опциональный, макс. 500 символов)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 500)")
    
    # 6. Проверка enable_prompt_expansion (опциональный, boolean)
    if 'enable_prompt_expansion' in data and data['enable_prompt_expansion'] is not None:
        enable_prompt_expansion = data['enable_prompt_expansion']
        # Конвертируем строку в boolean, если нужно
        if isinstance(enable_prompt_expansion, str):
            enable_prompt_expansion_str = enable_prompt_expansion.strip().lower()
            if enable_prompt_expansion_str not in ['true', 'false', '1', '0', 'yes', 'no']:
                errors.append(f"[ERROR] Параметр 'enable_prompt_expansion' должен быть boolean (true/false), получено: '{enable_prompt_expansion}'")
        elif not isinstance(enable_prompt_expansion, bool):
            errors.append(f"[ERROR] Параметр 'enable_prompt_expansion' должен быть boolean, получено: {type(enable_prompt_expansion).__name__}")
    
    # 7. Проверка seed (опциональный, целое число)
    if 'seed' in data and data['seed'] is not None:
        seed = data['seed']
        try:
            # Конвертируем в целое число
            if isinstance(seed, str):
                seed_str = seed.strip()
                # Убираем десятичную часть, если есть
                if '.' in seed_str:
                    seed_str = seed_str.split('.')[0]
                seed_int = int(seed_str)
            elif isinstance(seed, (int, float)):
                seed_int = int(seed)
            else:
                errors.append(f"[ERROR] Параметр 'seed' должен быть числом (целым), получено: {type(seed).__name__}")
        except ValueError:
            errors.append(f"[ERROR] Параметр 'seed' должен быть числом (целым), получено: '{seed}'")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(duration: str, resolution: str) -> int:
    """
    Вычисляет цену в кредитах на основе параметров duration и resolution
    
    Args:
        duration: Длительность видео ("5" или "10")
        resolution: Разрешение видео ("720p" или "1080p")
        
    Returns:
        int: Цена в кредитах
    """
    duration = str(duration).strip().lower()
    # Убираем "s" или "seconds" в конце, если есть
    if duration.endswith('seconds'):
        duration = duration[:-7].strip()
    elif duration.endswith('s'):
        duration = duration[:-1].strip()
    
    resolution = str(resolution).strip().lower()
    # Убеждаемся, что есть суффикс "p"
    if not resolution.endswith('p'):
        resolution = resolution + 'p'
    
    duration_int = int(duration) if duration.isdigit() else 5
    
    if resolution == "1080p":
        return 20 * duration_int  # 20 кредитов за секунду
    else:  # 720p (по умолчанию)
        return 12 * duration_int  # 12 кредитов за секунду


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "The same woman from the reference image looks directly into the camera, takes a breath, then smiles brightly and speaks with enthusiasm: \"Have you heard? Alibaba Wan 2.5 API is now available on Kie.ai!\" Ambient audio: quiet indoor atmosphere, soft natural room tone. Camera: medium close-up, steady framing, natural daylight mood, accurate lip-sync with dialogue.",
    "image_url": "Upload successfully",  # Это будет заменено на реальный URL после загрузки
    "duration": "5 seconds",  # Опциональный (форма может передавать с суффиксом "seconds")
    "resolution": "720p",  # Опциональный
    "negative_prompt": "",  # Опциональный (пустой в данном случае)
    "enable_prompt_expansion": True,  # Опциональный (boolean)
    "seed": None  # Опциональный (не указан в данном случае)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для wan/2-5-image-to-video")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  duration: '{test_data.get('duration', '5')}'")
    print(f"  resolution: '{test_data.get('resolution', '720p')}'")
    print(f"  negative_prompt: '{test_data.get('negative_prompt', '')}' ({len(test_data.get('negative_prompt', ''))} символов)")
    print(f"  enable_prompt_expansion: {test_data.get('enable_prompt_expansion', True)}")
    print(f"  seed: {test_data.get('seed', 'не указан')}")
    print()
    
    is_valid, errors, warnings = validate_wan_2_5_image_to_video_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: до 800) [OK]")
        print(f"  - image_url: '{test_data['image_url']}' [OK]")
        
        duration = str(test_data.get('duration', '5')).strip().lower()
        if duration.endswith('seconds'):
            duration_normalized = duration[:-7].strip()
        elif duration.endswith('s'):
            duration_normalized = duration[:-1].strip()
        else:
            duration_normalized = duration
        print(f"  - duration: '{test_data.get('duration', '5')}' -> нормализовано в '{duration_normalized}' [OK]")
        
        resolution = str(test_data.get('resolution', '720p')).strip().lower()
        if not resolution.endswith('p'):
            resolution = resolution + 'p'
        print(f"  - resolution: '{test_data.get('resolution', '720p')}' -> нормализовано в '{resolution}' [OK]")
        
        negative_prompt = test_data.get('negative_prompt', '')
        if negative_prompt:
            print(f"  - negative_prompt: {len(negative_prompt)} символов (лимит: до 500) [OK]")
        else:
            print(f"  - negative_prompt: не указан (опциональный) [OK]")
        
        enable_prompt_expansion = test_data.get('enable_prompt_expansion', True)
        print(f"  - enable_prompt_expansion: {enable_prompt_expansion} [OK]")
        
        seed = test_data.get('seed')
        if seed is not None:
            print(f"  - seed: {seed} [OK]")
        else:
            print(f"  - seed: не указан (опциональный) [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемого движения в видео, до 800 символов)")
        print("  - Требуется image_url (URL изображения для использования как первый кадр)")
        print("  - Опционально duration (длительность: 5 или 10 секунд, по умолчанию 5)")
        print("  - Опционально resolution (разрешение: 720p или 1080p, по умолчанию 720p)")
        print("  - Опционально negative_prompt (что избегать в видео, до 500 символов)")
        print("  - Опционально enable_prompt_expansion (включить переписывание промпта с помощью LLM, по умолчанию True)")
        print("  - Опционально seed (случайное число для воспроизводимости)")
        print()
        print("[PRICING] Ценообразование:")
        duration = str(test_data.get('duration', '5')).strip().lower()
        if duration.endswith('seconds'):
            duration = duration[:-7].strip()
        elif duration.endswith('s'):
            duration = duration[:-1].strip()
        resolution = str(test_data.get('resolution', '720p')).strip().lower()
        if not resolution.endswith('p'):
            resolution = resolution + 'p'
        price = calculate_price_credits(duration, resolution)
        print(f"  - Текущая цена: {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * duration='{duration}'")
        print(f"    * resolution='{resolution}'")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * prompt не влияет на цену")
        print(f"    * image_url не влияет на цену")
        print(f"    * negative_prompt не влияет на цену")
        print(f"    * enable_prompt_expansion не влияет на цену")
        print(f"    * seed не влияет на цену")
        print()
        print("  - Таблица цен:")
        print("    * 720p, 5s: 60 кредитов (12 кредитов/сек × 5)")
        print("    * 720p, 10s: 120 кредитов (12 кредитов/сек × 10)")
        print("    * 1080p, 5s: 100 кредитов (20 кредитов/сек × 5)")
        print("    * 1080p, 10s: 200 кредитов (20 кредитов/сек × 10)")
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
    
    # image_url - обязательный (конвертируем image_input в image_url, если нужно)
    image_url = test_data.get('image_url') or test_data.get('image_input')
    if isinstance(image_url, list) and len(image_url) > 0:
        image_url = image_url[0]
    api_data['image_url'] = str(image_url).strip()
    
    # duration - опциональный (нормализуем, убирая "s"/"seconds")
    duration = str(test_data.get('duration', '5')).strip().lower()
    if duration.endswith('seconds'):
        duration = duration[:-7].strip()
    elif duration.endswith('s'):
        duration = duration[:-1].strip()
    api_data['duration'] = duration
    
    # resolution - опциональный (нормализуем, добавляя "p" если нужно)
    resolution = str(test_data.get('resolution', '720p')).strip().lower()
    if not resolution.endswith('p'):
        resolution = resolution + 'p'
    api_data['resolution'] = resolution
    
    # negative_prompt - опциональный
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = str(test_data['negative_prompt']).strip()
    
    # enable_prompt_expansion - опциональный (конвертируем в boolean)
    if test_data.get('enable_prompt_expansion') is not None:
        enable_prompt_expansion = test_data['enable_prompt_expansion']
        if isinstance(enable_prompt_expansion, str):
            enable_prompt_expansion = enable_prompt_expansion.strip().lower()
            api_data['enable_prompt_expansion'] = enable_prompt_expansion in ['true', '1', 'yes']
        else:
            api_data['enable_prompt_expansion'] = bool(enable_prompt_expansion)
    
    # seed - опциональный (конвертируем в целое число)
    if test_data.get('seed') is not None:
        seed = test_data['seed']
        if isinstance(seed, str):
            seed_str = seed.strip()
            if '.' in seed_str:
                seed_str = seed_str.split('.')[0]
            api_data['seed'] = int(seed_str)
        else:
            api_data['seed'] = int(seed)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))



