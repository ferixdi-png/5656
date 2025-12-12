"""
Валидация входных данных для модели kling/v2-5-turbo-image-to-video-pro
"""

def validate_kling_v2_5_turbo_image_to_video_pro_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели kling/v2-5-turbo-image-to-video-pro
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 2500 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
        elif len(prompt) > 2500:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 2500)")
    
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
    
    # 3. Проверка tail_image_url (опциональный, один URL)
    if 'tail_image_url' in data and data['tail_image_url']:
        tail_image_url = str(data['tail_image_url']).strip()
        if tail_image_url:
            # Базовая проверка формата URL
            if not (tail_image_url.startswith('http://') or tail_image_url.startswith('https://')):
                # Предупреждение для placeholder значений
                if tail_image_url.lower().startswith('file') or 'upload' in tail_image_url.lower() or 'click' in tail_image_url.lower() or 'preview' in tail_image_url.lower():
                    warnings.append(f"[WARNING] URL tail_image_url может иметь неверный формат: '{tail_image_url[:50]}...' (должен начинаться с http:// или https://). Это может быть placeholder, который будет заменен на реальный URL.")
                else:
                    warnings.append(f"[WARNING] URL tail_image_url может иметь неверный формат: '{tail_image_url[:50]}...' (должен начинаться с http:// или https://)")
    
    # 4. Проверка duration (опциональный, enum: "5" или "10")
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
    
    # 5. Проверка negative_prompt (опциональный, макс. 2496 символов)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 2496:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 2496)")
    
    # 6. Проверка cfg_scale (опциональный, число от 0 до 1)
    # Форма может передавать: "0,5" (запятая) -> нужно нормализовать в 0.5
    if 'cfg_scale' in data and data['cfg_scale'] is not None:
        cfg_scale = data['cfg_scale']
        try:
            # Конвертируем строку в float, обрабатывая запятую и точку как разделитель
            if isinstance(cfg_scale, str):
                cfg_scale_str = cfg_scale.strip().replace(',', '.')
                cfg_scale_float = float(cfg_scale_str)
            elif isinstance(cfg_scale, (int, float)):
                cfg_scale_float = float(cfg_scale)
            else:
                errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть числом, получено: {type(cfg_scale).__name__}")
                cfg_scale_float = None
            
            if cfg_scale_float is not None:
                if cfg_scale_float < 0 or cfg_scale_float > 1:
                    errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть в диапазоне от 0 до 1, получено: {cfg_scale_float}")
        except ValueError:
            errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть числом, получено: '{cfg_scale}'")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(duration: str) -> int:
    """
    Вычисляет цену в кредитах на основе параметра duration
    
    Args:
        duration: Длительность видео ("5" или "10")
        
    Returns:
        int: Цена в кредитах
    """
    duration = str(duration).strip().lower()
    # Убираем "s" или "seconds" в конце, если есть
    if duration.endswith('seconds'):
        duration = duration[:-7].strip()
    elif duration.endswith('s'):
        duration = duration[:-1].strip()
    
    if duration == "10":
        return 84  # 10s
    else:  # duration == "5" (по умолчанию)
        return 42  # 5s


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "Astronaut instantly teleports through a glowing magical wooden door. Handheld tracking, camera stays 5–10 meters above and behind, smooth third-person chase. Hyper-realistic base, each scene with distinct art style, instant scene flashes with bright portal glow, high detail, 8K, epic orchestral undertones. High-frame interpolation for smooth motion and sharp instant transitions. Close-up: astronaut in white suit falls rapidly through glowing portal underfoot. First transition: LEGO Alps, high-saturation daylight, snowy peaks and valleys below, astronaut falls, next portal opens. Second transition: Amazon rainforest, dense canopy and rivers below, astronaut falls, next portal opens. Third transition: Ancient Egypt, Giza pyramids in mural style, desert and Nile below, astronaut falls, next portal opens. Fourth transition: abstract black-and-white ink style, Chinese Great Wall below, astronaut falls, final portal opens. Fifth transition: New York night, realistic dark skyline, glowing city lights, Empire State Building, astronaut hovers elegantly. Camera maintains constant distance, slight orbit, smooth third-person tracking throughout. Each portal transition is a sharp flash, emphasizing speed and magical journey, abrupt style and location shifts.",
    "image_url": "Upload successfully",  # Это будет заменено на реальный URL после загрузки
    "tail_image_url": "",  # Опциональный (пустой в данном случае)
    "duration": "5 seconds",  # Опциональный (форма может передавать с суффиксом "seconds")
    "negative_prompt": "blur, distort, and low quality",  # Опциональный
    "cfg_scale": "0,5"  # Опциональный (форма может передавать с запятой вместо точки)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для kling/v2-5-turbo-image-to-video-pro")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_url: '{test_data['image_url']}'")
    print(f"  tail_image_url: '{test_data.get('tail_image_url', '')}'")
    print(f"  duration: '{test_data.get('duration', '5')}'")
    print(f"  negative_prompt: '{test_data.get('negative_prompt', '')}' ({len(test_data.get('negative_prompt', ''))} символов)")
    print(f"  cfg_scale: '{test_data.get('cfg_scale', '0.5')}'")
    print()
    
    is_valid, errors, warnings = validate_kling_v2_5_turbo_image_to_video_pro_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: до 2500) [OK]")
        print(f"  - image_url: '{test_data['image_url']}' [OK]")
        
        tail_image_url = test_data.get('tail_image_url', '')
        if tail_image_url:
            print(f"  - tail_image_url: '{tail_image_url}' [OK]")
        else:
            print(f"  - tail_image_url: не указан (опциональный) [OK]")
        
        duration = str(test_data.get('duration', '5')).strip().lower()
        if duration.endswith('seconds'):
            duration_normalized = duration[:-7].strip()
        elif duration.endswith('s'):
            duration_normalized = duration[:-1].strip()
        else:
            duration_normalized = duration
        print(f"  - duration: '{test_data.get('duration', '5')}' -> нормализовано в '{duration_normalized}' [OK]")
        
        negative_prompt = test_data.get('negative_prompt', '')
        if negative_prompt:
            print(f"  - negative_prompt: {len(negative_prompt)} символов (лимит: до 2496) [OK]")
        else:
            print(f"  - negative_prompt: не указан (опциональный) [OK]")
        
        cfg_scale = test_data.get('cfg_scale')
        if cfg_scale is not None:
            cfg_scale_str = str(cfg_scale).strip().replace(',', '.')
            cfg_scale_float = float(cfg_scale_str)
            print(f"  - cfg_scale: '{cfg_scale}' -> нормализовано в {cfg_scale_float} [OK]")
        else:
            print(f"  - cfg_scale: не указан (опциональный, по умолчанию 0.5) [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемого движения в видео, до 2500 символов)")
        print("  - Требуется image_url (URL изображения для использования в качестве первого кадра)")
        print("  - Опционально tail_image_url (URL изображения для последнего кадра видео)")
        print("  - Опционально duration (длительность: 5 или 10 секунд, по умолчанию 5)")
        print("  - Опционально negative_prompt (что избегать в видео, до 2496 символов)")
        print("  - Опционально cfg_scale (CFG scale, число от 0 до 1, по умолчанию 0.5)")
        print()
        print("[PRICING] Ценообразование:")
        duration = str(test_data.get('duration', '5')).strip().lower()
        if duration.endswith('seconds'):
            duration = duration[:-7].strip()
        elif duration.endswith('s'):
            duration = duration[:-1].strip()
        price = calculate_price_credits(duration)
        print(f"  - Текущая цена: {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * duration='{duration}'")
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * image_url не влияет на цену")
        print(f"    * tail_image_url не влияет на цену")
        print(f"    * negative_prompt не влияет на цену")
        print(f"    * cfg_scale не влияет на цену")
        print()
        print("  - Таблица цен:")
        print("    * 5s: 42 кредита")
        print("    * 10s: 84 кредита")
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
    
    # tail_image_url - опциональный
    if test_data.get('tail_image_url'):
        api_data['tail_image_url'] = str(test_data['tail_image_url']).strip()
    
    # duration - опциональный (нормализуем, убирая "s"/"seconds")
    duration = str(test_data.get('duration', '5')).strip().lower()
    if duration.endswith('seconds'):
        duration = duration[:-7].strip()
    elif duration.endswith('s'):
        duration = duration[:-1].strip()
    api_data['duration'] = duration
    
    # negative_prompt - опциональный
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = str(test_data['negative_prompt']).strip()
    
    # cfg_scale - опциональный (нормализуем, заменяя запятую на точку)
    if test_data.get('cfg_scale') is not None:
        cfg_scale = test_data['cfg_scale']
        if isinstance(cfg_scale, str):
            cfg_scale_str = cfg_scale.strip().replace(',', '.')
            api_data['cfg_scale'] = float(cfg_scale_str)
        else:
            api_data['cfg_scale'] = float(cfg_scale)
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

