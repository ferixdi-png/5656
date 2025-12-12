"""
Валидация входных данных для модели kling-2.6/text-to-video
"""

def validate_kling_2_6_text_to_video_input(data: dict) -> tuple[bool, list[str], list[str]]:
    """
    Валидирует входные данные для модели kling-2.6/text-to-video
    
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
    
    # 2. Проверка sound (обязательный, boolean)
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
    
    # 3. Проверка aspect_ratio (обязательный, enum)
    # Модель ожидает: ["1:1", "16:9", "9:16"]
    valid_aspect_ratios = ["1:1", "16:9", "9:16"]
    
    if 'aspect_ratio' not in data or not data['aspect_ratio']:
        errors.append("[ERROR] Параметр 'aspect_ratio' обязателен и не может быть пустым")
    else:
        aspect_ratio = str(data['aspect_ratio']).strip()
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{data['aspect_ratio']}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
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
    "prompt": "Visual: In a fashion live-streaming room, clothes hang on a rack, and a full-length mirror reflects the host's figure. Dialog: [African-American female host] turns to show off the sweatshirt fit. [African-American female host, cheerful voice] says: \"360-degree flawless cut, slimming and flattering.\" Immediately, [African-American female host] moves closer to the camera. [African-American female host, lively voice] says: \"Double-sided brushed fleece, 30 dollars off with purchase now.\"",
    "sound": True,  # Обязательный, boolean
    "aspect_ratio": "1:1",  # Обязательный
    "duration": "5"  # Обязательный
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для kling-2.6/text-to-video")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt'][:100]}...' ({len(test_data['prompt'])} символов)")
    print(f"  sound: {test_data['sound']}")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}'")
    print(f"  duration: '{test_data['duration']}'")
    print()
    
    is_valid, errors, warnings = validate_kling_2_6_text_to_video_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 1000) [OK]")
        print(f"  - sound: {test_data['sound']} [OK]")
        print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        print(f"  - duration: '{test_data['duration']}' секунд [OK]")
        print()
        if warnings:
            print("[WARNING] Предупреждения:")
            for warning in warnings:
                print(f"  {warning}")
            print()
        print("[NOTE] Особенности модели:")
        print("  - Требуется prompt (текстовое описание желаемого видео с визуальными и диалоговыми элементами, макс. 1000 символов)")
        print("  - Требуется sound (boolean: добавить звук в видео)")
        print("  - Требуется aspect_ratio (соотношение сторон видео: 1:1, 16:9, 9:16)")
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
        print(f"  - Параметры НЕ влияют на цену:")
        print(f"    * aspect_ratio='{test_data.get('aspect_ratio', '1:1')}' не влияет на цену")
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
    
    # sound - обязательный (boolean)
    sound = test_data['sound']
    if isinstance(sound, str):
        sound = str(sound).strip().lower() in ['true', '1', 'yes', 'on']
    api_data['sound'] = bool(sound)
    
    # aspect_ratio - обязательный
    api_data['aspect_ratio'] = str(test_data['aspect_ratio']).strip()
    
    # duration - обязательный
    api_data['duration'] = str(test_data['duration']).strip()
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))




