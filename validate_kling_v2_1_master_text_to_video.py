"""
Валидация входных данных для модели kling/v2-1-master-text-to-video
"""

def validate_kling_v2_1_master_text_to_video_input(data: dict) -> tuple[bool, list[str]]:
    """
    Валидирует входные данные для модели kling/v2-1-master-text-to-video
    
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
        if len(prompt) > 5000:
            errors.append(f"[ERROR] Параметр 'prompt' слишком длинный: {len(prompt)} символов (максимум 5000)")
        elif len(prompt) == 0:
            errors.append("[ERROR] Параметр 'prompt' не может быть пустым")
    
    # 2. Проверка duration (опциональный, enum)
    # Модель ожидает: ["5", "10"]
    # Форма может передавать: "5 seconds", "10 seconds"
    valid_durations = ["5", "10"]
    if 'duration' in data and data['duration']:
        duration = str(data['duration'])
        # Нормализуем значение (убираем " seconds" если есть)
        if " seconds" in duration.lower() or " second" in duration.lower():
            duration = duration.lower().replace(" seconds", "").replace(" second", "").strip()
        
        if duration not in valid_durations:
            errors.append(f"[ERROR] Параметр 'duration' имеет недопустимое значение: '{data['duration']}'. Допустимые значения: {', '.join(valid_durations)}")
    
    # 3. Проверка aspect_ratio (опциональный, enum)
    # Модель ожидает: ["16:9", "9:16", "1:1"]
    valid_aspect_ratios = ["16:9", "9:16", "1:1"]
    if 'aspect_ratio' in data and data['aspect_ratio']:
        aspect_ratio = str(data['aspect_ratio'])
        if aspect_ratio not in valid_aspect_ratios:
            errors.append(f"[ERROR] Параметр 'aspect_ratio' имеет недопустимое значение: '{aspect_ratio}'. Допустимые значения: {', '.join(valid_aspect_ratios)}")
    
    # 4. Проверка negative_prompt (опциональный)
    if 'negative_prompt' in data and data['negative_prompt']:
        negative_prompt = str(data['negative_prompt'])
        if len(negative_prompt) > 500:
            errors.append(f"[ERROR] Параметр 'negative_prompt' слишком длинный: {len(negative_prompt)} символов (максимум 500)")
    
    # 5. Проверка cfg_scale (опциональный, number)
    # ВАЖНО: В модели это float от 0 до 1 с шагом 0.1
    if 'cfg_scale' in data and data['cfg_scale']:
        try:
            # Обработка запятой как разделителя десятичных (0,5 -> 0.5)
            cfg_scale_str = str(data['cfg_scale']).replace(',', '.')
            cfg_scale = float(cfg_scale_str)
            
            if cfg_scale < 0 or cfg_scale > 1:
                errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть в диапазоне от 0 до 1, получено: {cfg_scale}")
            else:
                # Проверяем шаг 0.1 (округление до 1 знака после запятой)
                rounded = round(cfg_scale, 1)
                if abs(cfg_scale - rounded) > 0.01:
                    errors.append(f"[WARNING] Параметр 'cfg_scale' должен иметь шаг 0.1, получено: {cfg_scale}. Будет округлено до {rounded}")
        except (ValueError, TypeError):
            errors.append(f"[ERROR] Параметр 'cfg_scale' должен быть числом (0-1), получено: {data['cfg_scale']}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


# Тестовые данные из запроса пользователя
test_data = {
    "prompt": "First-person view from a soldier jumping from a transport plane — the camera shakes with turbulence, oxygen mask reflections flicker — as the clouds part, the battlefield below pulses with anti-air fire and missile trails.",
    "duration": "5 seconds",  # Форма передает "5 seconds", нужно нормализовать в "5"
    "aspect_ratio": "16:9",  # Указан
    "negative_prompt": "blur, distort, and low quality",
    "cfg_scale": "0,5"  # Указан с запятой (нужно конвертировать в 0.5)
}

if __name__ == "__main__":
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Валидация входных данных для kling/v2-1-master-text-to-video")
    print("=" * 60)
    print()
    
    print("[INFO] Проверяемые данные:")
    print(f"  prompt: '{test_data['prompt']}' ({len(test_data['prompt'])} символов)")
    print(f"  duration: '{test_data['duration']}'")
    print(f"  aspect_ratio: '{test_data['aspect_ratio']}'")
    print(f"  negative_prompt: '{test_data['negative_prompt']}' ({len(test_data['negative_prompt'])} символов)")
    print(f"  cfg_scale: '{test_data['cfg_scale']}'")
    print()
    
    is_valid, errors = validate_kling_v2_1_master_text_to_video_input(test_data)
    
    if is_valid:
        print("[OK] ВСЕ ДАННЫЕ КОРРЕКТНЫ!")
        print()
        print("[DETAILS] Детали:")
        print(f"  - prompt: {len(test_data['prompt'])} символов (лимит: 5000) [OK]")
        
        # Нормализация duration
        duration_normalized = str(test_data['duration']).lower().replace(" seconds", "").replace(" second", "").strip()
        print(f"  - duration: '{test_data['duration']}' -> нормализовано в '{duration_normalized}' [OK]")
        
        print(f"  - aspect_ratio: '{test_data['aspect_ratio']}' - валидное значение [OK]")
        print(f"  - negative_prompt: {len(test_data['negative_prompt'])} символов (лимит: 500) [OK]")
        
        # Конвертация cfg_scale
        cfg_scale_str = str(test_data['cfg_scale']).replace(',', '.')
        cfg_scale_val = float(cfg_scale_str)
        print(f"  - cfg_scale: '{test_data['cfg_scale']}' -> конвертировано в {cfg_scale_val} [OK]")
        print()
        print("[NOTE] Особенности модели:")
        print("  - Это модель text-to-video (не требует image_input)")
        print("  - duration влияет на цену: 5 секунд (160 кредитов), 10 секунд (320 кредитов)")
        print("  - aspect_ratio определяет соотношение сторон видео (16:9, 9:16, 1:1)")
        print("  - cfg_scale определяет, насколько близко модель следует промпту (0-1, шаг 0.1)")
        print("  - По умолчанию duration='5', aspect_ratio='16:9', cfg_scale=0.5")
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
    
    # duration - опциональный, но можно указать default
    if test_data.get('duration'):
        duration = str(test_data['duration'])
        # Нормализуем значение (убираем " seconds" если есть)
        if " seconds" in duration.lower() or " second" in duration.lower():
            duration = duration.lower().replace(" seconds", "").replace(" second", "").strip()
        api_data['duration'] = duration
    else:
        api_data['duration'] = "5"  # default
    
    # aspect_ratio - опциональный, но можно указать default
    if test_data.get('aspect_ratio'):
        api_data['aspect_ratio'] = test_data['aspect_ratio']
    else:
        api_data['aspect_ratio'] = "16:9"  # default
    
    # negative_prompt - только если не пустой
    if test_data.get('negative_prompt'):
        api_data['negative_prompt'] = test_data['negative_prompt']
    
    # cfg_scale - только если указан (как number!)
    if test_data.get('cfg_scale'):
        try:
            cfg_scale_str = str(test_data['cfg_scale']).replace(',', '.')
            cfg_scale_val = float(cfg_scale_str)
            # Округляем до 1 знака после запятой (шаг 0.1)
            api_data['cfg_scale'] = round(cfg_scale_val, 1)
        except (ValueError, TypeError):
            pass  # Пропускаем невалидный cfg_scale
    else:
        api_data['cfg_scale'] = 0.5  # default
    
    import json
    print(json.dumps(api_data, indent=2, ensure_ascii=False))

