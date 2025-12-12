"""
Валидация входных данных для модели kling-2.6/image-to-video
"""

def validate_kling_2_6_image_to_video_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели kling-2.6/image-to-video
    
    Args:
        data: Словарь с входными данными
        
    Returns:
        tuple: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Проверка prompt (обязательный, макс. 1000 символов)
    if 'prompt' not in data or not data['prompt']:
        errors.append("[ERROR] Параметр 'prompt' обязателен и не может быть пустым")
    else:
        prompt = str(data['prompt'])
        if len(prompt) > 1000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 1000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка image_input/image_urls (обязательный, массив URL, 1 изображение)
    # Модель ожидает image_input как массив, но пользователь может передать image_urls или строку
    image_input = None
    if 'image_input' in data:
        image_input = data['image_input']
    elif 'image_urls' in data:
        # Конвертируем image_urls в image_input
        image_input = data['image_urls']
    elif 'image_url' in data:
        # Конвертируем image_url в image_input
        image_input = data['image_url']
    
    if not image_input:
        errors.append("[ERROR] Параметр 'image_input' (или 'image_urls', 'image_url') обязателен и не может быть пустым")
    else:
        # Конвертируем строку в массив
        if isinstance(image_input, str):
            image_input = [image_input]
        elif not isinstance(image_input, list):
            errors.append(f"[ERROR] Параметр 'image_input' должен быть массивом URL или строкой URL, получено: {type(image_input).__name__}")
            image_input = None
        
        if image_input:
            if len(image_input) == 0:
                errors.append("[ERROR] Параметр 'image_input' не может быть пустым массивом")
            elif len(image_input) > 1:
                warnings.append(f"[WARNING] Параметр 'image_input' содержит {len(image_input)} изображений, но модель поддерживает только 1 изображение. Будет использовано первое изображение.")
            else:
                # Проверяем URL
                url_str = str(image_input[0]).strip()
                if not url_str:
                    errors.append(f"[ERROR] URL изображения в массиве 'image_input' не может быть пустым")
                # Базовая проверка формата URL (должен начинаться с http:// или https://)
                elif not (url_str.startswith('http://') or url_str.startswith('https://')):
                    # Предупреждение для placeholder значений (например, "File 1")
                    if url_str.lower().startswith('file') or 'upload' in url_str.lower() or 'click' in url_str.lower():
                        warnings.append(f"[WARNING] URL изображения может иметь неверный формат: '{url_str[:50]}...' (должен начинаться с http:// или https://). Это может быть placeholder, который будет заменен на реальный URL.")
                    else:
                        warnings.append(f"[WARNING] URL изображения может иметь неверный формат: '{url_str[:50]}...' (должен начинаться с http:// или https://)")
    
    # 3. Проверка sound (обязательный, boolean)
    if 'sound' not in data or data['sound'] is None:
        errors.append("[ERROR] Параметр 'sound' обязателен и не может быть пустым")
    else:
        sound = data['sound']
        if not isinstance(sound, bool):
            # Попытка конвертировать строку в boolean
            if isinstance(sound, str):
                sound_str = str(sound).strip().lower()
                if sound_str not in ['true', 'false', '1', '0', 'yes', 'no', 'on', 'off']:
                    errors.append(f"[ERROR] Параметр 'sound' должен быть boolean (true/false), получено: '{sound}'")
            else:
                errors.append(f"[ERROR] Параметр 'sound' должен быть boolean (true/false), получено: {type(sound).__name__}")
    
    # 4. Проверка duration (обязательный, enum)
    # Модель ожидает: ["5", "10"]
    valid_durations = ["5", "10"]
    
    if 'duration' not in data or not data['duration']:
        errors.append("[ERROR] Параметр 'duration' обязателен и не может быть пустым")
    else:
        duration = str(data['duration']).strip()
        if duration not in valid_durations:
            errors.append(f"[ERROR] Параметр 'duration' имеет недопустимое значение: '{data['duration']}'. Допустимые значения: {', '.join(valid_durations)}")
    
    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def calculate_price_credits(duration: str, sound: bool) -> int:
    """
    Вычисляет цену в кредитах на основе параметров duration и sound
    
    Args:
        duration: Длительность видео ("5" или "10")
        sound: Наличие звука (True или False)
        
    Returns:
        int: Цена в кредитах
    """
    duration = str(duration).strip()
    if duration == "5":
        if sound:
            return 110  # 5s with audio
        else:
            return 55  # 5s no-audio
    else:  # duration == "10"
        if sound:
            return 220  # 10s with audio
        else:
            return 110  # 10s no-audio


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "In a bright rehearsal room, sunlight streams through the window, and a standing microphone is placed in the center of the room. [Campus band female lead singer] stands in front of the microphone with her eyes closed, while the other members stand around her. [Campus band female lead singer, full voice] leads: \"I will try to fix you, with all my heart and soul...\" The background is an a cappella harmony, and the camera slowly circles around the band members.",
    "image_urls": "File 1",  # Это будет заменено на реальный URL после загрузки
    "sound": True,  # Обязательный, boolean
    "duration": "5"  # Обязательный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для kling-2.6/image-to-video")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  image_urls: '{test_data['image_urls']}'")
    print(f"  sound: {test_data['sound']}")
    print(f"  duration: '{test_data['duration']}'")
    print()
    
    is_valid, errors, warnings = validate_kling_2_6_image_to_video_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 1000) [OK]")
        print(f"  - image_urls: '{test_data['image_urls']}' - будет заменено на реальный URL [OK]")
        print(f"  - sound: {test_data['sound']} [OK]")
        print(f"  - duration: '{test_data['duration']}' секунд [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемого движения, макс. 1000 символов)")
        print("  - Требуется image_input (1 изображение для генерации видео)")
        print("  - Требуется sound (boolean: добавить звук в видео)")
        print("  - Требуется duration (длительность видео: 5 или 10 секунд)")
        print()
        print("[PRICING] Ценообразование:")
        duration = str(test_data.get('duration', '5')).strip()
        sound = test_data.get('sound', False)
        if isinstance(sound, str):
            sound = str(sound).strip().lower() in ['true', '1', 'yes', 'on']
        
        price = calculate_price_credits(duration, sound)
        print(f"  - Текущая цена: {price} кредитов")
        print(f"  - Параметры влияют на цену:")
        print(f"    * duration='{duration}' секунд")
        print(f"    * sound={sound}")
        print()
        print("  - Таблица цен:")
        print("    * 5s без звука: 55 кредитов")
        print("    * 5s со звуком: 110 кредитов")
        print("    * 10s без звука: 110 кредитов")
        print("    * 10s со звуком: 220 кредитов")
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
    
    # image_input - обязательный (конвертируем image_urls в массив, если строка)
    image_input = test_data.get('image_urls') or test_data.get('image_input')
    if isinstance(image_input, str):
        image_input = [image_input]
    api_data['image_input'] = image_input
    
    # sound - обязательный (boolean)
    sound = test_data['sound']
    if isinstance(sound, str):
        sound = str(sound).strip().lower() in ['true', '1', 'yes', 'on']
    api_data['sound'] = bool(sound)
    
    # duration - обязательный
    api_data['duration'] = str(test_data['duration']).strip()
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




